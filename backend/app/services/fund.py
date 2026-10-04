from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.domain import ExpenseSource
from app.models import (
    Earning,
    Expense,
    FundClosureApproval,
    FundManualMovement,
    FundMonthClosure,
    FundMonthConfig,
    FundMonthShare,
    FundMpAssignment,
    FundMpOriginRule,
    FundOpeningBalance,
    ImportBatch,
    ImportLine,
    Membership,
    MercadoPagoIntegration,
    User,
)

CENT = Decimal("0.01")
HUNDRED = Decimal("100")
PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def human_amount(value: Decimal | int | str) -> str:
    return f"{money(value):,.0f}".replace(",", ".")


def validate_period(period: str) -> str:
    if not PERIOD_RE.fullmatch(period):
        raise HTTPException(status_code=400, detail="El periodo debe tener formato YYYY-MM")
    return period


def period_for_date(value: date) -> str:
    return value.strftime("%Y-%m")


def period_end(period: str) -> date:
    year, month = map(int, validate_period(period).split("-"))
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def household_members(db: Session, home_group_id: int) -> list[tuple[Membership, User]]:
    return list(
        db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.home_group_id == home_group_id)
            .order_by(User.display_name, User.id)
        )
    )


def effective_config(db: Session, home_group_id: int, period: str) -> tuple[FundMonthConfig | None, list[FundMonthShare]]:
    config = db.scalar(
        select(FundMonthConfig)
        .where(FundMonthConfig.home_group_id == home_group_id, FundMonthConfig.period <= validate_period(period))
        .order_by(FundMonthConfig.period.desc())
    )
    if config is None:
        return None, []
    shares = list(db.scalars(select(FundMonthShare).where(FundMonthShare.config_id == config.id).order_by(FundMonthShare.user_id)))
    return config, shares


def expense_fund_context(
    db: Session, expenses: list[Expense]
) -> dict[int, tuple[ImportLine | None, ImportBatch | None, MercadoPagoIntegration | None]]:
    line_ids = [item.import_line_id for item in expenses if item.import_line_id]
    lines = {item.id: item for item in db.scalars(select(ImportLine).where(ImportLine.id.in_(line_ids)))} if line_ids else {}
    batch_ids = {line.import_batch_id for line in lines.values()}
    batches = {item.id: item for item in db.scalars(select(ImportBatch).where(ImportBatch.id.in_(batch_ids)))} if batch_ids else {}
    integration_users = {
        (batches[lines[item.import_line_id].import_batch_id].uploaded_by_user_id if item.import_line_id in lines else item.paid_by_user_id)
        for item in expenses if item.source == ExpenseSource.mercadopago
    }
    integrations = {
        item.user_id: item
        for item in db.scalars(
            select(MercadoPagoIntegration).where(
                MercadoPagoIntegration.user_id.in_(integration_users),
                MercadoPagoIntegration.home_group_id == expenses[0].home_group_id,
            )
        )
    } if integration_users else {}
    result = {}
    for expense in expenses:
        line = lines.get(expense.import_line_id) if expense.import_line_id else None
        batch = batches.get(line.import_batch_id) if line else None
        account_user_id = batch.uploaded_by_user_id if batch else expense.paid_by_user_id
        integration = integrations.get(account_user_id) if expense.source == ExpenseSource.mercadopago else None
        result[expense.id] = (line, batch, integration)
    return result


def expense_period(expense: Expense, batch: ImportBatch | None) -> tuple[str, bool]:
    if expense.source == ExpenseSource.import_pdf:
        if batch and batch.statement_period:
            return batch.statement_period, False
        return period_for_date(expense.date), True
    return period_for_date(expense.date), False


