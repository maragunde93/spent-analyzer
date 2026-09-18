import asyncio
import csv
import hashlib
import io
import json
import logging
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.domain import Currency, ExpenseSource, ImportLineKind
from app.models import Category, Earning, Expense, ImportBatch, ImportLine, MercadoPagoIntegration, Subcategory
from app.services.accounting import amount_to_ars
from app.services.audit import log_action
from app.services.categorizer import suggest_category, suggest_shared
from app.services.merchant_learning import find_learned_suggestion, find_mercadopago_rule, learn_from_expense
from app.services.recurring import should_suggest_recurring, sync_recurring_rule


MERCADOPAGO_REQUIRED_COLUMNS = {
    "TRANSACTION_DATE",
    "SOURCE_ID",
    "TRANSACTION_TYPE",
    "TRANSACTION_AMOUNT",
    "TRANSACTION_CURRENCY",
    "PAYMENT_METHOD_TYPE",
}
MERCADOPAGO_REPORT_COLUMNS = (
    "EXTERNAL_REFERENCE",
    "SOURCE_ID",
    "USER_ID",
    "PAYMENT_METHOD_TYPE",
    "PAYMENT_METHOD",
    "SITE",
    "TRANSACTION_TYPE",
    "TRANSACTION_AMOUNT",
    "TRANSACTION_CURRENCY",
    "TRANSACTION_DATE",
    "FEE_AMOUNT",
    "SETTLEMENT_NET_AMOUNT",
    "SETTLEMENT_CURRENCY",
    "SETTLEMENT_DATE",
    "REAL_AMOUNT",
    "ORDER_ID",
    "BUSINESS_UNIT",
    "SUB_UNIT",
    "SALE_DETAIL",
)

CARD_METHOD_TYPES = {"credit_card", "debit_card", "prepaid_card"}
TRANSFER_TOKENS = ("TRANSFER", "TRANSFERENCIA", "MONEY_TRANSFER", "PAYOUT", "PAYOUTS", "WITHDRAWAL")
REFUND_TOKENS = ("REFUND", "DEVOLUCION", "DEVOLUCIÓN", "REIMBURSEMENT", "CHARGEBACK", "REINTEGRO")
PURCHASE_TOKENS = ("PAYMENT", "SETTLEMENT", "COMPRA", "PAGO")
logger = logging.getLogger(__name__)


class MercadoPagoError(RuntimeError):
    pass


class MercadoPagoTemporaryError(MercadoPagoError):
    pass


class MercadoPagoNotFoundError(MercadoPagoError):
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
    merchant_key: str | None = None
    collector_id: str | None = None
    store_id: str | None = None
    ignored_reason: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class MercadoPagoSyncResult:
    batch_id: int | None
    report_file_name: str
    imported: int
    ignored: int
    duplicates: int
    begin_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class MercadoPagoFetchedReport:
    report: MercadoPagoReport
    movements: list[MercadoPagoMovement]


