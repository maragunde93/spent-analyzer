import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.dashboard import dashboard
from app.api.expenses import create_expense, delete_expense, list_deleted_expenses, list_expenses, restore_expense, update_expense
from app.api.imports import _duplicate_status_for_line, commit_import
from app.database import Base, ensure_incremental_schema
from app.domain import Currency, ExpenseSource, ImportLineKind
from app.models import AuditLog, CashWalletEntry, Expense, HomeGroup, ImportBatch, ImportLine, Membership, ReceiptImport, User
from app.schemas import ExpenseCreate, ExpenseUpdate, ImportCommitRequest
from app.services.fund import _all_expenses


class ExpenseRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.home = HomeGroup(name="Casa")
        self.user = User(email="test@example.test", display_name="Persona Demo")
        self.db.add_all([self.home, self.user])
        self.db.flush()
        self.db.add(Membership(home_group_id=self.home.id, user_id=self.user.id, role="owner"))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _expense(self, source=ExpenseSource.cash):
        return create_expense(self.home.id, ExpenseCreate(
            date=date(2026, 10, 1), description="Servicio Demo", paid_by_user_id=self.user.id,
            original_amount=Decimal("1500"), source=source, is_recurring=True, is_shared=True,
            notes="Nota conservada",
        ), self.user, self.db)

    def _line(self, batch, fingerprint="charge", kind=ImportLineKind.purchase):
        line = ImportLine(import_batch_id=batch.id, home_group_id=self.home.id, date=date(2026, 10, 1),
                          description="Compra", kind=kind, currency=Currency.ARS, original_amount=Decimal("1500"),
                          status="committed", fingerprint=f"{batch.id}:{fingerprint}", raw_text="Compra")
        self.db.add(line)
        self.db.flush()
        return line

    def _batch(self):
        batch = ImportBatch(home_group_id=self.home.id, uploaded_by_user_id=self.user.id, filename="demo.pdf")
        self.db.add(batch)
        self.db.flush()
        return batch

    def test_trash_excludes_totals_and_restore_preserves_data_and_cash_once(self):
        expense = self._expense()
        self.db.add(ReceiptImport(home_group_id=self.home.id, uploaded_by_user_id=self.user.id,
                                  expense_id=expense.id, filename="ticket.png", status="associated"))
        self.db.commit()
        self.assertEqual(len(list(self.db.scalars(select(CashWalletEntry)))), 1)
        delete_expense(self.home.id, expense.id, self.user, self.db)
        delete_expense(self.home.id, expense.id, self.user, self.db)
        self.assertEqual(list_expenses(self.home.id, search=None, user=self.user, db=self.db), [])
        self.assertEqual([item.id for item in list_deleted_expenses(self.home.id, self.user, self.db)], [expense.id])
        self.assertEqual(list(self.db.scalars(select(CashWalletEntry))), [])
        summary = dashboard(self.home.id, user=self.user, db=self.db)
        self.assertEqual(summary.total_ars, Decimal("0"))
        self.assertEqual(summary.recurring_preview, [])
        self.assertEqual(_all_expenses(self.db, self.home.id)[0], [])
        with self.assertRaises(HTTPException):
            update_expense(self.home.id, expense.id, ExpenseUpdate(notes="No cambiar"), self.user, self.db)
        restored = restore_expense(self.home.id, expense.id, self.user, self.db)
        restore_expense(self.home.id, expense.id, self.user, self.db)
        self.assertEqual(restored.id, expense.id)
        self.assertEqual(restored.notes, "Nota conservada")
        self.assertTrue(restored.is_shared)
        self.assertTrue(restored.is_recurring)
        self.assertIsNone(restored.deleted_at)
        self.assertEqual(self.db.scalar(select(ReceiptImport.expense_id)), expense.id)
        entries = list(self.db.scalars(select(CashWalletEntry)))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].amount, Decimal("-1500"))
        self.assertEqual(dashboard(self.home.id, user=self.user, db=self.db).total_ars, Decimal("1500"))
        self.assertEqual(len(list(self.db.scalars(select(AuditLog).where(AuditLog.action == "expense_restore")))), 1)

    def test_reimport_does_not_restore_trashed_consumption(self):
        batch = self._batch()
        line = self._line(batch)
        expense = self._expense(ExpenseSource.import_pdf)
        expense.import_line_id = line.id
        self.db.commit()
        delete_expense(self.home.id, expense.id, self.user, self.db)
        reupload = self._batch()
        new_line = self._line(reupload)
        new_line.status = "pending"
        self.db.commit()
        self.assertEqual(_duplicate_status_for_line(self.db, new_line), "deleted")
        result = commit_import(self.home.id, reupload.id, ImportCommitRequest(line_ids=[new_line.id], paid_by_user_id=self.user.id), self.user, self.db)
        self.assertEqual(result["created"], 0)
        self.assertIsNotNone(self.db.get(Expense, expense.id).deleted_at)
        self.assertEqual(len(list(self.db.scalars(select(Expense)))), 1)
        restore_expense(self.home.id, expense.id, self.user, self.db)
        self.assertEqual(_duplicate_status_for_line(self.db, new_line), "already_committed")

    def test_old_hard_deleted_consumption_can_be_reimported_but_cash_is_not_duplicated(self):
        original = self._batch()
        self._line(original)
        self._line(original, "withdrawal", ImportLineKind.cash_withdrawal)
        reupload = self._batch()
        line = self._line(reupload)
        line.status = "pending"
        cash = self._line(reupload, "withdrawal", ImportLineKind.cash_withdrawal)
        cash.status = "pending"
        self.db.commit()
        self.assertEqual(_duplicate_status_for_line(self.db, line), "previously_parsed")
        self.assertEqual(_duplicate_status_for_line(self.db, cash), "already_committed")
        result = commit_import(self.home.id, reupload.id, ImportCommitRequest(line_ids=[line.id, cash.id], paid_by_user_id=self.user.id), self.user, self.db)
        self.assertEqual(result["created"], 1)
        self.assertEqual(list(self.db.scalars(select(CashWalletEntry))), [])

    def test_restore_cannot_cross_households(self):
        expense = self._expense()
        delete_expense(self.home.id, expense.id, self.user, self.db)
        other_home = HomeGroup(name="Otra casa")
        self.db.add(other_home)
        self.db.flush()
        self.db.add(Membership(home_group_id=other_home.id, user_id=self.user.id, role="owner"))
        self.db.commit()
        self.assertEqual(list_deleted_expenses(other_home.id, self.user, self.db), [])
        with self.assertRaises(HTTPException) as error:
            restore_expense(other_home.id, expense.id, self.user, self.db)
        self.assertEqual(error.exception.status_code, 404)
        self.assertIsNotNone(self.db.get(Expense, expense.id).deleted_at)

    def test_startup_adds_owner_and_trash_columns_idempotently_to_existing_database(self):
        expense = self._expense()
        expense_id = expense.id
        self.db.close()
        with self.engine.begin() as connection:
            connection.execute(text("ALTER TABLE expenses DROP COLUMN deleted_at"))
            connection.execute(text("ALTER TABLE import_batches DROP COLUMN owner_name"))
        with patch("app.database.engine", self.engine):
            ensure_incremental_schema()
            ensure_incremental_schema()
        self.assertIn("deleted_at", {column["name"] for column in inspect(self.engine).get_columns("expenses")})
        self.assertIn("owner_name", {column["name"] for column in inspect(self.engine).get_columns("import_batches")})
        self.db = Session(self.engine, autoflush=False)
        self.assertIsNone(self.db.get(Expense, expense_id).deleted_at)


if __name__ == "__main__":
    unittest.main()