def ensure_mp_assignments(db: Session, home_group_id: int) -> list[FundMpAssignment]:
    common_integration_ids = list(
        db.scalars(
            select(MercadoPagoIntegration.id).where(
                MercadoPagoIntegration.home_group_id == home_group_id,
                MercadoPagoIntegration.fund_role == "fondo_comun",
            )
        )
    )
    if not common_integration_ids:
        return []
    rows = list(
        db.execute(
            select(Earning, ImportLine, ImportBatch, MercadoPagoIntegration)
            .join(ImportLine, ImportLine.id == Earning.import_line_id)
            .join(ImportBatch, ImportBatch.id == ImportLine.import_batch_id)
            .join(
                MercadoPagoIntegration,
                (MercadoPagoIntegration.home_group_id == Earning.home_group_id)
                & (MercadoPagoIntegration.user_id == Earning.uploaded_by_user_id),
            )
            .where(
                Earning.home_group_id == home_group_id,
                ImportBatch.source_type == "mercadopago_account_money",
                MercadoPagoIntegration.fund_role == "fondo_comun",
            )
        )
    )
    existing = {
        item.earning_id: item
        for item in db.scalars(
            select(FundMpAssignment).where(
                FundMpAssignment.home_group_id == home_group_id,
                FundMpAssignment.integration_id.in_(common_integration_ids),
            )
        )
    }
    rules = {
        (item.integration_id, item.stable_origin_id): item
        for item in db.scalars(select(FundMpOriginRule).where(FundMpOriginRule.home_group_id == home_group_id))
    }
    for earning, line, _batch, integration in rows:
        if earning.id in existing:
            assignment = existing[earning.id]
            if not assignment.stable_origin_id and line.mercadopago_origin_id:
                assignment.stable_origin_id = line.mercadopago_origin_id
                rule = rules.get((integration.id, assignment.stable_origin_id))
                if rule and assignment.classification == "pending" and assignment.updated_by_user_id is None:
                    assignment.classification = "contribution"
                    assignment.contributor_user_id = rule.user_id
                db.flush()
            continue
        origin = line.mercadopago_origin_id
        rule = rules.get((integration.id, origin)) if origin else None
        values = {
            "home_group_id": home_group_id, "earning_id": earning.id, "integration_id": integration.id,
            "contributor_user_id": rule.user_id if rule else None,
            "classification": "contribution" if rule else "pending", "stable_origin_id": origin,
        }
        dialect = db.get_bind().dialect.name
        if dialect == "sqlite":
            statement = sqlite_insert(FundMpAssignment).values(**values).on_conflict_do_nothing(index_elements=["earning_id"])
        elif dialect == "postgresql":
            statement = postgres_insert(FundMpAssignment).values(**values).on_conflict_do_nothing(index_elements=["earning_id"])
        else:
            raise RuntimeError(f"Unsupported fund database dialect: {dialect}")
        db.execute(statement)
        existing[earning.id] = db.scalar(select(FundMpAssignment).where(FundMpAssignment.earning_id == earning.id))
    return list(existing.values())


def _all_expenses(db: Session, home_group_id: int) -> tuple[list[Expense], dict[int, tuple[ImportLine | None, ImportBatch | None, MercadoPagoIntegration | None]]]:
    expenses = list(db.scalars(select(Expense).where(Expense.home_group_id == home_group_id).order_by(Expense.date, Expense.id)))
    return expenses, expense_fund_context(db, expenses)


def _opening_agreed_balance(db: Session, home_group_id: int, period: str) -> Decimal:
    previous = db.scalar(
        select(FundMonthClosure)
        .where(
            FundMonthClosure.home_group_id == home_group_id,
            FundMonthClosure.period < period,
            FundMonthClosure.status.in_(("cerrado", "desactualizado")),
        )
        .order_by(FundMonthClosure.period.desc())
    )
    if previous is not None:
        return money(previous.agreed_closing_balance)
    opening = db.scalar(select(FundOpeningBalance).where(FundOpeningBalance.home_group_id == home_group_id))
    return money(opening.amount) if opening and period_for_date(opening.start_date) <= period else Decimal("0.00")