class MercadoPagoClient:
    def __init__(
        self,
        access_token: str,
        api_base_url: str = "https://api.mercadopago.com",
        identity_base_url: str = "https://api.mercadolibre.com",
        timeout_seconds: float = 30.0,
        debug_http: bool = False,
        debug_http_max_chars: int = 12000,
    ) -> None:
        self.access_token = access_token
        self.api_base_url = api_base_url.rstrip("/")
        self.identity_base_url = identity_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.debug_http = debug_http
        self.debug_http_max_chars = debug_http_max_chars

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

    async def ensure_report_config(self, mp_user_id: str | None = None) -> dict[str, Any]:
        existing = await self.get_report_config()
        payload = _report_config_payload(existing, mp_user_id)
        if existing is None:
            return await self.create_report_config(payload)
        if _report_config_needs_update(existing):
            return await self.update_report_config(payload)
        return existing

    async def get_report_config(self) -> dict[str, Any] | None:
        try:
            return await self._request_json("GET", f"{self.api_base_url}/v1/account/settlement_report/config")
        except MercadoPagoNotFoundError:
            return None

    async def create_report_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"{self.api_base_url}/v1/account/settlement_report/config",
            json=payload,
            accepted_statuses={200, 201},
        )

    async def update_report_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json(
            "PUT",
            f"{self.api_base_url}/v1/account/settlement_report/config",
            json=payload,
            accepted_statuses={200},
        )

    async def get_payment(self, payment_id: str) -> dict[str, Any] | None:
        try:
            return await self._request_json("GET", f"{self.api_base_url}/v1/payments/{payment_id}")
        except MercadoPagoNotFoundError:
            return None
        except MercadoPagoError as exc:
            logger.info("No se pudo enriquecer pago de Mercado Pago %s: %s", payment_id, exc)
            return None

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

        report_id = str((created_response or {}).get("id") or "").strip() or None
        deadline = datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)
        while True:
            report = self._matching_report(await self.list_reports(), begin, end, report_id=report_id)
            if report is not None:
                file_name = _file_name_from_report(report)
                if file_name:
                    return MercadoPagoReport(file_name=file_name, raw=report)
            if datetime.now(timezone.utc) >= deadline:
                raise MercadoPagoTemporaryError("El reporte de Mercado Pago no estuvo listo antes del timeout")
            await asyncio.sleep(poll_interval_seconds)

    async def download_report(self, file_name: str) -> bytes:
        url = f"{self.api_base_url}/v1/account/settlement_report/{file_name}"
        self._log_request("GET", url, None)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                url,
                headers=self.headers,
            )
        self._log_response("GET", url, response)
        if response.status_code == 401:
            raise MercadoPagoError("Token de Mercado Pago invalido")
        if response.status_code == 404:
            raise MercadoPagoTemporaryError("El archivo de reporte todavia no esta disponible")
        if response.status_code >= 500:
            raise MercadoPagoTemporaryError("Mercado Pago devolvio un error temporal")
        if response.status_code >= 400:
            raise MercadoPagoError(_response_error_message(response))
        return response.content

    async def _request_json(
        self,
        method: str,
        url: str,
        json: dict[str, Any] | None = None,
        accepted_statuses: set[int] | None = None,
    ) -> Any:
        accepted = accepted_statuses or {200}
        self._log_request(method, url, json)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.request(method, url, headers=self.headers, json=json)
        self._log_response(method, url, response)
        if response.status_code == 401:
            raise MercadoPagoError("Token de Mercado Pago invalido")
        if response.status_code == 404:
            raise MercadoPagoNotFoundError(_response_error_message(response))
        if response.status_code >= 500:
            raise MercadoPagoTemporaryError("Mercado Pago devolvio un error temporal")
        if response.status_code not in accepted:
            raise MercadoPagoError(_response_error_message(response))
        try:
            return response.json()
        except ValueError:
            return {}

    def _matching_report(
        self,
        reports: list[dict[str, Any]],
        begin: datetime,
        end: datetime,
        report_id: str | None = None,
    ) -> dict[str, Any] | None:
        if report_id:
            return next((report for report in reports if str(report.get("id") or "") == report_id), None)
        matching = []
        for report in reports:
            report_begin = _parse_report_date(report.get("begin_date"))
            report_end = _parse_report_date(report.get("end_date"))
            if report_begin and report_end and abs((report_begin - begin).total_seconds()) < 1 and abs((report_end - end).total_seconds()) < 1:
                matching.append(report)
        if not matching:
            return None
        return sorted(matching, key=lambda item: str(item.get("date_created") or item.get("generation_date") or ""), reverse=True)[0]

    def _log_request(self, method: str, url: str, payload: dict[str, Any] | None) -> None:
        if not self.debug_http:
            return
        logger.warning(
            "Mercado Pago HTTP request %s %s headers=%s body=%s",
            method,
            url,
            _safe_headers(self.headers),
            _truncate_text(json.dumps(payload, ensure_ascii=True, sort_keys=True) if payload is not None else "", self.debug_http_max_chars),
        )

    def _log_response(self, method: str, url: str, response: httpx.Response) -> None:
        if not self.debug_http:
            return
        logger.warning(
            "Mercado Pago HTTP response %s %s status=%s content_type=%s body=%s",
            method,
            url,
            response.status_code,
            response.headers.get("content-type", ""),
            _response_text(response, self.debug_http_max_chars),
        )


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


