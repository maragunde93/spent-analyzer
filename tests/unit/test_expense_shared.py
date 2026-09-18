import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.expenses import create_expense, list_expenses
from app.database import Base
from app.domain import Currency, ExpenseSource
from app.models import Category, HomeGroup, Membership, User
from app.schemas import ExpenseCreate


class ExpenseSharedTests(unittest.TestCase):
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
        self.db.add(self.services)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_new_expense_uses_shared_defaults_and_scope_filter(self):
        shared = self._create("EDESUR FACTURA", self.services.id)
        personal = self._create("OPENAI CHATGPT", self.services.id)

        self.assertTrue(shared.is_shared)
        self.assertFalse(personal.is_shared)
        self.assertEqual(
            [expense.description for expense in list_expenses(self.home.id, is_shared=True, search=None, user=self.user, db=self.db)],
            ["EDESUR FACTURA"],
        )
        self.assertEqual(
            [expense.description for expense in list_expenses(self.home.id, is_shared=False, search=None, user=self.user, db=self.db)],
            ["OPENAI CHATGPT"],
        )

    def _create(self, description: str, category_id: int):
        return create_expense(
            self.home.id,
            ExpenseCreate(
                date=date(2026, 9, 18),
                description=description,
                category_id=category_id,
                paid_by_user_id=self.user.id,
                currency=Currency.ARS,
                original_amount=Decimal("1000.00"),
                source=ExpenseSource.manual,
            ),
            self.user,
            self.db,
        )


if __name__ == "__main__":
    unittest.main()
