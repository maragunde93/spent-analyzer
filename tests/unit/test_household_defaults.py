import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.households import delete_member, list_members, update_member
from app.database import Base
from app.dev_seed import seed_development_data
from app.domain import Currency, ExpenseSource
from app.models import Category, Expense, HomeGroup, Membership, User
from app.schemas import MemberUpdate


class HouseholdDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_startup_seed_keeps_existing_configuration_and_removes_obsolete_system_categories(self):
        user = User(email="mauro@example.test", display_name="Mauro")
        home = HomeGroup(name="Casa Adrogue")
        self.db.add_all([user, home])
        self.db.flush()
        self.db.add(Membership(user_id=user.id, home_group_id=home.id, role="owner"))
        services = Category(home_group_id=home.id, name="Servicios", color="#ff9800", icon="receipt", is_system=True)
        obsolete = Category(home_group_id=home.id, name="Compras del hogar", color="#2171b5", icon="shopping-cart", is_system=True)
        self.db.add_all([services, obsolete])
        self.db.flush()
        self.db.add(
            Expense(
                home_group_id=home.id,
                date=date(2026, 7, 7),
                description="Compra historica",
                category_id=obsolete.id,
                paid_by_user_id=user.id,
                uploaded_by_user_id=user.id,
                source=ExpenseSource.manual,
                currency=Currency.ARS,
                original_amount=Decimal("100.00"),
                amount_ars=Decimal("100.00"),
            )
        )
        self.db.commit()

        seed_development_data(self.db)

        names = set(self.db.scalars(select(Category.name).where(Category.home_group_id == home.id)))
        expense = self.db.scalar(select(Expense).where(Expense.description == "Compra historica"))

        self.assertIn("Servicios", names)
        self.assertNotIn("Compras del hogar", names)
        self.assertNotIn("Herramientas", names)
        self.assertNotIn("Delivery", names)
        self.assertIsNotNone(expense)
        self.assertIsNone(expense.category_id)

    def test_members_include_consumption_counts(self):
        mauro = User(email="mauro@example.test", display_name="Mauro")
        mica = User(email="mica@example.test", display_name="Mica")
        home = HomeGroup(name="Casa")
        self.db.add_all([mauro, mica, home])
        self.db.flush()
        self.db.add_all([
            Membership(user_id=mauro.id, home_group_id=home.id, role="owner"),
            Membership(user_id=mica.id, home_group_id=home.id, role="member"),
        ])
        self.db.add(
            Expense(
                home_group_id=home.id,
                date=date(2026, 7, 8),
                description="Consumo Mauro",
                paid_by_user_id=mauro.id,
                uploaded_by_user_id=mauro.id,
                source=ExpenseSource.manual,
                currency=Currency.ARS,
                original_amount=Decimal("100.00"),
                amount_ars=Decimal("100.00"),
            )
        )
        self.db.commit()

        members = list_members(home.id, mauro, self.db)

        counts = {member.email: member.consumption_count for member in members}
        self.assertEqual(counts["mauro@example.test"], 1)
        self.assertEqual(counts["mica@example.test"], 0)

    def test_update_member_changes_name_and_email(self):
        mauro = User(email="mauro@example.test", display_name="Mauro")
        mica = User(email="mica@example.test", display_name="Mica")
        home = HomeGroup(name="Casa")
        self.db.add_all([mauro, mica, home])
        self.db.flush()
        self.db.add_all([
            Membership(user_id=mauro.id, home_group_id=home.id, role="owner"),
            Membership(user_id=mica.id, home_group_id=home.id, role="member"),
        ])
        self.db.commit()

        updated = update_member(home.id, mica.id, MemberUpdate(email="mica.real@example.test", display_name="Mica Real"), mauro, self.db)

        self.assertEqual(updated.email, "mica.real@example.test")
        self.assertEqual(updated.display_name, "Mica Real")
        self.assertEqual(self.db.get(User, mica.id).display_name, "Mica Real")

    def test_delete_member_removes_empty_member_and_blocks_members_with_consumptions(self):
        mauro = User(email="mauro@example.test", display_name="Mauro")
        mica = User(email="mica@example.test", display_name="Mica")
        duplicate = User(email="mauro.duplicate@example.test", display_name="Mauro")
        home = HomeGroup(name="Casa")
        self.db.add_all([mauro, mica, duplicate, home])
        self.db.flush()
        self.db.add_all([
            Membership(user_id=mauro.id, home_group_id=home.id, role="owner"),
            Membership(user_id=mica.id, home_group_id=home.id, role="member"),
            Membership(user_id=duplicate.id, home_group_id=home.id, role="member"),
        ])
        self.db.add(
            Expense(
                home_group_id=home.id,
                date=date(2026, 7, 8),
                description="Consumo Mica",
                paid_by_user_id=mica.id,
                uploaded_by_user_id=mauro.id,
                source=ExpenseSource.manual,
                currency=Currency.ARS,
                original_amount=Decimal("100.00"),
                amount_ars=Decimal("100.00"),
            )
        )
        self.db.commit()

        delete_member(home.id, duplicate.id, mauro, self.db)

        self.assertIsNone(
            self.db.scalar(select(Membership).where(Membership.home_group_id == home.id, Membership.user_id == duplicate.id))
        )
        with self.assertRaises(HTTPException) as raised:
            delete_member(home.id, mica.id, mauro, self.db)
        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
