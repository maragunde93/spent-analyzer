from datetime import date, timedelta
import re


MONTH_MAP = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}


def parse_card_due_date(period_label: str | None) -> date | None:
    if not period_label:
        return None
    match = re.search(r"(\d{2})-([A-Za-z]{3})-(\d{2})", period_label)
    if not match:
        return None
    month = MONTH_MAP.get(match.group(2).lower())
    if month is None:
        return None
    return date(2000 + int(match.group(3)), month, int(match.group(1)))


def infer_card_statement_period(period_label: str | None) -> str | None:
    due_date = parse_card_due_date(period_label)
    if due_date is None:
        return None
    if due_date.day < 25:
        previous_month = date(due_date.year, due_date.month, 1) - timedelta(days=1)
        return previous_month.strftime("%Y-%m")
    return due_date.strftime("%Y-%m")


def valid_statement_period(value: str | None) -> bool:
    if value is None:
        return True
    return bool(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value))