def _verified_balance(
    db: Session,
    home_group_id: int,
    through_period: str,
    expenses: list[Expense],
    contexts: dict[int, tuple[ImportLine | None, ImportBatch | None, MercadoPagoIntegration | None]],
    assignments: list[FundMpAssignment],
) -> Decimal:
    opening = db.scalar(select(FundOpeningBalance).where(FundOpeningBalance.home_group_id == home_group_id))
    if opening is None or period_for_date(opening.start_date) > through_period:
        balance = Decimal("0.00")
        start_date = date.min
    else:
        balance = Decimal(opening.amount)
        start_date = opening.start_date
    end = period_end(through_period)
    # A pending income is already real money in the common account even while its
    # economic contributor is unknown. Only an explicit exclusion removes it
    # from the verified fund balance.
    earning_ids = [item.earning_id for item in assignments if item.classification != "excluded"]
    if earning_ids:
        for earning in db.scalars(select(Earning).where(Earning.id.in_(earning_ids), Earning.date >= start_date, Earning.date < end)):
            balance += Decimal(earning.amount_ars)
    for movement in db.scalars(
        select(FundManualMovement).where(
            FundManualMovement.home_group_id == home_group_id,
            FundManualMovement.date >= start_date,
            FundManualMovement.date < end,
        )
    ):
        if movement.from_user_id is not None and movement.to_user_id is None:
            balance += Decimal(movement.amount)
        elif movement.from_user_id is None and movement.to_user_id is not None:
            balance -= Decimal(movement.amount)
    for expense in expenses:
        if expense.date < start_date or expense.date >= end or expense.source != ExpenseSource.mercadopago:
            continue
        integration = contexts[expense.id][2]
        if integration and integration.fund_role == "fondo_comun":
            balance -= Decimal(expense.amount_ars)
    return money(balance)


