from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.domain import Currency
from app.models import FxRate

router = APIRouter(prefix="/fx", tags=["fx"])


@router.get("/rates")
def list_rates(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "date": rate.date,
            "source": rate.source,
            "from_currency": rate.from_currency.value,
            "to_currency": rate.to_currency.value,
            "rate": rate.rate,
        }
        for rate in db.scalars(select(FxRate).order_by(FxRate.date.desc()))
    ]


@router.post("/rates")
def upsert_rate(payload: dict, db: Session = Depends(get_db)) -> dict:
    rate_date = date.fromisoformat(payload["date"])
    source = payload.get("source", "blue_average")
    from_currency = Currency(payload.get("from_currency", "USD"))
    to_currency = Currency(payload.get("to_currency", "ARS"))
    rate = db.scalar(
        select(FxRate).where(
            FxRate.date == rate_date,
            FxRate.source == source,
            FxRate.from_currency == from_currency,
            FxRate.to_currency == to_currency,
        )
    )
    if rate is None:
        rate = FxRate(date=rate_date, source=source, from_currency=from_currency, to_currency=to_currency)
        db.add(rate)
    rate.from_currency = from_currency
    rate.to_currency = to_currency
    rate.rate = Decimal(str(payload["rate"]))
    db.commit()
    return {"ok": True}
