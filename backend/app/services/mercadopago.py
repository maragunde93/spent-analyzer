import asyncio
import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain import Currency, ExpenseSource, ImportLineKind
from app.models import Category, Earning, Expense, ImportBatch, ImportLine, MercadoPagoIntegration, Subcategory
from app.services.accounting import amount_to_ars
from app.services.audit import log_action
from app.services.categorizer import suggest_category
from app.services.merchant_learning import find_learned_suggestion, learn_from_expense
from app.services.recurring import should_suggest_recurring, sync_recurring_rule


MERCADOPAGO_REQUIRED_COLUMNS = {
    "TRANSACTION_DATE",
    "SOURCE_ID",
    "TRANSACTION_TYPE",
    "TRANSACTION_AMOUNT",
    "TRANSACTION_CURRENCY",
    "PAYMENT_METHOD_TYPE",
}

CARD_METHOD_TYPES = {"credit_card", "debit_card", "prepaid_card"}
TRANSFER_TOKENS = ("TRANSFER", "TRANSFERENCIA", "MONEY_TRANSFER")
REFUND_TOKENS = ("REFUND", "DEVOLUCION", "DEVOLUCIÓN", "REIMBURSEMENT", "CHARGEBACK", "REINTEGRO")
PURCHASE_TOKENS = ("PAYMENT", "SETTLEMENT", "COMPRA", "PAGO")


class MercadoPagoError(RuntimeError):
    pass


class MercadoPagoTemporaryError(MercadoPagoError):
    pass


@dataclass(frozen=True)
class MercadoPagoAccount:
    mp_user_id: str | None
    nickname: str | None
    site_id: str | None


@dataclass(frozen=True)
class MercadoPagoReport:
    file_name: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class MercadoPagoMovement:
    external_id: str
    date: date
    description: str
    kind: ImportLineKind
    currency: Currency
    amount: Decimal
    raw: dict[str, str]
    ignored_reason: str | None = None


@dataclass(frozen=True)
class MercadoPagoSyncResult:
    batch_id: int | None
    report_file_name: str
    imported: int
    ignored: int
    duplicates: int