def calculate_fund_summary(db: Session, home_group_id: int, period: str, *, persist_stale: bool = True) -> dict:
    period = validate_period(period)
    members = household_members(db, home_group_id)
    names = {member.id: member.display_name for _, member in members}
    config, shares = effective_config(db, home_group_id, period)
    assignments = ensure_mp_assignments(db, home_group_id)
    expenses, contexts = _all_expenses(db, home_group_id)
    closure = db.scalar(select(FundMonthClosure).where(FundMonthClosure.home_group_id == home_group_id, FundMonthClosure.period == period))

    if config is None:
        return {
            "period": period,
            "activated": False,
            "status": closure.status if closure else "abierto",
            "members": [{"user_id": user.id, "display_name": user.display_name} for _, user in members],
            "alerts": ["Configura el fondo y el saldo inicial para comenzar."],
            "mp_integrations": _integration_metadata(db, home_group_id),
            "mp_contributions": _mp_contribution_rows(db, home_group_id, assignments, period),
        }

    share_by_user = {item.user_id: Decimal(item.percentage) for item in shares}
    period_expenses: list[Expense] = []
    fallback_expenses: list[Expense] = []
    personal_mp_expenses: list[Expense] = []
    direct_paid: dict[int, Decimal] = defaultdict(Decimal)
    fund_paid = Decimal("0")
    movements: list[dict] = []
    grouped: dict[tuple, Decimal] = defaultdict(Decimal)
    for expense in expenses:
        line, batch, integration = contexts[expense.id]
        assigned_period, fallback = expense_period(expense, batch)
        if assigned_period != period:
            continue
        is_common_mp = bool(expense.source == ExpenseSource.mercadopago and integration and integration.fund_role == "fondo_comun")
        if is_common_mp and not expense.is_shared and Decimal(expense.amount_ars) > 0:
            personal_mp_expenses.append(expense)
            continue
        if not expense.is_shared:
            continue
        period_expenses.append(expense)
        if fallback:
            fallback_expenses.append(expense)
        amount = Decimal(expense.amount_ars)
        if is_common_mp:
            fund_paid += amount
            key = ("expense", "Fondo común · Mercado Pago", "mercadopago")
        else:
            direct_paid[expense.paid_by_user_id] += amount
            if expense.source == ExpenseSource.import_pdf:
                network = (batch.card_network if batch else None) or "Tarjeta"
                label = f"{names.get(expense.paid_by_user_id, 'Usuario')} · {network}"
            else:
                label = f"{names.get(expense.paid_by_user_id, 'Usuario')} · {_source_label(expense.source)}"
            key = ("expense", label, expense.source.value)
        grouped[key] += amount

    manual_rows = list(
        db.scalars(
            select(FundManualMovement).where(
                FundManualMovement.home_group_id == home_group_id,
                FundManualMovement.date >= date.fromisoformat(f"{period}-01"),
                FundManualMovement.date < period_end(period),
            ).order_by(FundManualMovement.date, FundManualMovement.id)
        )
    )
    contribution_by_user: dict[int, Decimal] = defaultdict(Decimal)
    fund_deposits_by_user: dict[int, Decimal] = defaultdict(Decimal)
    fund_inflows = Decimal("0")
    fund_outflows = Decimal("0")
    for item in manual_rows:
        amount = Decimal(item.amount)
        if item.from_user_id is not None and item.to_user_id is None:
            contribution_by_user[item.from_user_id] += amount
            fund_deposits_by_user[item.from_user_id] += amount
            fund_inflows += amount
        elif item.from_user_id is not None and item.to_user_id is not None:
            contribution_by_user[item.from_user_id] += amount
            contribution_by_user[item.to_user_id] -= amount
        elif item.from_user_id is None and item.to_user_id is not None:
            contribution_by_user[item.to_user_id] -= amount
            fund_outflows += amount
        movements.append(_manual_movement_read(item, names))

    mp_rows = _mp_contribution_rows(db, home_group_id, assignments, period)
    for item in mp_rows:
        if item["classification"] == "contribution" and item["contributor_user_id"] is not None:
            amount = Decimal(item["amount_ars"])
            contribution_by_user[item["contributor_user_id"]] += amount
            fund_deposits_by_user[item["contributor_user_id"]] += amount
            fund_inflows += amount
            movements.append({
                "id": f"mp-{item['earning_id']}", "kind": "mp_contribution", "date": item["date"],
                "label": item["description"], "amount": str(money(amount)), "editable": False,
            })

    shared_total = money(sum((Decimal(item.amount_ars) for item in period_expenses), Decimal("0")))
    configured = money(config.monthly_amount)
    financing_base = max(configured, shared_total)
    personal_outflow_by_user: dict[int, Decimal] = defaultdict(Decimal)
    for expense in personal_mp_expenses:
        # The token owner is responsible for restoring a personal debit from
        # the fund wallet, even if the expense payer was later edited.
        personal_outflow_by_user[contexts[expense.id][2].user_id] += Decimal(expense.amount_ars)
    personal_outflow_total = money(sum(personal_outflow_by_user.values(), Decimal("0")))
    personal_repaid_by_user = {
        user_id: money(min(amount, max(Decimal("0"), fund_deposits_by_user[user_id])))
        for user_id, amount in personal_outflow_by_user.items()
    }
    personal_to_repay_by_user = {
        user_id: money(amount - personal_repaid_by_user[user_id])
        for user_id, amount in personal_outflow_by_user.items()
    }
    positions = []
    remaining: dict[int, Decimal] = {}
    quotas = {
        member.id: money(financing_base * share_by_user.get(member.id, Decimal("0")) / HUNDRED)
        for _, member in members
    }
    if members:
        last_member_id = members[-1][1].id
        quotas[last_member_id] = money(quotas[last_member_id] + financing_base - sum(quotas.values(), Decimal("0")))
    for _, member in members:
        percentage = share_by_user.get(member.id, Decimal("0"))
        quota = quotas[member.id]
        direct = money(direct_paid[member.id])
        contributed = money(contribution_by_user[member.id] - personal_repaid_by_user.get(member.id, Decimal("0")))
        economic = money(direct + contributed)
        outstanding = money(quota - economic)
        remaining[member.id] = outstanding
        positions.append({
            "user_id": member.id,
            "display_name": member.display_name,
            "percentage": str(percentage),
            "quota": str(quota),
            "direct_paid": str(direct),
            "contributed": str(contributed),
            "personal_outflow": str(money(personal_outflow_by_user[member.id])),
            "personal_repaid": str(personal_repaid_by_user.get(member.id, Decimal("0.00"))),
            "personal_to_repay": str(personal_to_repay_by_user.get(member.id, Decimal("0.00"))),
            "economic_contribution": str(economic),
            "outstanding": str(outstanding),
            "to_receive": str(money(max(Decimal("0"), -outstanding))),
        })

    plan: list[dict] = []
    debtors = [[user_id, value] for user_id, value in remaining.items() if value > 0]
    creditors = [[user_id, -value] for user_id, value in remaining.items() if value < 0]
    for debtor in debtors:
        for creditor in creditors:
            transfer = money(min(debtor[1], creditor[1]))
            if transfer <= 0:
                continue
            plan.append(_plan_row(debtor[0], creditor[0], transfer, names))
            debtor[1] = money(debtor[1] - transfer)
            creditor[1] = money(creditor[1] - transfer)
    for user_id, amount in debtors:
        if amount > 0:
            plan.append(_plan_row(user_id, None, money(amount), names))
    for user_id, amount in personal_to_repay_by_user.items():
        if amount > 0:
            plan.append({**_plan_row(user_id, None, amount, names), "reason": "personal_mp_outflow"})

    proposed_fund = sum((Decimal(item["amount"]) for item in plan if item["to_kind"] == "fund"), Decimal("0"))
    agreed_opening = _opening_agreed_balance(db, home_group_id, period)
    # An over-budget month has no agreed fund remainder to carry forward. Keep
    # the verified balance separate: it still reflects actual money movements.
    agreed_closing = (
        Decimal("0.00") if shared_total > configured
        else money(agreed_opening + fund_inflows + proposed_fund - fund_paid - personal_outflow_total - fund_outflows)
    )
    verified = _verified_balance(db, home_group_id, period, expenses, contexts, assignments)
    input_hash = calculation_hash(db, config, shares, period_expenses + personal_mp_expenses, assignments, manual_rows, period, contexts)
    status = closure.status if closure else "abierto"
    if closure and closure.status in ("cerrado", "pendiente_aprobacion") and closure.input_hash != input_hash:
        status = "desactualizado"
        if persist_stale and closure.status != status:
            closure.status = status
            db.flush()

    approvals = []
    if closure:
        approved = {item.user_id: item for item in db.scalars(select(FundClosureApproval).where(FundClosureApproval.closure_id == closure.id))}
        obligated = sorted({item["from_user_id"] for item in closure.snapshot.get("plan", []) if item.get("amount") != "0.00"})
        approvals = [
            {"user_id": user_id, "display_name": names.get(user_id, f"Usuario #{user_id}"), "approved": user_id in approved,
             "approved_at": approved[user_id].approved_at.isoformat() if user_id in approved else None}
            for user_id in obligated
        ]

    opening = db.scalar(select(FundOpeningBalance).where(FundOpeningBalance.home_group_id == home_group_id))

    for (kind, label, source), amount in grouped.items():
        movements.append({"id": f"group-{len(movements)}", "kind": kind, "date": period, "label": label, "source": source, "amount": str(money(amount)), "editable": False})
    if closure:
        movements.append({
            "id": f"closure-{closure.id}", "kind": "closure", "date": period,
            "label": f"Cierre mensual · {status.replace('_', ' ')}",
            "amount": str(money(closure.agreed_closing_balance)), "editable": False,
        })
    movements.sort(key=lambda item: (item["date"], str(item["id"])), reverse=True)
    alerts: list[str] = []
    if shared_total > configured:
        alerts.append(f"Los gastos superan el fondo configurado por ARS {human_amount(shared_total - configured)}.")
    if fallback_expenses:
        alerts.append(f"{len(fallback_expenses)} consumo(s) de tarjeta no tienen período de resumen; se usó la fecha del consumo.")
    pending_mp = [item for item in mp_rows if item["classification"] == "pending"]
    if pending_mp:
        alerts.append(f"Hay {len(pending_mp)} ingreso(s) de Mercado Pago pendientes de asignar.")
    possible_duplicates = sum(
        1
        for mp_item in mp_rows
        for manual in manual_rows
        if manual.from_user_id is not None
        and manual.to_user_id is None
        and abs((date.fromisoformat(mp_item["date"]) - manual.date).days) <= 2
        and money(mp_item["amount_ars"]) == money(manual.amount)
    )
    if possible_duplicates:
        alerts.append(f"Hay {possible_duplicates} ingreso(s) MP que podrían duplicar movimientos manuales; confirmá su clasificación.")
    if personal_mp_expenses:
        alerts.append(f"Hay {len(personal_mp_expenses)} compra(s) personales en una cuenta Mercado Pago del fondo por ARS {human_amount(personal_outflow_total)}. El titular debe conciliar la salida.")

    result = {
        "period": period,
        "activated": True,
        "status": status,
        "config": {
            "source_period": config.period,
            "inherited": config.period != period,
            "monthly_amount": str(configured),
            "shares": [{"user_id": item.user_id, "percentage": str(Decimal(item.percentage))} for item in shares],
        },
        "opening_balance": {"start_date": opening.start_date.isoformat(), "amount": str(money(opening.amount))} if opening else None,
        "totals": {
            "configured_fund": str(configured), "shared_expenses": str(shared_total), "financing_base": str(money(financing_base)),
            "surplus_or_excess": str(money(configured - shared_total)), "agreed_opening_balance": str(agreed_opening),
            "agreed_balance": str(agreed_closing), "verified_balance": str(verified), "difference": str(money(verified - agreed_closing)),
            "personal_outflows": str(personal_outflow_total),
            "personal_to_repay": str(money(sum(personal_to_repay_by_user.values(), Decimal("0")))),
        },
        "positions": positions,
        "plan": plan,
        "approvals": approvals,
        "alerts": alerts,
        "movements": movements,
        "mp_contributions": mp_rows,
        "mp_personal_outflows": _mp_personal_outflow_rows(personal_mp_expenses, contexts, names),
        "mp_integrations": _integration_metadata(db, home_group_id),
        "input_hash": input_hash,
    }
    return result


