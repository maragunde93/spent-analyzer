from decimal import Decimal
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import Currency
from app.models import Category, Expense, RecurringRule


def recurring_pattern(description: str) -> str:
    normalized = re.sub(r"\s+", " ", description.upper()).strip()
    normalized = re.sub(r"\b\d{4,}\b", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized[:160] or description[:160]


def recurring_group_key(description: str) -> str:
    normalized = recurring_pattern(description)
    normalized = re.sub(r"^(DEV|CR|DB)\s+", "", normalized)
    normalized = normalized.replace(".", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized[:160] or recurring_pattern(description)


def recurring_identity(expense: Expense, category_name: str | None = None, subcategory_name: str | None = None) -> str:
    if expense.subcategory_id and subcategory_name:
        return f"subcategory:{expense.subcategory_id}"
    return f"description:{recurring_group_key(expense.description)}"


def recurring_display_name(expense: Expense, category_name: str | None = None, subcategory_name: str | None = None) -> str:
    if subcategory_name:
        if category_name == "Auto" and subcategory_name.lower() == "seguro":
            return "Seguro Auto"
        return subcategory_name
    return recurring_group_key(expense.description).title()


def should_suggest_recurring(db: Session, home_group_id: int, description: str, category_id: int | None) -> bool:
    category_name = None
    if category_id is not None:
        category_name = db.scalar(select(Category.name).where(Category.id == category_id, Category.home_group_id == home_group_id))
    if category_name in ("Suscripciones", "Servicios"):
        return True

    pattern = recurring_pattern(description)
    return db.scalar(
        select(RecurringRule.id).where(
            RecurringRule.home_group_id == home_group_id,
            RecurringRule.active == True,
            RecurringRule.description_pattern == pattern,
        )
    ) is not None


def sync_recurring_rule(db: Session, expense: Expense) -> None:
    pattern = recurring_pattern(expense.description)
    existing = db.scalar(
        select(RecurringRule).where(
            RecurringRule.home_group_id == expense.home_group_id,
            RecurringRule.description_pattern == pattern,
        )
    )
    if not expense.is_recurring:
        if existing is not None:
            existing.active = False
        return

    if existing is None:
        existing = RecurringRule(
            home_group_id=expense.home_group_id,
            description_pattern=pattern,
        )
        db.add(existing)
    existing.category_id = expense.category_id
    existing.currency = expense.currency if isinstance(expense.currency, Currency) else Currency(expense.currency)
    existing.expected_amount = Decimal(expense.original_amount)
    existing.cadence = "monthly"
    existing.active = True
