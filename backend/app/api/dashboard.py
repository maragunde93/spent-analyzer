from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
import re
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_home_member
from app.database import get_db
from app.domain import Currency, ExpenseSource
from app.models import Category, Expense, FxRate, ImportBatch, ImportLine, RecurringRule, Subcategory, User
from app.schemas import DashboardSummary
from app.services.recurring import recurring_display_name, recurring_identity
from app.services.statement_period import infer_card_statement_period, parse_card_due_date

router = APIRouter(prefix="/households/{home_group_id}/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardSummary)
def dashboard(
    home_group_id: int,
    start: date | None = None,
    end: date | None = None,
    paid_by_user_id: int | None = None,
    category_ids: list[int] = Query(default=[]),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    require_home_member(home_group_id, user, db)
    category_filter_ids = category_ids if isinstance(category_ids, list) else []
    stmt = select(Expense).where(Expense.home_group_id == home_group_id)
    if start:
        stmt = stmt.where(Expense.date >= start)
    if end:
        stmt = stmt.where(Expense.date <= end)
    if paid_by_user_id:
        stmt = stmt.where(Expense.paid_by_user_id == paid_by_user_id)
    if category_filter_ids:
        stmt = stmt.where(Expense.category_id.in_(category_filter_ids))
    expenses = [expense for expense in db.scalars(stmt) if not _is_non_consumption_expense(expense)]
    category_rows = list(db.scalars(select(Category).where(Category.home_group_id == home_group_id)))
    categories = {c.id: c.name for c in category_rows}
    subcategories = {
        s.id: s.name
        for s in db.scalars(select(Subcategory).where(Subcategory.home_group_id == home_group_id))
    }
    total = sum((Decimal(e.amount_ars) for e in expenses), Decimal("0"))

    by_category: dict[str, Decimal] = {}
    by_user: dict[int, Decimal] = {}
    trend: dict[str, Decimal] = {}
    monthly_by_category: dict[str, dict[str, Decimal]] = {}
    for expense in expenses:
        category = categories.get(expense.category_id, "Sin categoria")
        by_category[category] = by_category.get(category, Decimal("0")) + Decimal(expense.amount_ars)
        by_user[expense.paid_by_user_id] = by_user.get(expense.paid_by_user_id, Decimal("0")) + Decimal(expense.amount_ars)
        month = expense.date.strftime("%Y-%m")
        trend[month] = trend.get(month, Decimal("0")) + Decimal(expense.amount_ars)
        monthly_by_category.setdefault(month, {})
        monthly_by_category[month][category] = monthly_by_category[month].get(category, Decimal("0")) + Decimal(expense.amount_ars)

    cumulative_totals: dict[str, Decimal] = {}
    cumulative_by_category = []
    for period in sorted(monthly_by_category):
        row: dict[str, Decimal | str] = {"period": period}
        for category, amount in monthly_by_category[period].items():
            cumulative_totals[category] = cumulative_totals.get(category, Decimal("0")) + amount
        for category, amount in cumulative_totals.items():
            row[category] = amount
        cumulative_by_category.append(row)

    latest_period = max((expense.date.strftime("%Y-%m") for expense in expenses), default=None)
    recent_card_scopes, card_line_scopes = _recent_card_statement_scopes(db, home_group_id, paid_by_user_id)
    recent_card_line_ids, recent_card_periods = _recent_card_statement_scope(db, home_group_id, paid_by_user_id)
    recurring_groups: dict[str, list[Expense]] = {}
    for expense in sorted(expenses, key=lambda item: (item.date, item.id)):
        if expense.is_recurring:
            category_name = categories.get(expense.category_id)
            subcategory_name = subcategories.get(expense.subcategory_id) if expense.subcategory_id else None
            group_key = f"{recurring_identity(expense, category_name, subcategory_name)}:{expense.currency.value}"
            recurring_groups.setdefault(group_key, []).append(expense)
    recurring = []
    for grouped_expenses in recurring_groups.values():
        monthly_totals: dict[str, Decimal] = {}
        monthly_ars_totals: dict[str, Decimal] = {}
        for expense in grouped_expenses:
            period = expense.date.strftime("%Y-%m")
            monthly_totals[period] = monthly_totals.get(period, Decimal("0")) + Decimal(expense.original_amount)
            monthly_ars_totals[period] = monthly_ars_totals.get(period, Decimal("0")) + Decimal(expense.amount_ars)
        positive_months = {period: amount for period, amount in monthly_totals.items() if amount > 0}
        if not positive_months:
            continue
        last_period = max(positive_months)
        positive_expenses = [expense for expense in grouped_expenses if Decimal(expense.original_amount) > 0]
        if not positive_expenses:
            continue
        latest_expense = sorted(positive_expenses, key=lambda item: (item.date, item.id))[-1]
        category_name = categories.get(latest_expense.category_id, "Sin categoria")
        subcategory_name = subcategories.get(latest_expense.subcategory_id) if latest_expense.subcategory_id else None
        is_service_group = category_name == "Servicios"
        recurring_warning = None
        has_card_expense = any(expense.source == ExpenseSource.import_pdf for expense in grouped_expenses)
        card_expenses = [expense for expense in grouped_expenses if expense.source == ExpenseSource.import_pdf]
        has_recent_global_card_expense = any(
            _is_recent_card_expense_in_scope(expense, recent_card_line_ids, recent_card_periods)
            for expense in card_expenses
        )
        has_recent_card_expense = any(
            _is_recent_card_expense(expense, recent_card_scopes, card_line_scopes)
            for expense in card_expenses
        )
        has_card_scope = any(
            _card_scope_for_expense(expense, recent_card_scopes, card_line_scopes) is not None
            for expense in card_expenses
        )
        if has_card_expense and has_card_scope:
            if not has_recent_card_expense:
                if is_service_group:
                    if not has_recent_global_card_expense and not _has_recent_non_card_expense(grouped_expenses, latest_period):
                        recurring_warning = "No se detecto pago en los ultimos 2 resumenes de tarjeta ni en gastos de debito recientes."
                else:
                    continue
            elif is_service_group and not has_recent_global_card_expense and not _has_recent_non_card_expense(grouped_expenses, latest_period):
                recurring_warning = "No se detecto pago en los ultimos 2 resumenes de tarjeta ni en gastos de debito recientes."
        elif latest_period and _month_distance(last_period, latest_period) > 1:
            if is_service_group:
                recurring_warning = "No se detecto pago reciente en los gastos cargados."
            else:
                continue
        accumulated = sum(positive_months.values(), Decimal("0"))
        monthly_average = accumulated / Decimal(len(positive_months))
        accumulated_ars = sum((amount for amount in monthly_ars_totals.values() if amount > 0), Decimal("0"))
        monthly_average_ars = accumulated_ars / Decimal(max(len(positive_months), 1))
        recurring.append(
            {
                "description": recurring_display_name(latest_expense, category_name, subcategory_name),
                "category": category_name,
                "subcategory": subcategory_name,
                "last_period": last_period,
                "last_amount": positive_months[last_period],
                "monthly_average": monthly_average,
                "expected_amount": monthly_average,
                "accumulated_amount": accumulated,
                "annualized_amount": monthly_average * Decimal("12"),
                "sort_amount_ars": monthly_average_ars,
                "currency": latest_expense.currency.value,
                "cadence": "monthly",
                "warning": recurring_warning,
                "items": [
                    {
                        "date": expense.date.isoformat(),
                        "description": expense.description,
                        "amount": expense.original_amount,
                        "amount_ars": expense.amount_ars,
                        "currency": expense.currency.value,
                    }
                    for expense in sorted(grouped_expenses, key=lambda item: (item.date, item.id))
                ],
            }
        )
    recurring.sort(key=lambda item: Decimal(item.get("sort_amount_ars", item["monthly_average"])), reverse=True)
    if not recurring and not paid_by_user_id and not category_filter_ids:
        recurring = [
            {
                "description": rule.description_pattern,
                "category": categories.get(rule.category_id, "Sin categoria") if rule.category_id else "Sin categoria",
                "subcategory": None,
                "last_period": None,
                "last_amount": rule.expected_amount or Decimal("0"),
                "monthly_average": rule.expected_amount or Decimal("0"),
                "expected_amount": rule.expected_amount,
                "accumulated_amount": rule.expected_amount or Decimal("0"),
                "annualized_amount": (rule.expected_amount or Decimal("0")) * Decimal("12"),
                "currency": rule.currency.value,
                "cadence": rule.cadence,
                "warning": None,
                "items": [],
            }
            for rule in db.scalars(select(RecurringRule).where(RecurringRule.home_group_id == home_group_id, RecurringRule.active == True))
        ]
    return DashboardSummary(
        total_ars=total,
        by_category=[{"name": name, "amount_ars": amount} for name, amount in sorted(by_category.items())],
        by_user=[{"user_id": uid, "amount_ars": amount} for uid, amount in sorted(by_user.items())],
        trend=[{"period": period, "amount_ars": amount} for period, amount in sorted(trend.items())],
        monthly_by_category=[
            {"period": period, **values}
            for period, values in sorted(monthly_by_category.items())
        ],
        cumulative_by_category=cumulative_by_category,
        card_statement_periods=_card_statement_periods(db, home_group_id, paid_by_user_id),
        recurring_preview=recurring,
        fx_rate=_dashboard_fx_rate(db, end or date.today()),
    )


def _is_non_consumption_expense(expense: Expense) -> bool:
    return expense.source == ExpenseSource.bank_import and "TITULOS" in expense.description.upper()


def _dashboard_fx_rate(db: Session, reference_date: date) -> dict:
    rate = db.scalar(
        select(FxRate)
        .where(
            FxRate.date <= reference_date,
            FxRate.from_currency == Currency.USD,
            FxRate.to_currency == Currency.ARS,
        )
        .order_by(FxRate.date.desc())
    )
    if rate is None:
        return {
            "from_currency": Currency.USD.value,
            "to_currency": Currency.ARS.value,
            "rate": Decimal("1000"),
            "source": "fallback_local",
            "date": None,
            "is_fallback": True,
        }
    return {
        "from_currency": rate.from_currency.value,
        "to_currency": rate.to_currency.value,
        "rate": rate.rate,
        "source": rate.source,
        "date": rate.date,
        "is_fallback": False,
    }


def _month_distance(older_period: str, newer_period: str) -> int:
    older_year, older_month = [int(part) for part in older_period.split("-")]
    newer_year, newer_month = [int(part) for part in newer_period.split("-")]
    return (newer_year - older_year) * 12 + newer_month - older_month


def _has_recent_non_card_expense(expenses: list[Expense], latest_period: str | None) -> bool:
    if not latest_period:
        return False
    return any(
        expense.source != ExpenseSource.import_pdf
        and Decimal(expense.original_amount) > 0
        and _month_distance(expense.date.strftime("%Y-%m"), latest_period) <= 1
        for expense in expenses
    )


CardScopeKey = tuple[int, str]
CardScope = dict[str, set[int] | set[str]]


def _recent_card_statement_scope(
    db: Session,
    home_group_id: int,
    paid_by_user_id: int | None = None,
    limit: int = 2,
) -> tuple[set[int], set[str]]:
    stmt = (
        select(ImportBatch, ImportLine)
        .join(ImportLine, ImportLine.import_batch_id == ImportBatch.id)
        .join(Expense, Expense.import_line_id == ImportLine.id)
        .where(
            ImportBatch.home_group_id == home_group_id,
            ImportBatch.source_type != "bbva_account_xls",
            Expense.home_group_id == home_group_id,
            Expense.source == ExpenseSource.import_pdf,
        )
    )
    if paid_by_user_id:
        stmt = stmt.where(Expense.paid_by_user_id == paid_by_user_id)

    rows = [
        (_card_batch_sort_key(batch), _statement_period_for_batch(batch) or line.date.strftime("%Y-%m"), line.id)
        for batch, line in db.execute(stmt)
    ]
    recent_periods: list[str] = []
    for _, period, _ in sorted(rows, key=lambda item: item[0], reverse=True):
        if period not in recent_periods:
            recent_periods.append(period)
        if len(recent_periods) == limit:
            break
    recent_period_set = set(recent_periods)
    return {line_id for _, period, line_id in rows if period in recent_period_set}, recent_period_set


def _recent_card_statement_scopes(
    db: Session,
    home_group_id: int,
    paid_by_user_id: int | None = None,
    limit: int = 2,
) -> tuple[dict[CardScopeKey, CardScope], dict[int, CardScopeKey]]:
    stmt = (
        select(ImportBatch, ImportLine, Expense.paid_by_user_id)
        .join(ImportLine, ImportLine.import_batch_id == ImportBatch.id)
        .join(Expense, Expense.import_line_id == ImportLine.id)
        .where(
            ImportBatch.home_group_id == home_group_id,
            ImportBatch.source_type != "bbva_account_xls",
            Expense.home_group_id == home_group_id,
            Expense.source == ExpenseSource.import_pdf,
        )
    )
    if paid_by_user_id:
        stmt = stmt.where(Expense.paid_by_user_id == paid_by_user_id)

    rows_by_scope: dict[CardScopeKey, list[tuple[tuple[date, datetime, int], str, int]]] = defaultdict(list)
    line_scopes: dict[int, CardScopeKey] = {}
    for batch, line, payer_id in db.execute(stmt):
        period = _statement_period_for_batch(batch) or line.date.strftime("%Y-%m")
        account_key = batch.statement_account or batch.source_type or "card"
        scope_key = (payer_id, account_key)
        line_scopes[line.id] = scope_key
        rows_by_scope[scope_key].append((_card_batch_sort_key(batch), period, line.id))

    scopes: dict[CardScopeKey, CardScope] = {}
    for scope_key, rows in rows_by_scope.items():
        recent_periods: list[str] = []
        for _, period, _ in sorted(rows, key=lambda item: item[0], reverse=True):
            if period not in recent_periods:
                recent_periods.append(period)
            if len(recent_periods) == limit:
                break
        recent_period_set = set(recent_periods)
        scopes[scope_key] = {
            "line_ids": {line_id for _, period, line_id in rows if period in recent_period_set},
            "periods": recent_period_set,
        }
    return scopes, line_scopes


def _card_scope_for_expense(
    expense: Expense,
    recent_card_scopes: dict[CardScopeKey, CardScope],
    card_line_scopes: dict[int, CardScopeKey],
) -> CardScope | None:
    if expense.import_line_id is not None:
        scope_key = card_line_scopes.get(expense.import_line_id)
        if scope_key is not None:
            return recent_card_scopes.get(scope_key)
    payer_scopes = [
        scope
        for (payer_id, _), scope in recent_card_scopes.items()
        if payer_id == expense.paid_by_user_id
    ]
    if len(payer_scopes) == 1:
        return payer_scopes[0]
    return None


def _is_recent_card_expense(
    expense: Expense,
    recent_card_scopes: dict[CardScopeKey, CardScope],
    card_line_scopes: dict[int, CardScopeKey],
) -> bool:
    scope = _card_scope_for_expense(expense, recent_card_scopes, card_line_scopes)
    if scope is None:
        return False
    line_ids = scope["line_ids"]
    periods = scope["periods"]
    return (
        expense.import_line_id is not None
        and expense.import_line_id in line_ids
    ) or expense.date.strftime("%Y-%m") in periods


def _is_recent_card_expense_in_scope(expense: Expense, line_ids: set[int], periods: set[str]) -> bool:
    return (
        expense.import_line_id is not None
        and expense.import_line_id in line_ids
    ) or expense.date.strftime("%Y-%m") in periods


def _card_statement_periods(db: Session, home_group_id: int, paid_by_user_id: int | None = None) -> list[str]:
    stmt = (
        select(ImportBatch, ImportLine, Expense.paid_by_user_id)
        .join(ImportLine, ImportLine.import_batch_id == ImportBatch.id)
        .join(Expense, Expense.import_line_id == ImportLine.id)
        .where(
            ImportBatch.home_group_id == home_group_id,
            ImportBatch.source_type != "bbva_account_xls",
            Expense.home_group_id == home_group_id,
            Expense.source == ExpenseSource.import_pdf,
        )
    )
    if paid_by_user_id:
        stmt = stmt.where(Expense.paid_by_user_id == paid_by_user_id)

    periods_by_user: dict[int, set[str]] = {}
    for batch, line, payer_id in db.execute(stmt):
        period = _statement_period_for_batch(batch) or line.date.strftime("%Y-%m")
        periods_by_user.setdefault(payer_id, set()).add(period)

    if paid_by_user_id:
        return sorted(periods_by_user.get(paid_by_user_id, set()))

    return sorted(set().union(*periods_by_user.values()) if periods_by_user else set())


def _card_batch_sort_key(batch: ImportBatch) -> tuple[date, datetime, int]:
    statement_period = _statement_period_for_batch(batch)
    if statement_period:
        year, month = [int(part) for part in statement_period.split("-")]
        return (date(year, month, 1), batch.created_at or datetime.min, batch.id)
    return (parse_card_due_date(batch.period_label) or date.min, batch.created_at or datetime.min, batch.id)


def _statement_period_for_batch(batch: ImportBatch) -> str | None:
    return batch.statement_period or infer_card_statement_period(batch.period_label)


def _parse_statement_period(period_label: str | None) -> date | None:
    return parse_card_due_date(period_label)
    if not period_label:
        return None
    match = re.search(r"(\d{2})-([A-Za-zÁÉÍÓÚáéíóú]{3})-(\d{2})", period_label)
    if not match:
        return None
    month_map = {
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
    month = month_map.get(match.group(2).lower())
    if month is None:
        return None
    return date(2000 + int(match.group(3)), month, int(match.group(1)))