async def enrich_movements(client: MercadoPagoClient, movements: list[MercadoPagoMovement]) -> list[MercadoPagoMovement]:
    payment_cache: dict[str, dict[str, Any] | None] = {}
    enriched: list[MercadoPagoMovement] = []
    for movement in movements:
        payment_ids = _payment_lookup_ids(movement.raw)
        if not payment_ids:
            enriched.append(movement)
            continue
        description = None
        merchant_key = None
        collector_id = None
        store_id = None
        for payment_id in payment_ids:
            if payment_id not in payment_cache:
                payment_cache[payment_id] = await client.get_payment(payment_id)
            payment = payment_cache[payment_id]
            candidate_key, candidate_collector, candidate_store = _merchant_identity_from_payment(payment)
            description = _description_from_payment(payment, movement.raw) or description
            merchant_key = candidate_key or merchant_key
            collector_id = candidate_collector or collector_id
            store_id = candidate_store or store_id
            if description or merchant_key:
                break
        enriched.append(
            replace(
                movement,
                description=description or movement.description,
                merchant_key=merchant_key,
                collector_id=collector_id,
                store_id=store_id,
            )
        )
    return enriched


def _merchant_identity_from_payment(payment: dict[str, Any] | None) -> tuple[str | None, str | None, str | None]:
    if not payment:
        return None, None, None
    collector_id = _text_path(payment, "collector", "id")
    store_id = _text_path(payment, "store_id")
    if collector_id:
        return f"collector:{collector_id}", collector_id, store_id or None
    if store_id:
        return f"store:{store_id}", None, store_id
    return None, None, None


async def sync_integration(
    db: Session,
    integration: MercadoPagoIntegration,
    *,
    client: MercadoPagoClient,
    overlap_days: int = 3,
    poll_interval_seconds: float = 10.0,
    poll_timeout_seconds: float = 180.0,
    now: datetime | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    advance_cursor: bool = True,
) -> MercadoPagoSyncResult:
    sync_started_at = now or datetime.utcnow()
    begin, end = (
        _explicit_sync_window(start_date, end_date, sync_started_at)
        if start_date or end_date
        else _sync_window(integration.last_sync_at, overlap_days, sync_started_at)
    )
    integration.last_sync_status = "running"
    integration.last_sync_started_at = _naive_utc(sync_started_at)
    integration.last_sync_begin_date = _naive_utc(begin)
    integration.last_sync_end_date = _naive_utc(end)
    integration.last_sync_error = None
    fetched = await fetch_mercadopago_report(
        client,
        integration.mp_user_id,
        begin,
        end,
        poll_interval_seconds=poll_interval_seconds,
        poll_timeout_seconds=poll_timeout_seconds,
    )
    result = import_movements(db, integration, fetched.movements, fetched.report.file_name)
    result = MercadoPagoSyncResult(
        batch_id=result.batch_id,
        report_file_name=result.report_file_name,
        imported=result.imported,
        ignored=result.ignored,
        duplicates=result.duplicates,
        begin_date=_utc_iso(begin),
        end_date=_utc_iso(end),
    )
    if advance_cursor:
        integration.last_sync_at = sync_started_at
    integration.last_sync_status = "ok"
    integration.last_sync_error = None
    integration.last_report_file_name = fetched.report.file_name
    integration.last_sync_completed_at = datetime.utcnow()
    integration.last_sync_imported = result.imported
    integration.last_sync_ignored = result.ignored
    integration.last_sync_duplicates = result.duplicates
    db.commit()
    return result


