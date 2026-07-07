import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.database import Base
from app.domain import Currency, ExpenseSource
from app.models import Category, Expense, Subcategory
from app.services.merchant_learning import find_learned_suggestion, learn_from_expense, normalize_merchant_name
from app.services.recurring import should_suggest_recurring


class MerchantLearningTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_installment_number_is_ignored_for_learning_key(self):
        self.assertEqual(
            normalize_merchant_name("MERPAGO*TADA C.01/06"),
            normalize_merchant_name("MERPAGO*TADA C.02/06"),
        )
        self.assertEqual(
            normalize_merchant_name("COMPRA DEMO 01/06"),
            normalize_merchant_name("COMPRA DEMO 02/06"),
        )

    def test_learns_category_subcategory_and_recurring_for_next_installment(self):
        category = Category(home_group_id=1, name="Servicios", color="#ff9800", icon="receipt")
        subcategory = Subcategory(home_group_id=1, category_id=1, name="Electricidad")
        self.db.add(category)
        self.db.flush()
        subcategory.category_id = category.id
        self.db.add(subcategory)
        self.db.flush()

        expense = Expense(
            home_group_id=1,
            date=date(2026, 7, 6),
            description="EDESUR C.01/06",
            category_id=category.id,
            subcategory_id=subcategory.id,
            paid_by_user_id=1,
            uploaded_by_user_id=1,
            source=ExpenseSource.import_pdf,
            currency=Currency.ARS,
            original_amount=Decimal("1000.00"),
            amount_ars=Decimal("1000.00"),
            is_recurring=True,
        )
        self.db.add(expense)
        self.db.flush()
        learn_from_expense(self.db, expense)

        learned = find_learned_suggestion(self.db, 1, "EDESUR C.02/06")

        self.assertIsNotNone(learned)
        self.assertEqual(learned.category_id, category.id)
        self.assertEqual(learned.subcategory_id, subcategory.id)
        self.assertTrue(learned.is_recurring)

    def test_services_are_recurring_by_default(self):
        category = Category(home_group_id=1, name="Servicios", color="#ff9800", icon="receipt")
        self.db.add(category)
        self.db.flush()

        self.assertTrue(should_suggest_recurring(self.db, 1, "EDESUR FACTURA", category.id))


if __name__ == "__main__":
    unittest.main()
