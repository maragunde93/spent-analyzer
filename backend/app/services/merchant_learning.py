from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import ExpenseSource
from app.models import Expense, ImportLine, Merchant, MercadoPagoMerchantRule


INSTALLMENT_RE = re.compile(r"\b(?:C\.?\s*)?\d{1,2}/\d{1,2}\b", re.IGNORECASE)


@dataclass(frozen=True)
class LearnedSuggestion:
    category_id: int | None
    subcategory_id: int | None
    is_recurring: bool
    has_shared_override: bool
    is_shared: bool


@dataclass(frozen=True)
class MercadoPagoLearnedRule:
    description: str | None
    has_category_override: bool
    category_id: int | None
    subcategory_id: int | None
    is_recurring: bool
    has_shared_override: bool
    is_shared: bool


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
        has_shared_override=merchant.has_shared_override,
        is_shared=merchant.is_shared,
    )


def learn_from_expense(db: Session, expense: Expense, *, learn_shared_scope: bool = True) -> None:
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
    if learn_shared_scope:
        merchant.has_shared_override = True
        merchant.is_shared = bool(expense.is_shared)


def find_mercadopago_rule(db: Session, home_group_id: int, merchant_key: str | None) -> MercadoPagoLearnedRule | None:
    if not merchant_key:
        return None
    rule = db.scalar(
        select(MercadoPagoMerchantRule).where(
            MercadoPagoMerchantRule.home_group_id == home_group_id,
            MercadoPagoMerchantRule.merchant_key == merchant_key,
        )
    )
    if rule is None:
        return None
    return MercadoPagoLearnedRule(
        description=rule.learned_description,
        has_category_override=rule.has_category_override,
        category_id=rule.category_id,
        subcategory_id=rule.subcategory_id,
        is_recurring=rule.is_recurring,
        has_shared_override=rule.has_shared_override,
        is_shared=rule.is_shared,
    )


def learn_mercadopago_expense(
    db: Session,
    expense: Expense,
    *,
    description_changed: bool,
    categorization_submitted: bool,
    shared_scope_submitted: bool,
) -> None:
    if expense.source != ExpenseSource.mercadopago or expense.import_line_id is None:
        return
    line = db.get(ImportLine, expense.import_line_id)
    if line is None or not line.mercadopago_merchant_key:
        return
    rule = db.scalar(
        select(MercadoPagoMerchantRule).where(
            MercadoPagoMerchantRule.home_group_id == expense.home_group_id,
            MercadoPagoMerchantRule.merchant_key == line.mercadopago_merchant_key,
        )
    )
    if rule is None:
        rule = MercadoPagoMerchantRule(
            home_group_id=expense.home_group_id,
            merchant_key=line.mercadopago_merchant_key,
            collector_id=line.mercadopago_collector_id,
            store_id=line.mercadopago_store_id,
        )
        db.add(rule)
    if description_changed:
        rule.learned_description = expense.description[:240]
    if categorization_submitted:
        rule.has_category_override = True
        rule.category_id = expense.category_id
        rule.subcategory_id = expense.subcategory_id
        rule.is_recurring = bool(expense.is_recurring)
    if shared_scope_submitted:
        rule.has_shared_override = True
        rule.is_shared = bool(expense.is_shared)
