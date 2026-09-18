from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_home_member
from app.database import get_db
from app.models import CashWalletEntry, Category, Earning, Expense, ExpenseSource, ImportLine, User
from app.schemas import ExpenseCreate, ExpenseRead, ExpenseUpdate
from app.services.accounting import add_cash_expense_entry, amount_to_ars
from app.services.audit import log_action
from app.services.categorizer import suggest_shared
from app.services.merchant_learning import find_learned_suggestion, learn_from_expense, learn_mercadopago_expense
from app.services.recurring import sync_recurring_rule

router = APIRouter(prefix="/households/{home_group_id}/expenses", tags=["expenses"])


@router.get("", response_model=list[ExpenseRead])
def list_expenses(
    home_group_id: int,
    paid_by_user_id: int | None = None,
    uploaded_by_user_id: int | None = None,
    category_id: int | None = None,
    is_shared: bool | None = None,
    start: date | None = None,
    end: date | None = None,
    search: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Expense]:
    require_home_member(home_group_id, user, db)
    stmt = select(Expense).where(Expense.home_group_id == home_group_id)
    if paid_by_user_id:
        stmt = stmt.where(Expense.paid_by_user_id == paid_by_user_id)
    if uploaded_by_user_id:
        stmt = stmt.where(Expense.uploaded_by_user_id == uploaded_by_user_id)
    if category_id:
        stmt = stmt.where(Expense.category_id == category_id)
    if is_shared is not None:
        stmt = stmt.where(Expense.is_shared.is_(is_shared))
    if start:
        stmt = stmt.where(Expense.date >= start)
    if end:
        stmt = stmt.where(Expense.date <= end)
    if search:
        stmt = stmt.outerjoin(Category, Category.id == Expense.category_id).where(
            Expense.description.ilike(f"%{search}%") | Category.name.ilike(f"%{search}%")
        )
    return list(db.scalars(stmt.order_by(Expense.date.desc(), Expense.id.desc())))


@router.post("", response_model=ExpenseRead)
def create_expense(
    home_group_id: int,
    payload: ExpenseCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Expense:
    require_home_member(home_group_id, user, db)
    amount_ars = payload.amount_ars or amount_to_ars(db, payload.original_amount, payload.currency, payload.date)
    category_name = db.scalar(select(Category.name).where(Category.id == payload.category_id, Category.home_group_id == home_group_id)) if payload.category_id else None
    learned = find_learned_suggestion(db, home_group_id, payload.description)
    initial_shared = (
        learned.is_shared
        if learned and learned.has_shared_override
        else suggest_shared(payload.description, category_name)
    )
    expense = Expense(
        home_group_id=home_group_id,
        date=payload.date,
        description=payload.description,
        category_id=payload.category_id,
        subcategory_id=payload.subcategory_id,
        paid_by_user_id=payload.paid_by_user_id,
        uploaded_by_user_id=user.id,
        source=payload.source,
        currency=payload.currency,
        original_amount=payload.original_amount,
        amount_ars=amount_ars,
        notes=payload.notes,
        is_recurring=payload.is_recurring or category_name in ("Suscripciones", "Servicios"),
        is_shared=payload.is_shared if "is_shared" in payload.model_fields_set else initial_shared,
    )
    db.add(expense)
    db.flush()
    add_cash_expense_entry(db, expense)
    learn_from_expense(db, expense)
    sync_recurring_rule(db, expense)
    log_action(
        db,
        home_group_id,
        user.id,
        "expense_create",
        "expense",
        expense.description,
        expense.id,
        expense.original_amount,
        expense.currency,
    )
    db.commit()
    db.refresh(expense)
    return expense


@router.put("/{expense_id}", response_model=ExpenseRead)
def update_expense(
    home_group_id: int,
    expense_id: int,
    payload: ExpenseUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Expense:
    require_home_member(home_group_id, user, db)
    expense = db.get(Expense, expense_id)
    if expense is None or expense.home_group_id != home_group_id:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    updates = payload.model_dump(exclude_unset=True)
    previous_description = expense.description
    for field in ["date", "description", "category_id", "subcategory_id", "paid_by_user_id", "currency", "source", "notes", "is_recurring", "is_shared"]:
        if field in updates:
            setattr(expense, field, updates[field])
    if "original_amount" in updates:
        expense.original_amount = updates["original_amount"]
    if "amount_ars" in updates and updates["amount_ars"] is not None:
        expense.amount_ars = updates["amount_ars"]
    elif "original_amount" in updates or "currency" in updates or "date" in updates:
        expense.amount_ars = amount_to_ars(db, expense.original_amount, expense.currency, expense.date)
    if "category_id" in updates and "is_recurring" not in updates:
        category_name = db.scalar(select(Category.name).where(Category.id == expense.category_id, Category.home_group_id == home_group_id)) if expense.category_id else None
        if category_name in ("Suscripciones", "Servicios"):
            expense.is_recurring = True

    db.execute(delete(CashWalletEntry).where(CashWalletEntry.expense_id == expense.id))
    db.flush()
    add_cash_expense_entry(db, expense)
    learn_from_expense(db, expense, learn_shared_scope="is_shared" in updates)
    learn_mercadopago_expense(
        db,
        expense,
        description_changed="description" in updates and expense.description != previous_description,
        categorization_submitted=bool({"category_id", "subcategory_id", "is_recurring"} & updates.keys()),
        shared_scope_submitted="is_shared" in updates,
    )
    sync_recurring_rule(db, expense)
    log_action(
        db,
        home_group_id,
        user.id,
        "expense_update",
        "expense",
        expense.description,
        expense.id,
        expense.original_amount,
        expense.currency,
    )
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/{expense_id}")
def delete_expense(
    home_group_id: int,
    expense_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_home_member(home_group_id, user, db)
    expense = db.get(Expense, expense_id)
    if expense and expense.home_group_id == home_group_id:
        deleted_import_line_id = expense.import_line_id if expense.source == ExpenseSource.mercadopago else None
        log_action(
            db,
            home_group_id,
            user.id,
            "expense_delete",
            "expense",
            expense.description,
            expense.id,
            expense.original_amount,
            expense.currency,
        )
        db.execute(delete(CashWalletEntry).where(CashWalletEntry.expense_id == expense.id))
        db.delete(expense)
        db.flush()
        if deleted_import_line_id is not None:
            still_referenced = db.scalar(select(Expense.id).where(Expense.import_line_id == deleted_import_line_id))
            still_referenced = still_referenced or db.scalar(select(Earning.id).where(Earning.import_line_id == deleted_import_line_id))
            if still_referenced is None:
                db.execute(delete(ImportLine).where(ImportLine.home_group_id == home_group_id, ImportLine.id == deleted_import_line_id))
        db.commit()
    return {"ok": True}
