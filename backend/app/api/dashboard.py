from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_home_member
from app.database import get_db
from app.models import Category, Expense, RecurringRule, User
from app.schemas import DashboardSummary

router = APIRouter(prefix="/households/{home_group_id}/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardSummary)
def dashboard(
    home_group_id: int,
    start: date | None = None,
    end: date | None = None,
    paid_by_user_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    require_home_member(home_group_id, user, db)
    stmt = select(Expense).where(Expense.home_group_id == home_group_id)
    if start:
        stmt = stmt.where(Expense.date >= start)
    if end:
        stmt = stmt.where(Expense.date <= end)
    if paid_by_user_id:
        stmt = stmt.where(Expense.paid_by_user_id == paid_by_user_id)
    expenses = list(db.scalars(stmt))
    categories = {c.id: c.name for c in db.scalars(select(Category).where(Category.home_group_id == home_group_id))}
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

    recurring = [
        {
            "description": rule.description_pattern,
            "expected_amount": rule.expected_amount,
            "currency": rule.currency.value,
            "cadence": rule.cadence,
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
        recurring_preview=recurring,
    )
