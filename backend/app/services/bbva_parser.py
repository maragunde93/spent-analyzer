from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import re
from pathlib import Path

import pdfplumber

from app.domain import Currency, ImportLineKind


MONTHS = {
    "Ene": 1,
    "Feb": 2,
    "Mar": 3,
    "Abr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Ago": 8,
    "Set": 9,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dic": 12,
}

DATE_RE = re.compile(r"^(?P<day>\d{2})-(?P<month>[A-Za-zÁÉÍÓÚáéíóú]{3})-(?P<year>\d{2})\s+(?P<body>.+)$")
AMOUNT_RE = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2}")


@dataclass(frozen=True)
class ParsedStatementLine:
    date: date
    description: str
    cardholder_name: str | None
    coupon: str | None
    currency: Currency
    amount: Decimal
    kind: ImportLineKind
    raw_text: str
    fingerprint: str


@dataclass(frozen=True)
class ParsedStatement:
    account: str | None
    period_label: str | None
    lines: list[ParsedStatementLine]


def parse_argentine_decimal(value: str) -> Decimal:
    return Decimal(value.replace(".", "").replace(",", "."))


def parse_spanish_date(value: str) -> date:
    day, month, year = value.split("-")
    month_number = MONTHS[month[:3].title()]
    full_year = 2000 + int(year)
    return date(full_year, month_number, int(day))


def extract_pdf_text(path: str | Path) -> str:
    with pdfplumber.open(str(path)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def parse_bbva_visa_pdf(path: str | Path) -> ParsedStatement:
    return parse_bbva_visa_text(extract_pdf_text(path))


def parse_bbva_visa_text(text: str) -> ParsedStatement:
    account = _first_match(text, r"cuenta\s+(\d+)")
    period_label = _first_match(text, r"CIERRE ACTUAL VENCIMIENTO ACTUAL.*?\n([0-9]{2}-[A-Za-z]{3}-[0-9]{2})")
    statement_date = parse_spanish_date(period_label) if period_label else None
    lines: list[ParsedStatementLine] = []
    section = "ignore"
    cardholder_name: str | None = None
    pending_line: str | None = None
    pending_section: str | None = None
    pending_cardholder_name: str | None = None

    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not line:
            continue
        if line.startswith("Legales y avisos") or "Para más información" in line or "Tarjetas de crédito (fuera" in line:
            section = "ignore"
        if line.startswith("Sus pagos y ajustes realizados"):
            if pending_line and pending_section:
                parsed = _parse_transaction_line(pending_line, pending_section, statement_date, pending_cardholder_name)
                if parsed:
                    lines.append(parsed)
                pending_line = None
            section = "adjustments"
            cardholder_name = None
            continue
        if line.startswith("Consumos "):
            if pending_line and pending_section:
                parsed = _parse_transaction_line(pending_line, pending_section, statement_date, pending_cardholder_name)
                if parsed:
                    lines.append(parsed)
                pending_line = None
            section = "consumptions"
            cardholder_name = _normalize_cardholder_name(line.removeprefix("Consumos "))
            continue
        if section == "ignore" or line.startswith("FECHA DESCRIP"):
            continue

        if DATE_RE.match(line):
            if pending_line and pending_section:
                parsed = _parse_transaction_line(pending_line, pending_section, statement_date, pending_cardholder_name)
                if parsed:
                    lines.append(parsed)
            pending_line = line
            pending_section = section
            pending_cardholder_name = cardholder_name
        elif pending_line and _looks_like_continuation(line):
            pending_line = f"{pending_line} {line}"

    if pending_line and pending_section:
        parsed = _parse_transaction_line(pending_line, pending_section, statement_date, pending_cardholder_name)
        if parsed:
            lines.append(parsed)

    return ParsedStatement(account=account, period_label=period_label, lines=lines)


def _first_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else None


def _looks_like_continuation(line: str) -> bool:
    normalized = line.upper()
    return not any(
        marker in normalized
        for marker in [
            "SOBRE (",
            "LEGALES",
            "SALDO ACTUAL",
            "TASAS TNA",
            "TOTAL DE CUOTAS",
            "TOTAL CONSUMOS",
            "TOTAL DE CONSUMOS",
            "TOTAL USUARIO",
        ]
    )


def _parse_transaction_line(raw: str, section: str, statement_date: date | None = None, cardholder_name: str | None = None) -> ParsedStatementLine | None:
    match = DATE_RE.match(raw)
    if not match:
        return None
    tx_date = parse_spanish_date(f"{match.group('day')}-{match.group('month')}-{match.group('year')}")
    body = _strip_summary_totals(match.group("body"))
    amounts = AMOUNT_RE.findall(body)
    if not amounts:
        return None
    amount = parse_argentine_decimal(amounts[-1])
    currency = Currency.USD if re.search(r"USD|U\$S|DÓLARES", body, re.IGNORECASE) else Currency.ARS
    body_without_last_amount = body[: body.rfind(amounts[-1])].strip()
    coupon_match = re.search(r"(\d{6,})\s*$", body_without_last_amount)
    coupon = coupon_match.group(1) if coupon_match else None
    description = body_without_last_amount[: coupon_match.start()].strip() if coupon_match else body_without_last_amount
    description = re.sub(r"USD\s*" + re.escape(amounts[-1]) + r"\b", "", description, flags=re.IGNORECASE).strip()
    if statement_date and re.search(r"\bC\.\d{2}/\d{2}\b", description, flags=re.IGNORECASE):
        tx_date = statement_date
    kind = _classify_kind(description, amount, section)
    fingerprint_source = f"{tx_date.isoformat()}|{cardholder_name or ''}|{description}|{coupon or ''}|{currency.value}|{amount}"
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
    return ParsedStatementLine(
        date=tx_date,
        description=description,
        cardholder_name=cardholder_name,
        coupon=coupon,
        currency=currency,
        amount=amount,
        kind=kind,
        raw_text=raw,
        fingerprint=fingerprint,
    )


def _normalize_cardholder_name(value: str) -> str | None:
    name = " ".join(value.split()).strip(":- ")
    return name[:160] if name else None


def _strip_summary_totals(body: str) -> str:
    return re.split(r"\bTOTAL\s+(?:DE\s+)?CONSUMOS\b", body, maxsplit=1, flags=re.IGNORECASE)[0].strip()


def _classify_kind(description: str, amount: Decimal, section: str) -> ImportLineKind:
    normalized = description.upper()
    if normalized in {"SU PAGO EN PESOS", "SU PAGO EN USD"}:
        return ImportLineKind.previous_payment
    if _is_tax_description(normalized):
        return ImportLineKind.tax
    if "DEV COMISION CTA PWORLD" in normalized or "COMISION" in normalized:
        return ImportLineKind.fee
    if "PAGO" in normalized:
        return ImportLineKind.payment
    if normalized.startswith("CR.") or normalized.startswith("DEV ") or amount < 0:
        return ImportLineKind.refund
    if section == "adjustments":
        return ImportLineKind.adjustment
    return ImportLineKind.purchase


def _is_tax_description(normalized: str) -> bool:
    return any(
        token in normalized
        for token in [
            "CR IVA $ 21",
            "DB IVA $ 21",
            "IIBB PERCEP-CABA",
            "IVA RG",
            "DB.RG",
            "CR.RG",
            "RG 5617",
        ]
    )