class MercadoPagoClient:
    def __init__(
        self,
        access_token: str,
        api_base_url: str = "https://api.mercadopago.com",
        identity_base_url: str = "https://api.mercadolibre.com",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.access_token = access_token
        self.api_base_url = api_base_url.rstrip("/")
        self.identity_base_url = identity_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def headers(self) -> dict[str, str]:
        return {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

    async def validate_token(self) -> MercadoPagoAccount:
        data = await self._request_json("GET", f"{self.identity_base_url}/users/me")
        return MercadoPagoAccount(
            mp_user_id=str(data.get("id")) if data.get("id") is not None else None,
            nickname=data.get("nickname") or data.get("first_name"),
            site_id=data.get("site_id"),
        )

    async def create_report(self, begin: datetime, end: datetime) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"{self.api_base_url}/v1/account/settlement_report",
            json={
                "begin_date": _utc_iso(begin),
                "end_date": _utc_iso(end),
            },
            accepted_statuses={200, 202, 203},
        )

    async def list_reports(self) -> list[dict[str, Any]]:
        data = await self._request_json("GET", f"{self.api_base_url}/v1/account/settlement_report/list")
        if not isinstance(data, list):
            raise MercadoPagoError("Mercado Pago devolvio un listado de reportes inesperado")
        return data

    async def wait_for_report(
        self,
        begin: datetime,
        end: datetime,
        created_response: dict[str, Any] | None = None,
        poll_interval_seconds: float = 10.0,
        timeout_seconds: float = 180.0,
    ) -> MercadoPagoReport:
        direct_file = _file_name_from_report(created_response or {})
        if direct_file:
            return MercadoPagoReport(file_name=direct_file, raw=created_response or {})

        deadline = datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)
        while True:
            report = self._matching_report(await self.list_reports(), begin, end)
            if report is not None:
                file_name = _file_name_from_report(report)
                if file_name:
                    return MercadoPagoReport(file_name=file_name, raw=report)
            if datetime.now(timezone.utc) >= deadline:
                raise MercadoPagoTemporaryError("El reporte de Mercado Pago no estuvo listo antes del timeout")
            await asyncio.sleep(poll_interval_seconds)

    async def download_report(self, file_name: str) -> bytes:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.api_base_url}/v1/account/settlement_report/{file_name}",
                headers=self.headers,
            )
        if response.status_code == 401:
            raise MercadoPagoError("Token de Mercado Pago invalido")
        if response.status_code == 404:
            raise MercadoPagoTemporaryError("El archivo de reporte todavia no esta disponible")
        if response.status_code >= 500:
            raise MercadoPagoTemporaryError("Mercado Pago devolvio un error temporal")
        if response.status_code >= 400:
            raise MercadoPagoError(f"Mercado Pago devolvio HTTP {response.status_code}")
        return response.content

    async def _request_json(
        self,
        method: str,
        url: str,
        json: dict[str, Any] | None = None,
        accepted_statuses: set[int] | None = None,
    ) -> Any:
        accepted = accepted_statuses or {200}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.request(method, url, headers=self.headers, json=json)
        if response.status_code == 401:
            raise MercadoPagoError("Token de Mercado Pago invalido")
        if response.status_code >= 500:
            raise MercadoPagoTemporaryError("Mercado Pago devolvio un error temporal")
        if response.status_code not in accepted:
            raise MercadoPagoError(f"Mercado Pago devolvio HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError:
            return {}

    def _matching_report(self, reports: list[dict[str, Any]], begin: datetime, end: datetime) -> dict[str, Any] | None:
        begin_date = begin.date()
        end_date = end.date()
        matching = []
        for report in reports:
            file_name = _file_name_from_report(report)
            if not file_name:
                continue
            report_begin = _parse_report_date(report.get("begin_date"))
            report_end = _parse_report_date(report.get("end_date"))
            if report_begin and report_end and report_begin.date() <= begin_date and report_end.date() >= end_date:
                matching.append(report)
        if not matching:
            return None
        return sorted(matching, key=lambda item: str(item.get("date_created") or item.get("generation_date") or ""), reverse=True)[0]


def parse_report_csv(content: bytes) -> list[MercadoPagoMovement]:
    text = content.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    movements = [_movement_from_row(_normalize_row(row)) for row in rows]
    return [movement for movement in movements if movement is not None]


def validate_required_columns(content: bytes) -> set[str]:
    text = content.decode("utf-8-sig", errors="replace")
    first_line = text.splitlines()[0] if text.splitlines() else ""
    delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
    present = {header.strip().upper() for header in first_line.split(delimiter)}
    return MERCADOPAGO_REQUIRED_COLUMNS - present


async def sync_integration(
    db: Session,
    integration: MercadoPagoIntegration,
    *,
    client: MercadoPagoClient,
    overlap_days: int = 3,
    poll_interval_seconds: float = 10.0,
    poll_timeout_seconds: float = 180.0,
    now: datetime | None = None,
) -> MercadoPagoSyncResult:
    sync_started_at = now or datetime.utcnow()
    begin, end = _sync_window(integration.last_sync_at, overlap_days, sync_started_at)
    created = await client.create_report(begin, end)
    report = await client.wait_for_report(
        begin,
        end,
        created,
        poll_interval_seconds=poll_interval_seconds,
        timeout_seconds=poll_timeout_seconds,
    )
    content = await client.download_report(report.file_name)
    missing_columns = validate_required_columns(content)
    if missing_columns:
        raise MercadoPagoError(f"El reporte no contiene columnas requeridas: {', '.join(sorted(missing_columns))}")
    movements = parse_report_csv(content)
    result = import_movements(db, integration, movements, report.file_name)
    integration.last_sync_at = sync_started_at
    integration.last_sync_status = "ok"
    integration.last_sync_error = None
    integration.last_report_file_name = report.file_name
    db.commit()
    return result


def import_movements(
    db: Session,
    integration: MercadoPagoIntegration,
    movements: list[MercadoPagoMovement],
    report_file_name: str,
) -> MercadoPagoSyncResult:
    batch = ImportBatch(
        home_group_id=integration.home_group_id,
        uploaded_by_user_id=integration.user_id,
        filename=report_file_name,
        source_type="mercadopago_account_money",
        statement_account=integration.mp_user_id,
        period_label="Mercado Pago",
        status="committed",
    )
    db.add(batch)
    db.flush()

    imported = 0
    ignored = 0
    duplicates = 0
    for movement in movements:
        fingerprint = f"mercadopago:{integration.mp_user_id or integration.user_id}:{movement.external_id}"
        existing = db.scalar(
            select(ImportLine.id).where(
                ImportLine.home_group_id == integration.home_group_id,
                ImportLine.fingerprint == fingerprint,
            )
        )
        if existing is not None:
            duplicates += 1
            continue

        category_id, subcategory_id, recurring = _suggest_movement(db, integration.home_group_id, movement.description)
        line = ImportLine(
            import_batch_id=batch.id,
            home_group_id=integration.home_group_id,
            date=movement.date,
            description=movement.description,
            cardholder_name=None,
            coupon=None,
            kind=movement.kind,
            currency=movement.currency,
            original_amount=movement.amount,
            suggested_category_id=category_id,
            suggested_subcategory_id=subcategory_id,
            suggested_recurring=recurring,
            notes=movement.ignored_reason,
            status="ignored" if movement.ignored_reason else "committed",
            fingerprint=fingerprint,
            raw_text=json.dumps(movement.raw, ensure_ascii=True, sort_keys=True),
        )
        db.add(line)
        db.flush()

        if movement.ignored_reason:
            ignored += 1
            continue
        if movement.kind == ImportLineKind.income:
            _create_earning(db, integration, line)
        else:
            _create_expense(db, integration, line)
        imported += 1

    if imported == 0 and ignored == 0 and duplicates > 0:
        batch.status = "duplicate"
    log_action(
        db,
        integration.home_group_id,
        integration.user_id,
        "mercadopago_sync",
        "mercadopago_integration",
        f"Mercado Pago sincronizado: {imported} importados, {ignored} ignorados, {duplicates} duplicados",
        integration.id,
    )
    db.flush()
    return MercadoPagoSyncResult(batch.id, report_file_name, imported, ignored, duplicates)


async def run_daily_mercadopago_sync(
    session_factory: sessionmaker[Session],
    *,
    api_base_url: str,
    identity_base_url: str,
    hour_argentina: int,
    overlap_days: int,
    poll_interval_seconds: float,
    poll_timeout_seconds: float,
) -> None:
    while True:
        await asyncio.sleep(_seconds_until_next_hour(hour_argentina))
        with session_factory() as db:
            integrations = list(db.scalars(select(MercadoPagoIntegration).where(MercadoPagoIntegration.enabled.is_(True))))
            for integration in integrations:
                client = MercadoPagoClient(
                    integration.access_token,
                    api_base_url=api_base_url,
                    identity_base_url=identity_base_url,
                )
                try:
                    await sync_integration(
                        db,
                        integration,
                        client=client,
                        overlap_days=overlap_days,
                        poll_interval_seconds=poll_interval_seconds,
                        poll_timeout_seconds=poll_timeout_seconds,
                    )
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    integration.last_sync_status = "error"
                    integration.last_sync_error = str(exc)[:1000]
                    db.commit()


def _movement_from_row(row: dict[str, str]) -> MercadoPagoMovement | None:
    raw_external = _first(row, "SOURCE_ID", "EXTERNAL_REFERENCE", "ORDER_ID", "PAYMENT_ID")
    movement_date = _parse_movement_date(_first(row, "TRANSACTION_DATE", "SETTLEMENT_DATE", "DATE"))
    amount = _parse_decimal(_first(row, "REAL_AMOUNT", "SETTLEMENT_NET_AMOUNT", "TRANSACTION_AMOUNT"))
    currency = _currency(_first(row, "TRANSACTION_CURRENCY", "SETTLEMENT_CURRENCY", "CURRENCY"))
    if not raw_external or movement_date is None or amount is None or currency is None:
        return None

    transaction_type = _first(row, "TRANSACTION_TYPE", "MOVEMENT_TYPE", "TYPE").upper()
    payment_method_type = _first(row, "PAYMENT_METHOD_TYPE", "PAYMENT_METHOD").lower()
    description = _description(row)
    ignored_reason = None
    kind = ImportLineKind.purchase

    if payment_method_type in CARD_METHOD_TYPES:
        ignored_reason = "Operacion financiada con tarjeta vinculada"
        kind = ImportLineKind.card_payment
    elif _contains_any(transaction_type, REFUND_TOKENS) or _contains_any(description, REFUND_TOKENS):
        kind = ImportLineKind.reimbursement
        amount = -abs(amount)
    elif amount > 0:
        kind = ImportLineKind.income
    elif _contains_any(transaction_type, TRANSFER_TOKENS) or _contains_any(description, TRANSFER_TOKENS):
        kind = ImportLineKind.transfer
        amount = abs(amount)
    elif _contains_any(transaction_type, PURCHASE_TOKENS) or amount < 0:
        kind = ImportLineKind.purchase
        amount = abs(amount)

    external_id = hashlib.sha256(
        "|".join([raw_external, movement_date.isoformat(), str(amount), transaction_type, description]).encode("utf-8")
    ).hexdigest()[:40]
    return MercadoPagoMovement(
        external_id=external_id,
        date=movement_date,
        description=description,
        kind=kind,
        currency=currency,
        amount=amount,
        raw=row,
        ignored_reason=ignored_reason,
    )


def _create_expense(db: Session, integration: MercadoPagoIntegration, line: ImportLine) -> None:
    signed_amount = Decimal(line.original_amount)
    if line.kind == ImportLineKind.reimbursement:
        original_amount = -abs(signed_amount)
    else:
        original_amount = abs(signed_amount)
    amount_ars = amount_to_ars(db, original_amount, line.currency, line.date)
    expense = Expense(
        home_group_id=integration.home_group_id,
        date=line.date,
        description=line.description,
        category_id=line.suggested_category_id,
        subcategory_id=line.suggested_subcategory_id,
        paid_by_user_id=integration.user_id,
        uploaded_by_user_id=integration.user_id,
        source=ExpenseSource.mercadopago,
        currency=line.currency,
        original_amount=original_amount,
        amount_ars=amount_ars,
        import_line_id=line.id,
        notes=line.notes,
        is_recurring=line.suggested_recurring and original_amount > 0,
    )
    db.add(expense)
    db.flush()
    if original_amount > 0:
        learn_from_expense(db, expense)
    sync_recurring_rule(db, expense)


def _create_earning(db: Session, integration: MercadoPagoIntegration, line: ImportLine) -> None:
    amount = abs(Decimal(line.original_amount))
    db.add(
        Earning(
            home_group_id=integration.home_group_id,
            date=line.date,
            description=line.description,
            user_id=integration.user_id,
            uploaded_by_user_id=integration.user_id,
            currency=line.currency,
            original_amount=amount,
            amount_ars=amount_to_ars(db, amount, line.currency, line.date),
            import_line_id=line.id,
        )
    )


def _suggest_movement(db: Session, home_group_id: int, description: str) -> tuple[int | None, int | None, bool]:
    learned = find_learned_suggestion(db, home_group_id, description)
    if learned and learned.category_id is not None:
        return (
            learned.category_id,
            learned.subcategory_id,
            learned.is_recurring or should_suggest_recurring(db, home_group_id, description, learned.category_id),
        )
    categories = {category.name: category.id for category in db.scalars(select(Category).where(Category.home_group_id == home_group_id))}
    subcategories = {
        (subcategory.category_id, subcategory.name.upper()): subcategory.id
        for subcategory in db.scalars(select(Subcategory).where(Subcategory.home_group_id == home_group_id))
    }
    suggestion = suggest_category(description)
    category_id = categories.get(suggestion.name) if suggestion else None
    return category_id, _suggest_subcategory_id(description, category_id, subcategories), should_suggest_recurring(db, home_group_id, description, category_id)


def _suggest_subcategory_id(description: str, category_id: int | None, subcategories: dict[tuple[int, str], int]) -> int | None:
    if category_id is None:
        return None
    normalized = description.upper()
    for token, subcategory_name in {
        "EDESUR": "Electricidad",
        "EDENOR": "Electricidad",
        "AYSA": "Agua",
        "METROGAS": "Gas",
        "MOVISTAR": "Internet",
        "CLARO": "Internet",
        "SEGURO": "Seguro",
    }.items():
        if token in normalized:
            return subcategories.get((category_id, subcategory_name.upper()))
    return None


def _normalize_row(row: dict[str, str | None]) -> dict[str, str]:
    return {(key or "").strip().upper(): (value or "").strip() for key, value in row.items()}


def _first(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key, "").strip()
        if value:
            return value
    return ""


def _description(row: dict[str, str]) -> str:
    pieces = [
        _first(row, "DESCRIPTION", "TRANSACTION_DESCRIPTION", "EXTERNAL_REFERENCE"),
        _first(row, "PAYMENT_METHOD"),
        _first(row, "TRANSACTION_TYPE"),
    ]
    return " - ".join(dict.fromkeys(piece for piece in pieces if piece))[:240] or "Mercado Pago"


def _parse_decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(".", "").replace(",", ".") if "," in value else value)
    except (InvalidOperation, ValueError):
        return None


