import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.imports import commit_import
from app.database import Base
from app.domain import Currency, ImportLineKind
from app.models import Category, Earning, Expense, HomeGroup, ImportBatch, ImportLine, Membership, User
from app.schemas import ImportCommitRequest


class ImportCommitAccountingTests(unittest.TestCase):
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

    def test_bank_outflow_import_creates_positive_expense_and_preserves_notes(self):
        batch = self._batch("bbva_account_xls")
        line = self._line(
            batch,
            "PAGO DE SERVICIOS TARJETA 18073039 OP5056",
            ImportLineKind.debit_purchase,
            Decimal("-36539.00"),
            suggested_category_id=self.services.id,
            suggested_recurring=True,
        )
        self.db.commit()

        commit_import(
            self.home.id,
            batch.id,
            ImportCommitRequest(
                line_ids=[line.id],
                paid_by_user_id=self.user.id,
                note_overrides={line.id: "Factura de luz compartida"},
            ),
            self.user,
            self.db,
        )

        expense = self.db.scalar(select(Expense).where(Expense.import_line_id == line.id))
        self.assertIsNotNone(expense)
        self.assertEqual(expense.original_amount, Decimal("36539.00"))
        self.assertEqual(expense.amount_ars, Decimal("36539.00"))
        self.assertEqual(expense.notes, "Factura de luz compartida")

    def test_bank_titulos_line_is_ignored_instead_of_becoming_service_consumption(self):
        batch = self._batch("bbva_account_xls")
        line = self._line(
            batch,
            "TITULOS 022938914403CUT",
            ImportLineKind.adjustment,
            Decimal("-150000.00"),
            suggested_category_id=self.services.id,
            suggested_recurring=True,
        )
        self.db.commit()

        result = commit_import(
            self.home.id,
            batch.id,
            ImportCommitRequest(line_ids=[line.id], paid_by_user_id=self.user.id),
            self.user,
            self.db,
        )

        self.assertEqual(result["created"], 0)
        self.assertIsNone(self.db.scalar(select(Expense).where(Expense.import_line_id == line.id)))
        self.assertEqual(self.db.get(ImportLine, line.id).status, "ignored")

    def test_reintegrated_recurring_charge_does_not_create_recurring_projection(self):
        batch = self._batch("bbva_visa_pdf")
        charge = self._line(
            batch,
            "COMISION CTA PWORLD",
            ImportLineKind.fee,
            Decimal("57599.00"),
            suggested_category_id=self.services.id,
            suggested_recurring=True,
        )
        reversal = self._line(
            batch,
            "DEV COMISION CTA PWORLD",
            ImportLineKind.refund,
            Decimal("-57599.00"),
            suggested_category_id=self.services.id,
            suggested_recurring=True,
        )
        self.db.commit()

        commit_import(
            self.home.id,
            batch.id,
            ImportCommitRequest(line_ids=[charge.id, reversal.id], paid_by_user_id=self.user.id),
            self.user,
            self.db,
        )

        expenses = list(self.db.scalars(select(Expense).where(Expense.import_line_id.in_([charge.id, reversal.id]))))
        self.assertEqual(len(expenses), 2)
        self.assertTrue(all(not expense.is_recurring for expense in expenses))

    def test_bank_income_can_be_committed_as_reimbursement_negative_consumption(self):
        batch = self._batch("bbva_account_xls")
        line = self._line(
            batch,
            "TRANSFERENCIA AMIGOS COMIDA",
            ImportLineKind.income,
            Decimal("12000.00"),
            suggested_category_id=self.services.id,
        )
        self.db.commit()

        commit_import(
            self.home.id,
            batch.id,
            ImportCommitRequest(
                line_ids=[line.id],
                paid_by_user_id=self.user.id,
                category_overrides={line.id: self.services.id},
                reimbursement_overrides={line.id: True},
            ),
            self.user,
            self.db,
        )

        expense = self.db.scalar(select(Expense).where(Expense.import_line_id == line.id))
        self.assertIsNotNone(expense)
        self.assertEqual(expense.original_amount, Decimal("-12000.00"))
        self.assertEqual(expense.amount_ars, Decimal("-12000.00"))
        self.assertEqual(expense.category_id, self.services.id)
        self.assertFalse(expense.is_recurring)
        self.assertIsNone(self.db.scalar(select(Earning).where(Earning.import_line_id == line.id)))

    def test_rejected_import_line_is_ignored_and_not_created_later(self):
        batch = self._batch("bbva_visa_pdf")
        selected_line = self._line(
            batch,
            "SPOTIFY",
            ImportLineKind.purchase,
            Decimal("4020.00"),
            suggested_category_id=self.services.id,
        )
        rejected_line = self._line(
            batch,
            "NO IMPORTAR",
            ImportLineKind.purchase,
            Decimal("9999.00"),
            suggested_category_id=self.services.id,
        )
        self.db.commit()

        commit_import(
            self.home.id,
            batch.id,
            ImportCommitRequest(
                line_ids=[selected_line.id],
                rejected_line_ids=[rejected_line.id],
                paid_by_user_id=self.user.id,
            ),
            self.user,
            self.db,
        )

        self.assertIsNotNone(self.db.scalar(select(Expense).where(Expense.import_line_id == selected_line.id)))
        self.assertIsNone(self.db.scalar(select(Expense).where(Expense.import_line_id == rejected_line.id)))
        self.assertEqual(self.db.get(ImportLine, rejected_line.id).status, "ignored")

    def _batch(self, source_type: str) -> ImportBatch:
        batch = ImportBatch(
            home_group_id=self.home.id,
            uploaded_by_user_id=self.user.id,
            filename="test",
            source_type=source_type,
        )
        self.db.add(batch)
        self.db.flush()
        return batch

    def _line(
        self,
        batch: ImportBatch,
        description: str,
        kind: ImportLineKind,
        amount: Decimal,
        suggested_category_id: int | None = None,
        suggested_recurring: bool = False,
    ) -> ImportLine:
        line = ImportLine(
            import_batch_id=batch.id,
            home_group_id=self.home.id,
            date=date(2026, 7, 6),
            description=description,
            kind=kind,
            currency=Currency.ARS,
            original_amount=amount,
            suggested_category_id=suggested_category_id,
            suggested_recurring=suggested_recurring,
            fingerprint=f"{batch.id}:{description}:{amount}",
            raw_text=description,
        )
        self.db.add(line)
        self.db.flush()
        return line


if __name__ == "__main__":
    unittest.main()
