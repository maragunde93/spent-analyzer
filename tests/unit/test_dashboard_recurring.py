import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.dashboard import dashboard
from app.database import Base
from app.domain import Currency, ExpenseSource, ImportLineKind
from app.models import Category, Expense, HomeGroup, ImportBatch, ImportLine, Membership, Subcategory, User


class DashboardRecurringTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(email="mauro@example.test", display_name="Mauro")
        self.home = HomeGroup(name="Casa")
        self.db.add_all([self.user, self.home])
        self.db.flush()
        self.db.add(Membership(user_id=self.user.id, home_group_id=self.home.id, role="owner"))
        self.services = Category(home_group_id=self.home.id, name="Servicios", color="#ff9800", icon="receipt")
        self.subscriptions = Category(home_group_id=self.home.id, name="Suscripciones", color="#ffc107", icon="repeat")
        self.db.add_all([self.services, self.subscriptions])
        self.db.flush()
        self.water = Subcategory(home_group_id=self.home.id, category_id=self.services.id, name="Agua")
        self.bank = Subcategory(home_group_id=self.home.id, category_id=self.services.id, name="Banco")
        self.db.add_all([self.water, self.bank])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_recurring_projection_groups_by_subcategory_expires_old_and_ignores_reimbursed(self):
        self._expense(date(2026, 5, 10), "PAGO DE SERVICIOS TARJETA 18073039 OP1111", self.services.id, self.water.id, Decimal("100000.00"), True)
        self._expense(date(2026, 6, 10), "PAGO DE SERVICIOS TARJETA 18073039 OP2222", self.services.id, self.water.id, Decimal("150000.00"), True)
        self._expense(date(2026, 7, 10), "PAGO DE SERVICIOS TARJETA 18073039 OP3333", self.services.id, self.water.id, Decimal("200000.00"), True)
        self._expense(date(2026, 4, 5), "CRUNCHYROLL", self.subscriptions.id, None, Decimal("8000.00"), True)
        self._expense(date(2026, 7, 1), "COMISION CTA PWORLD", self.services.id, self.bank.id, Decimal("57599.00"), True)
        self._expense(date(2026, 7, 1), "DEV COMISION CTA PWORLD", self.services.id, self.bank.id, Decimal("-57599.00"), True)
        self.db.commit()

        result = dashboard(self.home.id, user=self.user, db=self.db)
        names = [item["description"] for item in result.recurring_preview]

        self.assertIn("Agua", names)
        self.assertNotIn("Crunchyroll", names)
        self.assertNotIn("Banco", names)
        water = next(item for item in result.recurring_preview if item["description"] == "Agua")
        self.assertEqual(water["category"], "Servicios")
        self.assertEqual(water["subcategory"], "Agua")
        self.assertEqual(water["last_period"], "2026-07")
        self.assertEqual(water["last_amount"], Decimal("200000.00"))
        self.assertEqual(water["monthly_average"], Decimal("150000.00"))
        self.assertEqual(water["accumulated_amount"], Decimal("450000.00"))
        self.assertEqual(water["annualized_amount"], Decimal("1800000.00"))
        self.assertEqual(len(water["items"]), 3)

    def test_bank_statement_month_does_not_expire_recent_card_statement_recurring_items(self):
        card_batch = self._card_batch("31-May-26")
        card_line = self._card_line(card_batch, date(2026, 5, 18), "CRUNCHYROLL", Decimal("8000.00"))
        self._expense(
            date(2026, 5, 18),
            "CRUNCHYROLL",
            self.subscriptions.id,
            None,
            Decimal("8000.00"),
            True,
            source=ExpenseSource.import_pdf,
            import_line_id=card_line.id,
        )
        self._expense(date(2026, 7, 5), "PAGO DE SERVICIOS TARJETA OP3802", self.services.id, None, Decimal("38579.00"), True)
        self.db.commit()

        result = dashboard(self.home.id, user=self.user, db=self.db)
        names = [item["description"] for item in result.recurring_preview]

        self.assertIn("Crunchyroll", names)

    def _expense(
        self,
        expense_date: date,
        description: str,
        category_id: int,
        subcategory_id: int | None,
        amount: Decimal,
        is_recurring: bool,
        source: ExpenseSource = ExpenseSource.bank_import,
        import_line_id: int | None = None,
    ) -> Expense:
        expense = Expense(
            home_group_id=self.home.id,
            date=expense_date,
            description=description,
            category_id=category_id,
            subcategory_id=subcategory_id,
            paid_by_user_id=self.user.id,
            uploaded_by_user_id=self.user.id,
            source=source,
            currency=Currency.ARS,
            original_amount=amount,
            amount_ars=amount,
            import_line_id=import_line_id,
            is_recurring=is_recurring,
        )
        self.db.add(expense)
        return expense

    def _card_batch(self, period_label: str) -> ImportBatch:
        batch = ImportBatch(
            home_group_id=self.home.id,
            uploaded_by_user_id=self.user.id,
            filename="card.pdf",
            source_type="bbva_visa_pdf",
            period_label=period_label,
        )
        self.db.add(batch)
        self.db.flush()
        return batch

    def _card_line(self, batch: ImportBatch, line_date: date, description: str, amount: Decimal) -> ImportLine:
        line = ImportLine(
            import_batch_id=batch.id,
            home_group_id=self.home.id,
            date=line_date,
            description=description,
            kind=ImportLineKind.purchase,
            currency=Currency.ARS,
            original_amount=amount,
            suggested_category_id=self.subscriptions.id,
            suggested_recurring=True,
            fingerprint=f"{batch.id}:{description}:{amount}",
            raw_text=description,
        )
        self.db.add(line)
        self.db.flush()
        return line


if __name__ == "__main__":
    unittest.main()
