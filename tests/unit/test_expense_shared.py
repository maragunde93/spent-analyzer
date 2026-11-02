import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.expenses import create_expense, list_expenses, update_expense
from app.database import Base
from app.domain import Currency, ExpenseSource, ImportLineKind
from app.models import Category, HomeGroup, ImportBatch, ImportLine, Membership, User
from app.schemas import ExpenseCreate, ExpenseRead, ExpenseUpdate
from fastapi import HTTPException


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

    def test_imported_expense_exposes_network_and_allows_changing_payer(self):
        other = User(email="mica@example.test", display_name="Mica")
        self.db.add(other)
        self.db.flush()
        self.db.add(Membership(user_id=other.id, home_group_id=self.home.id, role="member"))
        batch = ImportBatch(home_group_id=self.home.id, uploaded_by_user_id=self.user.id, filename="visa.pdf", card_network="visa")
        self.db.add(batch)
        self.db.flush()
        line = ImportLine(import_batch_id=batch.id, home_group_id=self.home.id, date=date(2026, 10, 1), description="Compra", kind=ImportLineKind.purchase, currency=Currency.ARS, original_amount=Decimal("1000"), fingerprint="network", raw_text="Compra")
        self.db.add(line)
        self.db.flush()
        expense = self._create("Compra", self.services.id)
        expense.import_line_id = line.id
        expense.source = ExpenseSource.import_pdf
        self.db.commit()
        updated = update_expense(self.home.id, expense.id, ExpenseUpdate(paid_by_user_id=other.id), self.user, self.db)
        self.assertEqual(updated.paid_by_user_id, other.id)
        self.assertEqual(ExpenseRead.model_validate(updated).card_network, "visa")
        self.assertEqual(updated.uploaded_by_user_id, self.user.id)
        with self.assertRaises(HTTPException) as error:
            update_expense(self.home.id, expense.id, ExpenseUpdate(paid_by_user_id=999), self.user, self.db)
        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
