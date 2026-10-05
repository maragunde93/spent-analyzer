import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.imports import router
from app.auth import get_current_user
from app.database import Base, get_db
from app.models import HomeGroup, ImportLine, Membership, User
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


if __name__ == "__main__":
    unittest.main()