def _currency(value: str) -> Currency | None:
    try:
        return Currency(value.upper())
    except ValueError:
        return None


def _parse_movement_date(value: str) -> date | None:
    parsed = _parse_report_date(value)
    return parsed.date() if parsed else None


def _parse_report_date(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        try:
            return datetime.strptime(str(value)[:10], "%Y-%m-%d")
        except ValueError:
            return None


def _contains_any(value: str, tokens: tuple[str, ...]) -> bool:
    normalized = value.upper()
    return any(token in normalized for token in tokens)


def _file_name_from_report(report: dict[str, Any]) -> str | None:
    value = report.get("file_name") or report.get("filename")
    return str(value) if value else None


def _sync_window(last_sync_at: datetime | None, overlap_days: int, now: datetime) -> tuple[datetime, datetime]:
    end = datetime.combine(now.date(), time.max).replace(tzinfo=timezone.utc)
    if last_sync_at is None:
        begin_date = now.date() - timedelta(days=max(overlap_days, 7))
    else:
        begin_date = (last_sync_at.date() - timedelta(days=overlap_days))
    begin = datetime.combine(begin_date, time.min).replace(tzinfo=timezone.utc)
    return begin, end


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _seconds_until_next_hour(hour_argentina: int) -> float:
    argentina = timezone(timedelta(hours=-3))
    now = datetime.now(argentina)
    target = now.replace(hour=hour_argentina, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return max(1.0, (target - now).total_seconds())
