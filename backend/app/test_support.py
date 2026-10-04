"""Test-only HTTP fixtures used by browser end-to-end scenarios."""

from datetime import date
from decimal import Decimal
import json

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.database import SessionLocal
from app.domain import Currency, ExpenseSource, ImportLineKind
from app.models import Earning, Expense, ImportBatch, ImportLine, MercadoPagoIntegration, User

router = APIRouter(prefix="/test", tags=["test"])


@router.post("/seed-fund-mp")
def seed_fund_mp(phase: str = "initial") -> dict:
    if phase not in {"initial", "followup", "later-month"}:
        raise HTTPException(status_code=400, detail="Invalid fixture phase")
    with SessionLocal() as db:
        mauro = db.scalar(select(User).where(User.email == "mauro@example.test"))
        if mauro is None:
            raise HTTPException(status_code=404, detail="Reset the test database first")
        integration = db.scalar(select(MercadoPagoIntegration).where(MercadoPagoIntegration.home_group_id == 1, MercadoPagoIntegration.user_id == mauro.id))
        if phase == "initial":
            if integration is not None:
                raise HTTPException(status_code=409, detail="Fixture already seeded")
            integration = MercadoPagoIntegration(
                home_group_id=1, user_id=mauro.id, access_token="test-only-token",
                mp_nickname="FONDO_E2E", fund_role="personal",
            )
            db.add(integration)
            rows = [
                ("Ingreso Mauro", "income", "10000", "test:mauro-bank", None),
                ("Ingreso Mica", "income", "15000", "test:mica-bank", None),
                ("Ingreso desconocido", "income", "3000", None, None),
                ("Compra compartida", "purchase", "15000", None, True),
                ("Compra personal", "purchase", "2000", None, False),
            ]
        elif phase == "followup":
            if integration is None:
                raise HTTPException(status_code=404, detail="Seed the initial fixture first")
            rows = [("Segundo ingreso Mica", "income", "5000", "test:mica-bank", None)]
        else:
            if integration is None:
                raise HTTPException(status_code=404, detail="Seed the initial fixture first")
            rows = [("Ingreso siguiente mes", "income", "7000", "test:mica-bank", None)]

        batch = ImportBatch(
            home_group_id=1, uploaded_by_user_id=mauro.id,
            filename=f"fund-mp-{phase}.csv", source_type="mercadopago_account_money", status="committed",
        )
        db.add(batch)
        db.flush()
        for index, (description, kind, amount, origin, shared) in enumerate(rows):
            value = Decimal(amount)
            line = ImportLine(
                import_batch_id=batch.id, home_group_id=1, date=date(2026, 7 if phase == "later-month" else 6, 10),
                description=description, kind=ImportLineKind(kind), currency=Currency.ARS,
                original_amount=value, status="committed", fingerprint=f"fund-mp-{batch.id}-{index}",
                raw_text=json.dumps({"PAYER_NAME": "Mica" if "Mica" in description else "Mauro" if "Mauro" in description else "", "PAYMENT_METHOD_TYPE": "bank_transfer"}) if kind == "income" else "{}",
                mercadopago_origin_id=origin,
            )
            db.add(line)
            db.flush()
            if kind == "income":
                db.add(Earning(
                    home_group_id=1, date=line.date, description=description,
                    user_id=mauro.id, uploaded_by_user_id=mauro.id, currency=Currency.ARS,
                    original_amount=value, amount_ars=value, import_line_id=line.id,
                ))
            else:
                db.add(Expense(
                    home_group_id=1, date=line.date, description=description,
                    paid_by_user_id=mauro.id, uploaded_by_user_id=mauro.id,
                    source=ExpenseSource.mercadopago, currency=Currency.ARS,
                    original_amount=value, amount_ars=value, import_line_id=line.id,
                    is_shared=shared,
                ))
        db.commit()
        return {"ok": True, "rows": len(rows)}
