import asyncio
import json
import logging
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain import Currency
from app.models import Expense, FxRate

logger = logging.getLogger(__name__)

FX_SOURCE_BLUE_AVERAGE = "blue_average"
DEFAULT_BLUE_API_URL = "https://dolarapi.com/v1/dolares/blue"
ARS_TZ = ZoneInfo("America/Argentina/Buenos_Aires")


def argentina_now() -> datetime:
    return datetime.now(ARS_TZ)


def blue_average_rate(payload: dict) -> Decimal:
    compra = Decimal(str(payload["compra"]))
    venta = Decimal(str(payload["venta"]))
    return ((compra + venta) / Decimal("2")).quantize(Decimal("0.0001"))


def fetch_blue_payload(api_url: str = DEFAULT_BLUE_API_URL, timeout_seconds: float = 10.0) -> dict:
    request = Request(api_url, headers={"User-Agent": "spent-analyzer/1.0"})
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def upsert_blue_rate(db: Session, rate_date: date, rate: Decimal, source: str = FX_SOURCE_BLUE_AVERAGE) -> FxRate:
    fx_rate = db.scalar(
        select(FxRate).where(
            FxRate.date == rate_date,
            FxRate.source == source,
            FxRate.from_currency == Currency.USD,
            FxRate.to_currency == Currency.ARS,
        )
    )
    if fx_rate is None:
        fx_rate = FxRate(
            date=rate_date,
            source=source,
            from_currency=Currency.USD,
            to_currency=Currency.ARS,
        )
        db.add(fx_rate)
    fx_rate.rate = rate
    return fx_rate


def update_blue_rate(
    db: Session,
    *,
    api_url: str = DEFAULT_BLUE_API_URL,
    timeout_seconds: float = 10.0,
    rate_date: date | None = None,
    fetcher: Callable[[], dict] | None = None,
) -> dict:
    payload = fetcher() if fetcher is not None else fetch_blue_payload(api_url, timeout_seconds)
    rate = blue_average_rate(payload)
    effective_date = rate_date or argentina_now().date()
    fx_rate = upsert_blue_rate(db, effective_date, rate)
    db.commit()
    logger.info(
        "fx_blue_rate_updated source=%s date=%s rate=%s compra=%s venta=%s api_updated_at=%s",
        fx_rate.source,
        fx_rate.date,
        fx_rate.rate,
        payload.get("compra"),
        payload.get("venta"),
        payload.get("fechaActualizacion"),
    )
    return {
        "date": fx_rate.date.isoformat(),
        "source": fx_rate.source,
        "rate": str(fx_rate.rate),
        "compra": payload.get("compra"),
        "venta": payload.get("venta"),
        "fecha_actualizacion": payload.get("fechaActualizacion"),
    }


def recalculate_usd_expenses_with_rate(db: Session, rate: Decimal) -> int:
    expenses = list(db.scalars(select(Expense).where(Expense.currency == Currency.USD)))
    for expense in expenses:
        expense.amount_ars = (Decimal(expense.original_amount) * rate).quantize(Decimal("0.01"))
    db.commit()
    logger.info("fx_usd_expenses_recalculated count=%s rate=%s", len(expenses), rate)
    return len(expenses)


def recalculate_usd_expenses_with_latest_blue_rate(db: Session, reference_date: date | None = None) -> dict:
    effective_date = reference_date or argentina_now().date()
    fx_rate = db.scalar(
        select(FxRate)
        .where(
            FxRate.date <= effective_date,
            FxRate.source == FX_SOURCE_BLUE_AVERAGE,
            FxRate.from_currency == Currency.USD,
            FxRate.to_currency == Currency.ARS,
        )
        .order_by(FxRate.date.desc())
    )
    if fx_rate is None:
        raise RuntimeError("No hay tipo de cambio blue cargado para recalcular consumos USD")
    count = recalculate_usd_expenses_with_rate(db, Decimal(fx_rate.rate))
    return {"recalculated": count, "rate": str(fx_rate.rate), "date": fx_rate.date.isoformat()}


def seconds_until_next_run(now: datetime, hour_argentina: int) -> float:
    local_now = now.astimezone(ARS_TZ)
    target = datetime.combine(local_now.date(), time(hour_argentina, 0), tzinfo=ARS_TZ)
    if local_now >= target:
        target += timedelta(days=1)
    return max((target - local_now).total_seconds(), 0.0)


async def run_daily_blue_rate_update(
    session_factory: sessionmaker,
    *,
    api_url: str = DEFAULT_BLUE_API_URL,
    hour_argentina: int = 11,
    timeout_seconds: float = 10.0,
) -> None:
    last_success_date: date | None = None
    while True:
        now = argentina_now()
        today_target = datetime.combine(now.date(), time(hour_argentina, 0), tzinfo=ARS_TZ)
        should_run = now >= today_target and last_success_date != now.date()
        if not should_run:
            await asyncio.sleep(seconds_until_next_run(now, hour_argentina))
            continue

        try:
            with session_factory() as db:
                update_blue_rate(db, api_url=api_url, timeout_seconds=timeout_seconds, rate_date=now.date())
            last_success_date = now.date()
        except Exception:
            logger.exception("fx_blue_rate_update_failed")
            await asyncio.sleep(15 * 60)