async def fetch_mercadopago_report(
    client: MercadoPagoClient,
    mp_user_id: str | None,
    begin: datetime,
    end: datetime,
    *,
    poll_interval_seconds: float,
    poll_timeout_seconds: float,
) -> MercadoPagoFetchedReport:
    await client.ensure_report_config(mp_user_id)
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
    movements = await enrich_movements(client, parse_report_csv(content))
    return MercadoPagoFetchedReport(report=report, movements=movements)


def claim_mercadopago_sync(db: Session, integration_id: int) -> bool:
    now = datetime.utcnow()
    result = db.execute(
        update(MercadoPagoIntegration)
        .where(
            MercadoPagoIntegration.id == integration_id,
            or_(MercadoPagoIntegration.last_sync_status.is_(None), MercadoPagoIntegration.last_sync_status != "running"),
        )
        .values(
            last_sync_status="running",
            last_sync_error=None,
            last_sync_started_at=now,
            last_sync_completed_at=None,
            last_sync_imported=None,
            last_sync_ignored=None,
            last_sync_duplicates=None,
            updated_at=now,
        )
    )
    db.commit()
    return result.rowcount == 1


def recover_interrupted_mercadopago_syncs(db: Session) -> int:
    now = datetime.utcnow()
    result = db.execute(
        update(MercadoPagoIntegration)
        .where(MercadoPagoIntegration.last_sync_status == "running")
        .values(
            last_sync_status="error",
            last_sync_error="La sincronizacion fue interrumpida por un reinicio del servidor",
            last_sync_completed_at=now,
            updated_at=now,
        )
    )
    db.commit()
    return result.rowcount