def calculation_hash(db, config, shares, expenses, assignments, movements, period, contexts) -> str:
    assignment_rows = []
    earning_by_id = {}
    assignment_ids = [item.earning_id for item in assignments]
    if assignment_ids:
        # Earning values are reflected through their stable assignment identity and update state.
        earning_by_id = {item.id: item for item in db.scalars(select(Earning).where(Earning.id.in_(assignment_ids)))}
    payload = {
        "period": period,
        "config": [config.id, str(config.monthly_amount), config.period],
        "shares": [[item.user_id, str(item.percentage)] for item in shares],
        "expenses": [[item.id, str(item.amount_ars), item.paid_by_user_id, item.is_shared,
                      contexts[item.id][1].statement_period if contexts[item.id][1] else None,
                      contexts[item.id][2].fund_role if contexts[item.id][2] else None] for item in expenses],
        "assignments": assignment_rows or [[item.earning_id, item.contributor_user_id, item.classification, item.stable_origin_id] for item in assignments if earning_by_id.get(item.earning_id) and period_for_date(earning_by_id[item.earning_id].date) == period],
        "movements": [[item.id, item.date.isoformat(), item.from_user_id, item.to_user_id, str(item.amount), item.note] for item in movements],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
def _plan_row(from_user_id: int, to_user_id: int | None, amount: Decimal, names: dict[int, str]) -> dict:
    return {
        "from_user_id": from_user_id, "from_name": names.get(from_user_id, f"Usuario #{from_user_id}"),
        "to_kind": "person" if to_user_id is not None else "fund", "to_user_id": to_user_id,
        "to_name": names.get(to_user_id, "Fondo común") if to_user_id is not None else "Fondo común", "amount": str(amount),
    }


def _source_label(source: ExpenseSource) -> str:
    return {ExpenseSource.manual: "Manual", ExpenseSource.bank_import: "Banco", ExpenseSource.mercadopago: "Mercado Pago", ExpenseSource.cash: "Efectivo", ExpenseSource.transfer: "Transferencia"}.get(source, "Otros")


def _manual_movement_read(item: FundManualMovement, names: dict[int, str]) -> dict:
    from_name = names.get(item.from_user_id, "Fondo común") if item.from_user_id else "Fondo común"
    to_name = names.get(item.to_user_id, "Fondo común") if item.to_user_id else "Fondo común"
    return {
        "id": item.id, "kind": "manual", "date": item.date.isoformat(), "label": f"{from_name} → {to_name}",
        "from_user_id": item.from_user_id, "to_user_id": item.to_user_id,
        "amount": str(money(item.amount)), "note": item.note, "editable": True,
    }


def _mp_contribution_rows(db: Session, home_group_id: int, assignments: list[FundMpAssignment], period: str | None) -> list[dict]:
    earning_ids = [item.earning_id for item in assignments]
    earnings = {item.id: item for item in db.scalars(select(Earning).where(Earning.id.in_(earning_ids)))} if earning_ids else {}
    line_ids = [item.import_line_id for item in earnings.values() if item.import_line_id is not None]
    lines = {item.id: item for item in db.scalars(select(ImportLine).where(ImportLine.id.in_(line_ids)))} if line_ids else {}
    integration_ids = {item.integration_id for item in assignments}
    integrations = {item.id: item for item in db.scalars(select(MercadoPagoIntegration).where(MercadoPagoIntegration.id.in_(integration_ids)))} if integration_ids else {}
    names = {item.id: item.display_name for item in db.scalars(select(User).join(Membership, Membership.user_id == User.id).where(Membership.home_group_id == home_group_id))}
    output = []
    for item in assignments:
        earning = earnings.get(item.earning_id)
        if not earning or period is not None and period_for_date(earning.date) != period:
            continue
        line = lines.get(earning.import_line_id)
        try:
            raw = json.loads(line.raw_text) if line and line.raw_text else {}
        except (TypeError, ValueError):
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        payer_name = str(raw.get("PAYER_NAME") or "").strip() or None
        payer_document = str(raw.get("PAYER_ID_NUMBER") or "").strip()
        classification = "pending" if item.classification == "refund" else item.classification
        output.append({
            "assignment_id": item.id, "earning_id": earning.id, "date": earning.date.isoformat(), "description": earning.description,
            "amount_ars": str(money(earning.amount_ars)), "classification": classification,
            "contributor_user_id": item.contributor_user_id, "contributor_name": names.get(item.contributor_user_id),
            "stable_origin_id": item.stable_origin_id, "can_remember_origin": bool(item.stable_origin_id),
            "payer_name": payer_name,
            "payer_document_suffix": payer_document[-4:] if payer_document else None,
            "payment_method_type": str(raw.get("PAYMENT_METHOD_TYPE") or "").strip() or None,
            "integration_id": item.integration_id,
            "account_user_id": integrations[item.integration_id].user_id if item.integration_id in integrations else None,
            "account_name": names.get(integrations[item.integration_id].user_id) if item.integration_id in integrations else None,
            "assignment_source": "rule" if classification == "contribution" and item.updated_by_user_id is None else "manual" if classification == "contribution" else None,
            "legacy_refund": item.classification == "refund",
        })
    return sorted(output, key=lambda item: (item["date"], item["earning_id"]), reverse=True)


def _integration_metadata(db: Session, home_group_id: int) -> list[dict]:
    names = {item.id: item.display_name for item in db.scalars(select(User).join(Membership, Membership.user_id == User.id).where(Membership.home_group_id == home_group_id))}
    return [
        {"id": item.id, "user_id": item.user_id, "display_name": names.get(item.user_id), "fund_role": item.fund_role,
         "nickname": item.mp_nickname, "enabled": item.enabled}
        for item in db.scalars(select(MercadoPagoIntegration).where(MercadoPagoIntegration.home_group_id == home_group_id))
    ]


def _mp_personal_outflow_rows(expenses, contexts, names) -> list[dict]:
    return [
        {
            "expense_id": expense.id,
            "date": expense.date.isoformat(),
            "description": expense.description,
            "amount_ars": str(money(expense.amount_ars)),
            "account_user_id": contexts[expense.id][2].user_id,
            "account_name": names.get(contexts[expense.id][2].user_id),
        }
        for expense in sorted(expenses, key=lambda item: (item.date, item.id), reverse=True)
    ]


def mp_activity(db: Session, home_group_id: int) -> dict:
    assignments = ensure_mp_assignments(db, home_group_id)
    expenses, contexts = _all_expenses(db, home_group_id)
    names = {user.id: user.display_name for _, user in household_members(db, home_group_id)}
    personal_outflows = [
        expense for expense in expenses
        if expense.source == ExpenseSource.mercadopago and not expense.is_shared
        and Decimal(expense.amount_ars) > 0
        and contexts[expense.id][2] and contexts[expense.id][2].fund_role == "fondo_comun"
    ]
    return {
        "incomes": _mp_contribution_rows(db, home_group_id, assignments, None),
        "personal_outflows": _mp_personal_outflow_rows(personal_outflows, contexts, names),
    }
