from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_home_member
from app.database import get_db
from app.models import CashWalletEntry, User
from app.schemas import CashWalletAdjustment, CashWalletEntryCreate, CashWalletSummary
from app.services.accounting import cash_balances
from app.services.audit import log_action

router = APIRouter(prefix="/households/{home_group_id}/cash-wallet", tags=["cash"])


@router.get("", response_model=CashWalletSummary)
def get_cash_wallet(
    home_group_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CashWalletSummary:
    require_home_member(home_group_id, user, db)
    entries = list(db.scalars(select(CashWalletEntry).where(CashWalletEntry.home_group_id == home_group_id).order_by(CashWalletEntry.date.desc())))
    return CashWalletSummary(
        balances=cash_balances(entries),
        entries=[
            {
                "id": e.id,
                "user_id": e.user_id,
                "date": e.date,
                "description": e.description,
                "currency": e.currency.value,
                "amount": e.amount,
            }
            for e in entries
        ],
    )


@router.post("")
def add_cash_wallet_entry(
    home_group_id: int,
    payload: CashWalletEntryCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_home_member(home_group_id, user, db)
    entry = CashWalletEntry(home_group_id=home_group_id, **payload.model_dump())
    db.add(entry)
    db.flush()
    log_action(db, home_group_id, user.id, "cash_create", "cash_wallet_entry", entry.description, entry.id, entry.amount, entry.currency)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id}


@router.post("/adjust")
def adjust_cash_wallet_balance(
    home_group_id: int,
    payload: CashWalletAdjustment,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_home_member(home_group_id, user, db)
    entries = list(
        db.scalars(
            select(CashWalletEntry).where(
                CashWalletEntry.home_group_id == home_group_id,
                CashWalletEntry.user_id == payload.user_id,
                CashWalletEntry.currency == payload.currency,
            )
        )
    )
    current_balance = sum((entry.amount for entry in entries), payload.target_balance * 0)
    delta = payload.target_balance - current_balance
    entry = CashWalletEntry(
        home_group_id=home_group_id,
        user_id=payload.user_id,
        date=date.today(),
        description=payload.description,
        currency=payload.currency,
        amount=delta,
    )
    db.add(entry)
    db.flush()
    log_action(db, home_group_id, user.id, "cash_adjust", "cash_wallet_entry", entry.description, entry.id, delta, payload.currency)
    db.commit()
    return {"id": entry.id, "delta": delta}
