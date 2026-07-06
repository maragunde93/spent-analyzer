from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re
import unicodedata

import xlrd

from app.domain import Currency, ImportLineKind


@dataclass
class ParsedAccountLine:
    date: date
    description: str
    kind: ImportLineKind
    currency: Currency
    amount: Decimal
    balance: Decimal | None
    fingerprint: str
    raw_text: str


@dataclass
class ParsedAccountStatement:
    account: str | None
    period_label: str | None
    currency: Currency
    lines: list[ParsedAccountLine]


def parse_bbva_account_xls(path: str) -> ParsedAccountStatement:
    workbook = xlrd.open_workbook(path)
    sheet = workbook.sheet_by_index(0)
    rows = [[sheet.cell_value(row, col) for col in range(sheet.ncols)] for row in range(sheet.nrows)]
    account = _find_account(rows)
    currency = _detect_currency(rows)
    header = _find_header(rows)
    if header is None:
        raise ValueError("No se encontraron columnas Fecha/Concepto/Importe/Saldo")
    header_index, columns = header

    lines: list[ParsedAccountLine] = []
    for raw_row in rows[header_index + 1 :]:
        row = [_clean_cell(value) for value in raw_row]
        if not any(row):
            continue
        parsed_date = _parse_date(row[columns["fecha"]] if len(row) > columns["fecha"] else "")
        amount = _parse_amount(row[columns["importe"]] if len(row) > columns["importe"] else "")
        if parsed_date is None or amount is None:
            continue
        description = row[columns["concepto"]].strip() or "Movimiento sin descripcion"
        balance_index = columns.get("saldo")
        balance = _parse_amount(row[balance_index] if balance_index is not None and len(row) > balance_index else "")
        kind = _classify(description, amount)
        raw_text = " | ".join(part for part in row if part)
        fingerprint = sha256(f"{parsed_date}|{description}|{currency.value}|{amount}".encode()).hexdigest()[:32]
        lines.append(
            ParsedAccountLine(
                date=parsed_date,
                description=description,
                kind=kind,
                currency=currency,
                amount=amount,
                balance=balance,
                fingerprint=fingerprint,
                raw_text=raw_text,
            )
        )
    period_label = _period_label(lines)
    return ParsedAccountStatement(account=account, period_label=period_label, currency=currency, lines=lines)


def _find_header(rows: list[list[object]]) -> tuple[int, dict[str, int]] | None:
    for index, row in enumerate(rows):
        normalized = [_normalize(_clean_cell(value)) for value in row]
        if {"fecha", "concepto", "importe"}.issubset(set(normalized)):
            return index, {name: normalized.index(name) for name in ("fecha", "concepto", "importe", "saldo") if name in normalized}
    return None


def _find_account(rows: list[list[object]]) -> str | None:
    for row in rows[:12]:
        for value in row:
            text = _clean_cell(value)
            if re.search(r"\d{3,}-\d+/\d+", text):
                return text
    return None


def _detect_currency(rows: list[list[object]]) -> Currency:
    joined = " ".join(_clean_cell(value) for row in rows[:12] for value in row)
    normalized = _normalize(joined)
    return Currency.USD if "usd" in normalized or "dolares" in normalized or "u$s" in joined.lower() else Currency.ARS


def _period_label(lines: list[ParsedAccountLine]) -> str | None:
    if not lines:
        return None
    dates = sorted(line.date for line in lines)
    return f"{dates[0].isoformat()} a {dates[-1].isoformat()}"


def _clean_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _parse_date(value: object) -> date | None:
    text = _clean_cell(value)
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def _parse_amount(value: object) -> Decimal | None:
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    text = _clean_cell(value)
    if not text:
        return None
    text = text.replace("$", "").replace("ARS", "").replace("USD", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _classify(description: str, amount: Decimal) -> ImportLineKind:
    text = _normalize(description)
    if "cuenta visa" in text or "cuenta master" in text or "cuenta mastercard" in text:
        return ImportLineKind.card_payment
    if "pago de tarjeta" in text:
        return ImportLineKind.card_payment
    if "pago de servicios tarjeta" in text:
        return ImportLineKind.debit_purchase
    if any(token in text for token in ("extraccion", "cajero", "atm")):
        return ImportLineKind.cash_withdrawal
    if any(token in text for token in ("sueldo", "salario", "haberes", "acreditacion")):
        return ImportLineKind.income
    if "intereses ganados" in text or "interes ganado" in text:
        return ImportLineKind.income
    if "transferencia" in text:
        return ImportLineKind.income if amount > 0 else ImportLineKind.transfer
    return ImportLineKind.income if amount > 0 else ImportLineKind.debit_purchase


def _normalize(value: str) -> str:
    without_accents = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", without_accents.lower()).strip()
