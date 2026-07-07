from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Expense, Merchant


INSTALLMENT_RE = re.compile(r"\b(?:C\.?\s*)?\d{1,2}/\d{1,2}\b", re.IGNORECASE)


@dataclass(frozen=True)
class LearnedSuggestion:
    category_id: int | None
    subcategory_id: int | None
    is_recurring: bool


def normalize_merchant_name(description: str) -> str:
    normalized = description.upper()
    normalized = INSTALLMENT_RE.sub(" ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized[:160]


def find_learned_suggestion(db: Session, home_group_id: int, description: str) -> LearnedSuggestion | None:
    normalized_name = normalize_merchant_name(description)
    if not normalized_name:
        return None
    merchant = db.scalar(
        select(Merchant).where(
            Merchant.home_group_id == home_group_id,
            Merchant.normalized_name == normalized_name,
        )
    )
    if merchant is None:
        return None
    return LearnedSuggestion(
        category_id=merchant.category_id,
        subcategory_id=merchant.subcategory_id,
        is_recurring=merchant.is_recurring,
    )


def learn_from_expense(db: Session, expense: Expense) -> None:
    normalized_name = normalize_merchant_name(expense.description)
    if not normalized_name:
        return
    merchant = db.scalar(
        select(Merchant).where(
            Merchant.home_group_id == expense.home_group_id,
            Merchant.normalized_name == normalized_name,
        )
    )
    if merchant is None:
        merchant = Merchant(
            home_group_id=expense.home_group_id,
            display_name=expense.description[:160],
            normalized_name=normalized_name,
        )
        db.add(merchant)
    merchant.display_name = expense.description[:160]
    merchant.category_id = expense.category_id
    merchant.subcategory_id = expense.subcategory_id
    merchant.is_recurring = bool(expense.is_recurring)
