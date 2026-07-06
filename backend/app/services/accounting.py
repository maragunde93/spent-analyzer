from collections import defaultdict
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import Currency, ExpenseSource
from app.models import CashWalletEntry, Expense, FxRate


def amount_to_ars(db: Session, amount: Decimal, currency: Currency, expense_date: date) -> Decimal:
    if currency == Currency.ARS:
        return amount
    rate = db.scalar(
        select(FxRate.rate)
        .where(FxRate.date <= expense_date, FxRate.from_currency == Currency.USD, FxRate.to_currency == Currency.ARS)
        .order_by(FxRate.date.desc())
    )
    if rate is None:
        rate = Decimal("1000")
    return (amount * Decimal(rate)).quantize(Decimal("0.01"))


def add_cash_expense_entry(db: Session, expense: Expense) -> None:
    if expense.source != ExpenseSource.cash:
        return
    db.add(
        CashWalletEntry(
            home_group_id=expense.home_group_id,
            user_id=expense.paid_by_user_id,
            date=expense.date,
            description=f"Gasto en efectivo: {expense.description}",
            currency=expense.currency,
            amount=-expense.original_amount,
            expense_id=expense.id,
        )
    )


def cash_balances(entries: list[CashWalletEntry]) -> list[dict]:
    balances: dict[tuple[int, Currency], Decimal] = defaultdict(Decimal)
    for entry in entries:
        balances[(entry.user_id, entry.currency)] += Decimal(entry.amount)
    return [
        {"user_id": user_id, "currency": currency.value, "balance": amount}
        for (user_id, currency), amount in sorted(balances.items())
    ]