async def execute_mercadopago_sync_job(
    session_factory: sessionmaker[Session],
    integration_id: int,
    *,
    api_base_url: str,
    identity_base_url: str,
    overlap_days: int,
    poll_interval_seconds: float,
    poll_timeout_seconds: float,
    start_date: date | None = None,
    end_date: date | None = None,
    advance_cursor: bool = True,
    debug_http: bool = False,
    debug_http_max_chars: int = 12000,
) -> None:
    try:
        with session_factory() as db:
            integration = db.get(MercadoPagoIntegration, integration_id)
            if integration is None:
                return
            token = integration.access_token
            mp_user_id = integration.mp_user_id
            last_sync_at = integration.last_sync_at
        sync_started_at = datetime.utcnow()
        begin, end = (
            _explicit_sync_window(start_date, end_date, sync_started_at)
            if start_date or end_date
            else _sync_window(last_sync_at, overlap_days, sync_started_at)
        )
        with session_factory() as db:
            integration = db.get(MercadoPagoIntegration, integration_id)
            if integration is None:
                return
            integration.last_sync_begin_date = _naive_utc(begin)
            integration.last_sync_end_date = _naive_utc(end)
            db.commit()
        client = MercadoPagoClient(
            token,
            api_base_url=api_base_url,
            identity_base_url=identity_base_url,
            debug_http=debug_http,
            debug_http_max_chars=debug_http_max_chars,
        )
        fetched = await fetch_mercadopago_report(
            client,
            mp_user_id,
            begin,
            end,
            poll_interval_seconds=poll_interval_seconds,
            poll_timeout_seconds=poll_timeout_seconds,
        )
        with session_factory() as db:
            integration = db.get(MercadoPagoIntegration, integration_id)
            if integration is None:
                return
            result = import_movements(db, integration, fetched.movements, fetched.report.file_name)
            if advance_cursor:
                integration.last_sync_at = sync_started_at
            integration.last_sync_status = "ok"
            integration.last_sync_error = None
            integration.last_report_file_name = fetched.report.file_name
            integration.last_sync_completed_at = datetime.utcnow()
            integration.last_sync_imported = result.imported
            integration.last_sync_ignored = result.ignored
            integration.last_sync_duplicates = result.duplicates
            integration.updated_at = datetime.utcnow()
            db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("mercadopago_sync_job_failed integration_id=%s", integration_id)
        with session_factory() as db:
            integration = db.get(MercadoPagoIntegration, integration_id)
            if integration is not None:
                integration.last_sync_status = "error"
                integration.last_sync_error = str(exc)[:1000]
                integration.last_sync_completed_at = datetime.utcnow()
                integration.updated_at = datetime.utcnow()
                db.commit()


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
            select(ImportLine).where(
                ImportLine.home_group_id == integration.home_group_id,
                ImportLine.fingerprint == fingerprint,
            )
        )
        if existing is not None:
            _backfill_mercadopago_identity(existing, movement)
            _refresh_existing_description(db, existing, movement.description)
            if _should_reimport_existing_line(db, existing, movement):
                db.delete(existing)
                db.flush()
            else:
                duplicates += 1
                continue

        rule = find_mercadopago_rule(db, integration.home_group_id, movement.merchant_key)
        description = rule.description if rule and rule.description else movement.description
        category_id, subcategory_id, recurring, shared = _suggest_movement(db, integration.home_group_id, description)
        if rule and rule.has_category_override:
            category_id, subcategory_id, recurring = rule.category_id, rule.subcategory_id, rule.is_recurring
        if rule and rule.has_shared_override:
            shared = rule.is_shared
        line = ImportLine(
            import_batch_id=batch.id,
            home_group_id=integration.home_group_id,
            date=movement.date,
            description=description,
            cardholder_name=None,
            coupon=None,
            kind=movement.kind,
            currency=movement.currency,
            original_amount=movement.amount,
            suggested_category_id=category_id,
            suggested_subcategory_id=subcategory_id,
            suggested_recurring=recurring,
            suggested_shared=shared,
            notes=movement.ignored_reason,
            status="ignored" if movement.ignored_reason else "committed",
            fingerprint=fingerprint,
            raw_text=json.dumps(movement.raw, ensure_ascii=True, sort_keys=True),
            mercadopago_merchant_key=movement.merchant_key,
            mercadopago_collector_id=movement.collector_id,
            mercadopago_store_id=movement.store_id,
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
    debug_http: bool = False,
    debug_http_max_chars: int = 12000,
) -> None:
    while True:
        await asyncio.sleep(_seconds_until_next_hour(hour_argentina))
        with session_factory() as db:
            integration_ids = list(db.scalars(select(MercadoPagoIntegration.id).where(MercadoPagoIntegration.enabled.is_(True))))
        for integration_id in integration_ids:
            with session_factory() as db:
                if not claim_mercadopago_sync(db, integration_id):
                    continue
            await execute_mercadopago_sync_job(
                session_factory,
                integration_id,
                api_base_url=api_base_url,
                identity_base_url=identity_base_url,
                overlap_days=overlap_days,
                poll_interval_seconds=poll_interval_seconds,
                poll_timeout_seconds=poll_timeout_seconds,
                debug_http=debug_http,
                debug_http_max_chars=debug_http_max_chars,
            )


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

    fingerprint_description = _legacy_description(row)
    external_id = hashlib.sha256(
        "|".join([raw_external, movement_date.isoformat(), str(amount), transaction_type, fingerprint_description]).encode("utf-8")
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
        notes=None,
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
        is_shared=line.suggested_shared,
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


def _refresh_existing_description(db: Session, line: ImportLine, description: str) -> None:
    if not _should_replace_existing_description(line.description, description):
        return
    line.description = description
    expense = db.scalar(select(Expense).where(Expense.import_line_id == line.id))
    if expense is not None and _should_replace_existing_description(expense.description, description):
        expense.description = description
    earning = db.scalar(select(Earning).where(Earning.import_line_id == line.id))
    if earning is not None and _should_replace_existing_description(earning.description, description):
        earning.description = description


def _backfill_mercadopago_identity(line: ImportLine, movement: MercadoPagoMovement) -> None:
    if not line.mercadopago_merchant_key and movement.merchant_key:
        line.mercadopago_merchant_key = movement.merchant_key
    if not line.mercadopago_collector_id and movement.collector_id:
        line.mercadopago_collector_id = movement.collector_id
    if not line.mercadopago_store_id and movement.store_id:
        line.mercadopago_store_id = movement.store_id


def _should_reimport_existing_line(db: Session, line: ImportLine, movement: MercadoPagoMovement) -> bool:
    if movement.ignored_reason or line.status != "committed":
        return False
    has_expense = db.scalar(select(Expense.id).where(Expense.import_line_id == line.id)) is not None
    if has_expense:
        return False
    has_earning = db.scalar(select(Earning.id).where(Earning.import_line_id == line.id)) is not None
    return not has_earning


def _should_replace_existing_description(current: str | None, candidate: str) -> bool:
    if not candidate or not current or _same_text(current, candidate):
        return False
    normalized = current.strip().upper()
    return (
        _looks_like_technical_reference(current)
        or normalized
        in {
            "PAYOUTS",
            "PAYOUT",
            "SETTLEMENT",
            "MERCADO PAGO",
            "PAGO CON DINERO DISPONIBLE",
            "PAGO EN TIENDA FISICA",
            "COMPRA",
            "INGRESO DE MERCADO PAGO",
        }
        or "AVAILABLE_MONEY" in normalized
        or "ACCOUNT_MONEY" in normalized
    )


def _suggest_movement(db: Session, home_group_id: int, description: str) -> tuple[int | None, int | None, bool, bool]:
    learned = find_learned_suggestion(db, home_group_id, description)
    if learned and learned.category_id is not None:
        category_name = db.scalar(select(Category.name).where(Category.id == learned.category_id))
        return (
            learned.category_id,
            learned.subcategory_id,
            learned.is_recurring or should_suggest_recurring(db, home_group_id, description, learned.category_id),
            learned.is_shared if learned.has_shared_override else suggest_shared(description, category_name),
        )
    categories = {category.name: category.id for category in db.scalars(select(Category).where(Category.home_group_id == home_group_id))}
    subcategories = {
        (subcategory.category_id, subcategory.name.upper()): subcategory.id
        for subcategory in db.scalars(select(Subcategory).where(Subcategory.home_group_id == home_group_id))
    }
    suggestion = suggest_category(description)
    category_id = categories.get(suggestion.name) if suggestion else None
    return (
        category_id,
        _suggest_subcategory_id(description, category_id, subcategories),
        should_suggest_recurring(db, home_group_id, description, category_id),
        learned.is_shared if learned and learned.has_shared_override else suggest_shared(description, suggestion.name if suggestion else None),
    )


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


def _payment_lookup_ids(row: dict[str, str]) -> list[str]:
    transaction_type = _first(row, "TRANSACTION_TYPE", "MOVEMENT_TYPE", "TYPE").upper()
    amount = _parse_decimal(_first(row, "REAL_AMOUNT", "SETTLEMENT_NET_AMOUNT", "TRANSACTION_AMOUNT"))
    is_payment_like = _contains_any(transaction_type, PURCHASE_TOKENS) or transaction_type == "SETTLEMENT"
    if not is_payment_like or amount is None or amount >= 0:
        return []

    lookup_ids: list[str] = []
    for key in ("SOURCE_ID", "PAYMENT_ID", "ORDER_ID"):
        value = _first(row, key)
        if value and value.isdigit() and value not in lookup_ids:
            lookup_ids.append(value)
    return lookup_ids


def _description(row: dict[str, str]) -> str:
    explicit = _first(row, "SALE_DETAIL", "DESCRIPTION", "TRANSACTION_DESCRIPTION")
    if explicit:
        return explicit[:240]
    external_reference = _first(row, "EXTERNAL_REFERENCE")
    if external_reference and not _looks_like_technical_reference(external_reference):
        return external_reference[:240]
    operation_label = _mercadopago_operation_label(row)
    if operation_label:
        return operation_label
    return "Mercado Pago"


def _legacy_description(row: dict[str, str]) -> str:
    pieces = [
        _first(row, "DESCRIPTION", "TRANSACTION_DESCRIPTION", "EXTERNAL_REFERENCE"),
        _first(row, "PAYMENT_METHOD"),
        _first(row, "TRANSACTION_TYPE"),
    ]
    return " - ".join(dict.fromkeys(piece for piece in pieces if piece))[:240] or "Mercado Pago"


def _mercadopago_operation_label(row: dict[str, str]) -> str:
    external_reference = _first(row, "EXTERNAL_REFERENCE").upper()
    transaction_type = _first(row, "TRANSACTION_TYPE", "MOVEMENT_TYPE", "TYPE").upper()
    payment_method_type = _first(row, "PAYMENT_METHOD_TYPE", "PAYMENT_METHOD").lower()
    amount = _parse_decimal(_first(row, "REAL_AMOUNT", "SETTLEMENT_NET_AMOUNT", "TRANSACTION_AMOUNT"))
    sale_detail = _first(row, "SALE_DETAIL")
    if sale_detail and not _looks_like_technical_reference(sale_detail):
        return sale_detail[:240]
    if external_reference.startswith("INSTORE-"):
        return "Pago en tienda fisica"
    if _contains_any(transaction_type, ("PAYOUT", "PAYOUTS", "WITHDRAWAL")):
        return "Transferencia enviada"
    if amount is not None and amount > 0:
        return "Ingreso de Mercado Pago"
    if transaction_type == "SETTLEMENT" and amount is not None and amount < 0:
        return "Compra"
    if payment_method_type in {"account_money", "available_money"}:
        return "Pago con dinero disponible"
    return transaction_type.title() if transaction_type else ""


def _mercadopago_operation_note(row: dict[str, str]) -> str | None:
    label = _mercadopago_operation_label(row)
    return f"Tipo Mercado Pago: {label}" if label else None


def _description_from_payment(payment: dict[str, Any] | None, row: dict[str, str]) -> str | None:
    if not payment:
        return None
    candidates = [
        _text_path(payment, "description"),
        _text_path(payment, "statement_descriptor"),
        _text_path(payment, "point_of_interaction", "transaction_data", "store_name"),
        _merchant_from_idempotency_key(_text_path(payment, "idempotency_key")),
        _text_path(payment, "point_of_interaction", "business_info", "branch"),
        _text_path(payment, "point_of_interaction", "business_info", "name"),
        _text_path(payment, "additional_info", "items", 0, "title"),
        _person_or_business_name(payment.get("collector")),
        _text_path(payment, "collector", "nickname"),
        _text_path(payment, "collector", "email"),
        _text_path(payment, "merchant_order", "external_reference"),
        _text_path(payment, "external_reference"),
    ]
    fallback = _description(row)
    for candidate in candidates:
        cleaned = _clean_description_candidate(candidate)
        if cleaned and not _same_text(cleaned, fallback):
            return cleaned[:240]
    return None


def _merchant_from_idempotency_key(value: str) -> str:
    match = re.search(r"PostPay_([^_]+?)(?:-account_money|\b)", value or "", flags=re.IGNORECASE)
    if not match:
        return ""
    merchant = re.sub(r"-\d.*$", "", match.group(1)).strip(" -_")
    return merchant.replace("_", " ")


def _text_path(value: Any, *path: str | int) -> str:
    current = value
    for part in path:
        if isinstance(part, int):
            if not isinstance(current, list) or len(current) <= part:
                return ""
            current = current[part]
            continue
        if not isinstance(current, dict):
            return ""
        current = current.get(part)
    return str(current).strip() if current is not None else ""


def _person_or_business_name(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    business = _text_path(value, "business_name")
    if business:
        return business
    full_name = " ".join(part for part in [_text_path(value, "first_name"), _text_path(value, "last_name")] if part)
    return full_name or _text_path(value, "nickname")


def _clean_description_candidate(value: str | None) -> str:
    cleaned = (value or "").strip()
    if not cleaned or _looks_like_technical_reference(cleaned):
        return ""
    return cleaned


def _looks_like_technical_reference(value: str) -> bool:
    cleaned = value.strip().upper()
    if not cleaned:
        return True
    if cleaned.startswith(("INSTORE-", "ABU-", "MP-", "SRC-", "ORDER-", "PAYMENT-")):
        return True
    hexish = sum(1 for char in cleaned if char.isdigit() or char in "-_")
    return len(cleaned) >= 18 and hexish / len(cleaned) > 0.45


def _same_text(left: str, right: str) -> bool:
    return left.strip().casefold() == right.strip().casefold()


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
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    end = now.astimezone(timezone.utc)
    if last_sync_at is None:
        begin_date = now.date() - timedelta(days=max(overlap_days, 7))
    else:
        begin_date = (last_sync_at.date() - timedelta(days=overlap_days))
    begin = datetime.combine(begin_date, time.min).replace(tzinfo=timezone.utc)
    return begin, end


def _explicit_sync_window(start_date: date | None, end_date: date | None, now: datetime) -> tuple[datetime, datetime]:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now_utc = now.astimezone(timezone.utc)
    requested_end_date = end_date or now_utc.date()
    requested_start_date = start_date or requested_end_date
    begin = datetime.combine(requested_start_date, time.min).replace(tzinfo=timezone.utc)
    requested_end = datetime.combine(requested_end_date, time.max).replace(tzinfo=timezone.utc)
    end = min(requested_end, now_utc)
    if begin > end:
        raise MercadoPagoError("El rango de Mercado Pago no puede terminar en el futuro")
    return begin, end


def _report_config_payload(existing: dict[str, Any] | None, mp_user_id: str | None) -> dict[str, Any]:
    prefix = str((existing or {}).get("file_name_prefix") or f"spent-analyzer-settlement-report-{mp_user_id or 'account'}")
    frequency = (existing or {}).get("frequency")
    if not isinstance(frequency, dict):
        frequency = {"hour": 0, "type": "monthly", "value": 1}
    return {
        "file_name_prefix": prefix,
        "show_fee_prevision": bool((existing or {}).get("show_fee_prevision", False)),
        "show_chargeback_cancel": bool((existing or {}).get("show_chargeback_cancel", True)),
        "include_withdraw": True,
        "coupon_detailed": bool((existing or {}).get("coupon_detailed", True)),
        "shipping_detail": bool((existing or {}).get("shipping_detail", True)),
        "refund_detailed": bool((existing or {}).get("refund_detailed", True)),
        "display_timezone": str((existing or {}).get("display_timezone") or "GMT-03"),
        "header_language": "en",
        "separator": ";",
        "frequency": frequency,
        "columns": [{"key": key} for key in MERCADOPAGO_REPORT_COLUMNS],
    }


def _report_config_needs_update(existing: dict[str, Any]) -> bool:
    columns = {str(column.get("key", "")).upper() for column in (existing.get("columns") or []) if isinstance(column, dict)}
    return (
        not set(MERCADOPAGO_REPORT_COLUMNS).issubset(columns)
        or existing.get("header_language") != "en"
        or existing.get("separator") != ";"
        or existing.get("include_withdraw") is not True
    )


def _response_error_message(response: httpx.Response) -> str:
    body = response.text.strip()
    if len(body) > 500:
        body = body[:500]
    return f"Mercado Pago devolvio HTTP {response.status_code}: {body}" if body else f"Mercado Pago devolvio HTTP {response.status_code}"


def _safe_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key: ("Bearer ***REDACTED***" if key.lower() == "authorization" else value) for key, value in headers.items()}


def _response_text(response: httpx.Response, max_chars: int) -> str:
    return _truncate_text(response.content.decode("utf-8", errors="replace"), max_chars)


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}... [truncated {len(text) - max_chars} chars]"


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _seconds_until_next_hour(hour_argentina: int) -> float:
    argentina = timezone(timedelta(hours=-3))
    now = datetime.now(argentina)
    target = now.replace(hour=hour_argentina, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return max(1.0, (target - now).total_seconds())
