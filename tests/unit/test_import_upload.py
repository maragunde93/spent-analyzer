import sys
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.imports import router
from app.auth import get_current_user
from app.database import Base, get_db
from app.domain import Currency, ExpenseSource, ImportLineKind
from app.models import Expense, HomeGroup, ImportBatch, ImportLine, Membership, User
from app.services.bbva_parser import parse_bbva_visa_text


STATEMENT = """
Visa Signature
cuenta 0000000000
CIERRE ACTUAL VENCIMIENTO ACTUAL
30-Jul-26
Consumos Titular Demo
FECHA DESCRIP
24-Jul-26 OSDE 000000000000001 000885 1.000,00
24-Jul-26 OSDE 000000000000001 000885 1.000,00
24-Jul-26 OSDE 000000000000001 000885 -1.000,00
"""


class ImportUploadTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.user = User(email="demo@example.test", display_name="Titular Demo")
        self.home = HomeGroup(name="Casa Demo")
        self.db.add_all([self.user, self.home])
        self.db.flush()
        self.db.add(Membership(user_id=self.user.id, home_group_id=self.home.id, role="owner"))
        self.db.commit()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def _upload(self, statement=STATEMENT):
        parsed = parse_bbva_visa_text(statement)
        with patch("app.api.imports.parse_bbva_visa_pdf", return_value=parsed):
            response = self.client.post(
                f"/households/{self.home.id}/imports/bbva-visa",
                files={"file": ("statement.pdf", b"sanitized statement", "application/pdf")},
            )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json(), parsed

    def test_equal_card_charges_and_refund_are_all_preserved(self):
        batch, parsed = self._upload()

        lines = list(self.db.scalars(select(ImportLine).order_by(ImportLine.id)))
        self.assertEqual(len(batch["lines"]), 3)
        self.assertEqual([line.original_amount for line in lines], [Decimal("1000"), Decimal("1000"), Decimal("-1000")])
        self.assertEqual([line.fingerprint for line in lines], [
            f"{batch['id']}:{parsed.lines[0].fingerprint}",
            f"{batch['id']}:{parsed.lines[0].fingerprint}:2",
            f"{batch['id']}:{parsed.lines[2].fingerprint}",
        ])
        self.assertTrue(all(line["duplicate_status"] == "new" for line in batch["lines"]))

    def test_mastercard_preserves_three_identical_charges(self):
        statement = STATEMENT.replace("Visa Signature", "Mastercard Black")
        statement = statement.replace("000885 -1.000,00", "000885 1.000,00")
        batch, parsed = self._upload(statement)

        lines = list(self.db.scalars(select(ImportLine).order_by(ImportLine.id)))
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[2].fingerprint, f"{batch['id']}:{parsed.lines[0].fingerprint}:3")
        self.assertEqual(batch["card_network"], "mastercard")

    def test_reupload_matches_each_occurrence_to_its_prior_status(self):
        first, _ = self._upload()
        first_lines = list(self.db.scalars(select(ImportLine).order_by(ImportLine.id)))
        first_lines[0].status = "committed"
        first_lines[2].status = "ignored"
        self.db.commit()

        second, _ = self._upload()

        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(len(second["lines"]), 3)
        self.assertEqual([line["duplicate_status"] for line in second["lines"]], [
            "already_committed", "previously_parsed", "already_committed",
        ])

    def test_coverage_is_compact_and_uses_bounded_queries(self):
        card = ImportBatch(
            home_group_id=self.home.id, uploaded_by_user_id=self.user.id,
            filename="visa.pdf", source_type="bbva_visa_pdf", statement_period="2026-09",
            card_network="visa", status="committed", created_at=datetime(2026, 10, 2),
        )
        account = ImportBatch(
            home_group_id=self.home.id, uploaded_by_user_id=self.user.id,
            filename="cuenta.xls", source_type="bbva_account_xls", status="committed",
            created_at=datetime(2026, 10, 2),
        )
        self.db.add_all([card, account])
        self.db.flush()
        lines = [
            ImportLine(import_batch_id=batch.id, home_group_id=self.home.id, date=line_date,
                       description="Compra", kind=ImportLineKind.purchase, currency=Currency.ARS,
                       original_amount=Decimal("100"), status="committed", fingerprint=f"coverage-{index}", raw_text="Compra")
            for index, (batch, line_date) in enumerate([
                (card, date(2026, 8, 20)), (account, date(2026, 8, 30)), (account, date(2026, 9, 1)),
            ])
        ]
        self.db.add_all(lines)
        self.db.flush()
        self.db.add_all([
            Expense(home_group_id=self.home.id, date=line.date, description="Compra", paid_by_user_id=self.user.id,
                    uploaded_by_user_id=self.user.id, source=ExpenseSource.import_pdf, currency=Currency.ARS,
                    original_amount=Decimal("100"), amount_ars=Decimal("100"), import_line_id=line.id)
            for line in lines
        ])
        self.db.commit()
        home_id = self.home.id

        statements = []
        def count_select(_connection, _cursor, statement, _parameters, _context, _executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", count_select)
        try:
            response = self.client.get(f"/households/{home_id}/imports/coverage")
        finally:
            event.remove(self.engine, "before_cursor_execute", count_select)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertLessEqual(len(statements), 5)
        by_id = {batch["id"]: batch for batch in response.json()}
        self.assertEqual(by_id[card.id]["periods"], ["2026-09"])
        self.assertEqual(by_id[account.id]["periods"], ["2026-08", "2026-09"])
        self.assertEqual(by_id[card.id]["paid_by_user_ids"], [self.user.id])
        self.assertEqual(by_id[account.id]["paid_by_user_ids"], [self.user.id])
        self.assertNotIn("lines", by_id[card.id])


if __name__ == "__main__":
    unittest.main()
