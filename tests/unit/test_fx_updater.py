import sys
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.database import Base
from app.domain import Currency, ExpenseSource
from app.models import Expense, FxRate, HomeGroup, Membership, User
from app.services.fx_updater import (
    blue_average_rate,
    recalculate_usd_expenses_with_latest_blue_rate,
    seconds_until_next_run,
    update_blue_rate,
)


class FxUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(email="mauro@example.test", display_name="Mauro")
        self.home = HomeGroup(name="Casa")
        self.db.add_all([self.user, self.home])
        self.db.flush()
        self.db.add(Membership(user_id=self.user.id, home_group_id=self.home.id, role="owner"))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_blue_average_uses_compra_and_venta(self):
        rate = blue_average_rate({"compra": 1495, "venta": 1515})
        self.assertEqual(rate, Decimal("1505.0000"))

    def test_update_blue_rate_upserts_today_rate_from_dolarapi_payload(self):
        result = update_blue_rate(
            self.db,
            rate_date=date(2026, 7, 7),
            fetcher=lambda: {
                "moneda": "USD",
                "casa": "blue",
                "nombre": "Blue",
                "compra": 1495,
                "venta": 1515,
                "fechaActualizacion": "2026-07-06T21:00:00.000Z",
            },
        )

        rate = self.db.scalar(select(FxRate).where(FxRate.date == date(2026, 7, 7)))
        self.assertIsNotNone(rate)
        self.assertEqual(rate.rate, Decimal("1505.0000"))
        self.assertEqual(result["rate"], "1505.0000")

    def test_recalculate_usd_expenses_once_with_latest_blue_rate(self):
        self.db.add(
            FxRate(
                date=date(2026, 7, 7),
                source="blue_average",
                from_currency=Currency.USD,
                to_currency=Currency.ARS,
                rate=Decimal("1505.0000"),
            )
        )
        usd_expense = self._expense(
            description="Spotify",
            currency=Currency.USD,
            original_amount=Decimal("4.02"),
            amount_ars=Decimal("4020.00"),
        )
        ars_expense = self._expense(
            description="Edesur",
            currency=Currency.ARS,
            original_amount=Decimal("1000.00"),
            amount_ars=Decimal("1000.00"),
        )
        self.db.commit()

        result = recalculate_usd_expenses_with_latest_blue_rate(self.db, date(2026, 7, 7))
        self.db.refresh(usd_expense)
        self.db.refresh(ars_expense)

        self.assertEqual(result["recalculated"], 1)
        self.assertEqual(usd_expense.amount_ars, Decimal("6050.10"))
        self.assertEqual(ars_expense.amount_ars, Decimal("1000.00"))

    def test_daily_scheduler_waits_until_next_argentina_11am(self):
        tz = ZoneInfo("America/Argentina/Buenos_Aires")
        before = datetime(2026, 7, 7, 10, 30, tzinfo=tz)
        after = datetime(2026, 7, 7, 11, 5, tzinfo=tz)

        self.assertEqual(seconds_until_next_run(before, 11), 30 * 60)
        self.assertEqual(seconds_until_next_run(after, 11), 23 * 60 * 60 + 55 * 60)

    def _expense(
        self,
        *,
        description: str,
        currency: Currency,
        original_amount: Decimal,
        amount_ars: Decimal,
    ) -> Expense:
        expense = Expense(
            home_group_id=self.home.id,
            date=date(2026, 5, 3),
            description=description,
            paid_by_user_id=self.user.id,
            uploaded_by_user_id=self.user.id,
            source=ExpenseSource.import_pdf,
            currency=currency,
            original_amount=original_amount,
            amount_ars=amount_ars,
        )
        self.db.add(expense)
        self.db.flush()
        return expense


if __name__ == "__main__":
    unittest.main()
