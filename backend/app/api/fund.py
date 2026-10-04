from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_home_member
from app.database import get_db
from app.models import (
    FundClosureApproval,
    FundManualMovement,
    FundMonthClosure,
    FundMonthConfig,
    FundMonthShare,
    FundMpAssignment,
    FundMpOriginRule,
    FundOpeningBalance,
    Membership,
    User,
)
from app.schemas import FundConfigUpdate, FundManualMovementInput, FundMpContributionUpdate, FundOpeningBalanceUpdate
from app.services.audit import log_action
from app.services.fund import calculate_fund_summary, household_members, money, mp_activity, validate_period

router = APIRouter(prefix="/households/{home_group_id}/fund", tags=["fund"])


@router.get("/summary")
def summary(
    home_group_id: int,
    period: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_home_member(home_group_id, user, db)
    result = calculate_fund_summary(db, home_group_id, period)
    db.commit()
    return result


@router.put("/config/{period}")
def update_config(
    home_group_id: int,
    period: str,
    payload: FundConfigUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_home_member(home_group_id, user, db)
    period = validate_period(period)
    member_ids = _member_ids(db, home_group_id)
    provided_ids = [item.user_id for item in payload.shares]
    if len(provided_ids) != len(set(provided_ids)) or set(provided_ids) != member_ids:
        raise HTTPException(status_code=400, detail="Debe indicar un porcentaje para cada miembro del hogar")
    if sum((Decimal(item.percentage) for item in payload.shares), Decimal("0")) != Decimal("100"):
        raise HTTPException(status_code=400, detail="Los porcentajes deben sumar exactamente 100%")
    config = db.scalar(select(FundMonthConfig).where(FundMonthConfig.home_group_id == home_group_id, FundMonthConfig.period == period))
    if config is None:
        config = FundMonthConfig(home_group_id=home_group_id, period=period, monthly_amount=money(payload.monthly_amount), created_by_user_id=user.id)
        db.add(config)
        db.flush()
    else:
        config.monthly_amount = money(payload.monthly_amount)
        config.updated_at = datetime.utcnow()
        db.execute(delete(FundMonthShare).where(FundMonthShare.config_id == config.id))
    for share in payload.shares:
        db.add(FundMonthShare(config_id=config.id, user_id=share.user_id, percentage=share.percentage))
    log_action(db, home_group_id, user.id, "fund_config_update", "fund_month_config", f"Configuración del fondo para {period}", config.id, money(payload.monthly_amount))
    db.commit()
    return calculate_fund_summary(db, home_group_id, period, persist_stale=False)


@router.put("/opening-balance")
def update_opening_balance(
    home_group_id: int,
    payload: FundOpeningBalanceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_home_member(home_group_id, user, db)
    opening = db.scalar(select(FundOpeningBalance).where(FundOpeningBalance.home_group_id == home_group_id))
    if opening is None:
        opening = FundOpeningBalance(home_group_id=home_group_id, start_date=payload.start_date, amount=money(payload.amount), created_by_user_id=user.id)
        db.add(opening)
        db.flush()
    else:
        opening.start_date = payload.start_date
        opening.amount = money(payload.amount)
        opening.updated_at = datetime.utcnow()
    log_action(db, home_group_id, user.id, "fund_opening_balance_update", "fund_opening_balance", f"Saldo inicial del fondo desde {payload.start_date.isoformat()}", opening.id, money(payload.amount))
    db.commit()
    return {"id": opening.id, "start_date": opening.start_date.isoformat(), "amount": str(money(opening.amount))}


@router.post("/months/{period}/close")
def close_month(
    home_group_id: int,
    period: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_home_member(home_group_id, user, db)
    result = calculate_fund_summary(db, home_group_id, validate_period(period), persist_stale=False)
    if not result.get("activated"):
        raise HTTPException(status_code=400, detail="El fondo todavía no está configurado")
    closure = db.scalar(select(FundMonthClosure).where(FundMonthClosure.home_group_id == home_group_id, FundMonthClosure.period == period))
    if closure and closure.status in ("pendiente_aprobacion", "cerrado") and closure.input_hash == result["input_hash"]:
        return result
    if closure and result["status"] == "desactualizado":
        raise HTTPException(status_code=409, detail="Reabrí el cierre desactualizado antes de recalcularlo")
    obligated = {item["from_user_id"] for item in result["plan"] if Decimal(item["amount"]) > 0}
    status = "pendiente_aprobacion" if obligated else "cerrado"
    snapshot = {**result, "status": status}
    if closure is None:
        closure = FundMonthClosure(
            home_group_id=home_group_id,
            period=period,
            status=status,
            snapshot=snapshot,
            input_hash=result["input_hash"],
            agreed_closing_balance=Decimal(result["totals"]["agreed_balance"]),
            created_by_user_id=user.id,
        )
        db.add(closure)
        db.flush()
    else:
        db.execute(delete(FundClosureApproval).where(FundClosureApproval.closure_id == closure.id))
        closure.status = status
        closure.snapshot = snapshot
        closure.input_hash = result["input_hash"]
        closure.agreed_closing_balance = Decimal(result["totals"]["agreed_balance"])
        closure.updated_at = datetime.utcnow()
    log_action(db, home_group_id, user.id, "fund_month_close", "fund_month_closure", f"Cierre calculado para {period}", closure.id)
    db.commit()
    return calculate_fund_summary(db, home_group_id, period, persist_stale=False)


@router.post("/months/{period}/approve")
def approve_month(
    home_group_id: int,
    period: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_home_member(home_group_id, user, db)
    closure = db.scalar(select(FundMonthClosure).where(FundMonthClosure.home_group_id == home_group_id, FundMonthClosure.period == validate_period(period)))
    if closure is None or closure.status not in ("pendiente_aprobacion", "cerrado"):
        raise HTTPException(status_code=409, detail="Primero calculá el cierre del mes")
    outgoing = sum((Decimal(item["amount"]) for item in closure.snapshot.get("plan", []) if item["from_user_id"] == user.id), Decimal("0"))
    obligated = {item["from_user_id"] for item in closure.snapshot.get("plan", []) if Decimal(item["amount"]) > 0}
    if user.id not in obligated:
        raise HTTPException(status_code=403, detail="No tenés una obligación de salida para aprobar")
    approval = db.scalar(select(FundClosureApproval).where(FundClosureApproval.closure_id == closure.id, FundClosureApproval.user_id == user.id))
    if approval is None:
        approval = FundClosureApproval(closure_id=closure.id, user_id=user.id, amount=money(outgoing))
        db.add(approval)
        db.flush()
        log_action(db, home_group_id, user.id, "fund_month_approve", "fund_month_closure", f"Parte aprobada para {period}", closure.id, money(outgoing))
    approved_ids = set(db.scalars(select(FundClosureApproval.user_id).where(FundClosureApproval.closure_id == closure.id)))
    closure.status = "cerrado" if obligated <= approved_ids else "pendiente_aprobacion"
    closure.updated_at = datetime.utcnow()
    db.commit()
    return calculate_fund_summary(db, home_group_id, period, persist_stale=False)


@router.post("/months/{period}/reopen")
def reopen_month(
    home_group_id: int,
    period: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_home_member(home_group_id, user, db)
    closure = db.scalar(select(FundMonthClosure).where(FundMonthClosure.home_group_id == home_group_id, FundMonthClosure.period == validate_period(period)))
    if closure is None:
        raise HTTPException(status_code=404, detail="No existe un cierre para ese mes")
    db.execute(delete(FundClosureApproval).where(FundClosureApproval.closure_id == closure.id))
    closure.status = "abierto"
    closure.updated_at = datetime.utcnow()
    log_action(db, home_group_id, user.id, "fund_month_reopen", "fund_month_closure", f"Mes reabierto: {period}", closure.id)
    db.commit()
    return calculate_fund_summary(db, home_group_id, period, persist_stale=False)


@router.get("/series")
def series(home_group_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_home_member(home_group_id, user, db)
    periods = set(db.scalars(select(FundMonthConfig.period).where(FundMonthConfig.home_group_id == home_group_id)))
    periods.update(db.scalars(select(FundMonthClosure.period).where(FundMonthClosure.home_group_id == home_group_id)))
    current = date.today().strftime("%Y-%m")
    if periods:
        cursor = min(periods)
        while cursor <= current:
            periods.add(cursor)
            year, month = map(int, cursor.split("-"))
            cursor = f"{year + (month == 12):04d}-{1 if month == 12 else month + 1:02d}"
    rows = []
    for period in sorted(periods)[-24:]:
        item = calculate_fund_summary(db, home_group_id, period, persist_stale=False)
        if not item.get("activated"):
            continue
        totals = item["totals"]
        rows.append({"period": period, "configured_fund": totals["configured_fund"], "shared_expenses": totals["shared_expenses"], "surplus_or_excess": totals["surplus_or_excess"], "agreed_balance": totals["agreed_balance"], "verified_balance": totals["verified_balance"]})
    db.commit()
    return rows


@router.get("/mp-activity")
def mercado_pago_activity(home_group_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_home_member(home_group_id, user, db)
    result = mp_activity(db, home_group_id)
    db.commit()
    return result


@router.post("/manual-movements")
def create_manual_movement(home_group_id: int, payload: FundManualMovementInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_home_member(home_group_id, user, db)
    _validate_movement(db, home_group_id, payload)
    item = FundManualMovement(home_group_id=home_group_id, created_by_user_id=user.id, **payload.model_dump())
    db.add(item)
    db.flush()
    log_action(db, home_group_id, user.id, "fund_movement_create", "fund_manual_movement", payload.note or "Movimiento manual del fondo", item.id, money(payload.amount))
    db.commit()
    return {"id": item.id}


@router.put("/manual-movements/{movement_id}")
def update_manual_movement(home_group_id: int, movement_id: int, payload: FundManualMovementInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_home_member(home_group_id, user, db)
    item = _movement(db, home_group_id, movement_id)
    _validate_movement(db, home_group_id, payload)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    item.updated_at = datetime.utcnow()
    log_action(db, home_group_id, user.id, "fund_movement_update", "fund_manual_movement", payload.note or "Movimiento manual editado", item.id, money(payload.amount))
    db.commit()
    return {"id": item.id}


@router.delete("/manual-movements/{movement_id}")
def delete_manual_movement(home_group_id: int, movement_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_home_member(home_group_id, user, db)
    item = _movement(db, home_group_id, movement_id)
    log_action(db, home_group_id, user.id, "fund_movement_delete", "fund_manual_movement", item.note or "Movimiento manual eliminado", item.id, money(item.amount))
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.patch("/mp-contributions/{earning_id}")
def update_mp_contribution(home_group_id: int, earning_id: int, payload: FundMpContributionUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_home_member(home_group_id, user, db)
    if payload.classification not in ("pending", "contribution", "excluded"):
        raise HTTPException(status_code=400, detail="Clasificación inválida")
    assignment = db.scalar(select(FundMpAssignment).where(FundMpAssignment.home_group_id == home_group_id, FundMpAssignment.earning_id == earning_id))
    if assignment is None:
        raise HTTPException(status_code=404, detail="Ingreso de Mercado Pago no encontrado")
    if payload.classification == "contribution":
        if payload.contributor_user_id not in _member_ids(db, home_group_id):
            raise HTTPException(status_code=400, detail="Seleccioná un aportante del hogar")
    assignment.classification = payload.classification
    assignment.contributor_user_id = payload.contributor_user_id if payload.classification == "contribution" else None
    assignment.updated_by_user_id = user.id
    assignment.updated_at = datetime.utcnow()
    if payload.remember_origin:
        if not assignment.stable_origin_id or assignment.contributor_user_id is None:
            raise HTTPException(status_code=400, detail="No hay un identificador estable para recordar")
        rule = db.scalar(select(FundMpOriginRule).where(FundMpOriginRule.integration_id == assignment.integration_id, FundMpOriginRule.stable_origin_id == assignment.stable_origin_id))
        if rule is None:
            db.add(FundMpOriginRule(home_group_id=home_group_id, integration_id=assignment.integration_id, stable_origin_id=assignment.stable_origin_id, user_id=assignment.contributor_user_id, created_by_user_id=user.id))
        else:
            rule.user_id = assignment.contributor_user_id
    log_action(db, home_group_id, user.id, "fund_mp_assign", "fund_mp_assignment", f"Ingreso MP clasificado como {payload.classification}", assignment.id)
    db.commit()
    return {"ok": True}


@router.get("/mp-origin-rules")
def list_mp_origin_rules(home_group_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_home_member(home_group_id, user, db)
    return [{"id": item.id, "integration_id": item.integration_id, "stable_origin_id": item.stable_origin_id, "user_id": item.user_id} for item in db.scalars(select(FundMpOriginRule).where(FundMpOriginRule.home_group_id == home_group_id))]


@router.delete("/mp-origin-rules/{rule_id}")
def delete_mp_origin_rule(home_group_id: int, rule_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_home_member(home_group_id, user, db)
    rule = db.scalar(select(FundMpOriginRule).where(FundMpOriginRule.id == rule_id, FundMpOriginRule.home_group_id == home_group_id))
    if rule is None:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    db.delete(rule)
    log_action(db, home_group_id, user.id, "fund_mp_rule_delete", "fund_mp_origin_rule", "Regla de origen MP eliminada", rule.id)
    db.commit()
    return {"ok": True}


def _member_ids(db: Session, home_group_id: int) -> set[int]:
    return set(db.scalars(select(Membership.user_id).where(Membership.home_group_id == home_group_id)))


def _validate_movement(db: Session, home_group_id: int, payload: FundManualMovementInput) -> None:
    if payload.from_user_id is None and payload.to_user_id is None:
        raise HTTPException(status_code=400, detail="El movimiento debe tener un origen o destino personal")
    if payload.from_user_id is not None and payload.from_user_id == payload.to_user_id:
        raise HTTPException(status_code=400, detail="El origen y destino no pueden ser iguales")
    members = _member_ids(db, home_group_id)
    if payload.from_user_id is not None and payload.from_user_id not in members or payload.to_user_id is not None and payload.to_user_id not in members:
        raise HTTPException(status_code=400, detail="El movimiento solo puede incluir miembros del hogar")


def _movement(db: Session, home_group_id: int, movement_id: int) -> FundManualMovement:
    item = db.scalar(select(FundManualMovement).where(FundManualMovement.id == movement_id, FundManualMovement.home_group_id == home_group_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return item
