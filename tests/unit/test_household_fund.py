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
from app.domain import Currency, ExpenseSource, ImportLineKind
from app.models import (
    Earning,
    Expense,
    FundMonthClosure,
    FundMonthConfig,
    FundManualMovement,
    FundMonthShare,
    FundOpeningBalance,
    HomeGroup,
    ImportBatch,
    ImportLine,
    Membership,
    MercadoPagoIntegration,
    User,
)
from app.services.fund import calculate_fund_summary


class HouseholdFundTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.mauro = User(email="mauro@example.test", display_name="Mauro")
        self.mica = User(email="mica@example.test", display_name="Mica")
        self.home = HomeGroup(name="Casa")
        self.db.add_all([self.mauro, self.mica, self.home])
        self.db.flush()
        self.db.add_all([
            Membership(user_id=self.mauro.id, home_group_id=self.home.id, role="owner"),
            Membership(user_id=self.mica.id, home_group_id=self.home.id, role="member"),
        ])
        config = FundMonthConfig(home_group_id=self.home.id, period="2026-06", monthly_amount=Decimal("4000000"), created_by_user_id=self.mauro.id)
        self.db.add(config)
        self.db.flush()
        self.db.add_all([
            FundMonthShare(config_id=config.id, user_id=self.mauro.id, percentage=Decimal("76")),
            FundMonthShare(config_id=config.id, user_id=self.mica.id, percentage=Decimal("24")),
            FundOpeningBalance(home_group_id=self.home.id, start_date=date(2026, 6, 1), amount=Decimal("0"), created_by_user_id=self.mauro.id),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _expense(self, amount: str, payer: User | None = None, **kwargs) -> Expense:
        expense = Expense(
            home_group_id=self.home.id,
            date=kwargs.pop("expense_date", date(2026, 6, 10)),
            description=kwargs.pop("description", "Gasto compartido"),
            paid_by_user_id=(payer or self.mauro).id,
            uploaded_by_user_id=(payer or self.mauro).id,
            source=kwargs.pop("source", ExpenseSource.manual),
            currency=Currency.ARS,
            original_amount=Decimal(amount),
            amount_ars=Decimal(amount),
            is_shared=kwargs.pop("is_shared", True),
            **kwargs,
        )
        self.db.add(expense)
        self.db.commit()
        return expense

    def test_mauro_3_5m_proposes_460k_reimbursement_and_500k_to_fund(self):
        self._expense("3500000")
        result = calculate_fund_summary(self.db, self.home.id, "2026-06")

        self.assertEqual(result["totals"]["shared_expenses"], "3500000.00")
        self.assertEqual([(row["from_name"], row["to_name"], row["amount"]) for row in result["plan"]], [
            ("Mica", "Mauro", "460000.00"),
            ("Mica", "Fondo común", "500000.00"),
        ])
        self.assertEqual(result["totals"]["agreed_balance"], "500000.00")

    def test_mauro_4m_only_proposes_reimbursement_without_inflating_fund(self):
        self._expense("4000000")
        result = calculate_fund_summary(self.db, self.home.id, "2026-06")

        self.assertEqual(len(result["plan"]), 1)
        self.assertEqual(result["plan"][0]["amount"], "960000.00")
        self.assertEqual(result["plan"][0]["to_name"], "Mauro")
        self.assertEqual(result["totals"]["agreed_balance"], "0.00")

    def test_config_is_inherited_and_excess_uses_the_same_percentages(self):
        self._expense("5000000", expense_date=date(2026, 7, 8))
        result = calculate_fund_summary(self.db, self.home.id, "2026-07")

        self.assertTrue(result["config"]["inherited"])
        self.assertEqual(result["totals"]["financing_base"], "5000000.00")
        self.assertEqual(next(item for item in result["positions"] if item["user_id"] == self.mauro.id)["quota"], "3800000.00")
        self.assertIn("Los gastos superan el fondo configurado por ARS 1.000.000.", result["alerts"])

    def test_excess_zeroes_agreed_balance_without_rewriting_verified_balance(self):
        opening = self.db.query(FundOpeningBalance).filter_by(home_group_id=self.home.id).one()
        opening.amount = Decimal("3900000")
        self._expense("4100000")
        self.db.commit()

        result = calculate_fund_summary(self.db, self.home.id, "2026-06")
        self.assertEqual(result["totals"]["agreed_opening_balance"], "3900000.00")
        self.assertEqual(result["totals"]["agreed_balance"], "0.00")
        self.assertEqual(result["totals"]["verified_balance"], "3900000.00")

    def test_card_uses_statement_period_and_warns_on_fallback(self):
        batch = ImportBatch(home_group_id=self.home.id, uploaded_by_user_id=self.mauro.id, filename="visa.pdf", source_type="bbva_visa_pdf", statement_period="2026-06", status="committed")
        self.db.add(batch)
        self.db.flush()
        line = ImportLine(import_batch_id=batch.id, home_group_id=self.home.id, date=date(2026, 5, 20), description="Compra", kind=ImportLineKind.purchase, currency=Currency.ARS, original_amount=Decimal("1000"), status="committed", fingerprint="card-1", raw_text="Compra")
        self.db.add(line)
        self.db.flush()
        self._expense("1000", expense_date=date(2026, 5, 20), source=ExpenseSource.import_pdf, import_line_id=line.id)

        june = calculate_fund_summary(self.db, self.home.id, "2026-06")
        may = calculate_fund_summary(self.db, self.home.id, "2026-05")
        self.assertEqual(june["totals"]["shared_expenses"], "1000.00")
        self.assertFalse(any("no tienen período" in alert for alert in june["alerts"]))
        self.assertFalse(may["activated"])

    def test_common_mp_account_tracks_contributors_without_crediting_token_owner(self):
        integration = MercadoPagoIntegration(home_group_id=self.home.id, user_id=self.mauro.id, access_token="secret", fund_role="fondo_comun")
        self.db.add(integration)
        self.db.flush()
        batch = ImportBatch(home_group_id=self.home.id, uploaded_by_user_id=self.mauro.id, filename="mp.csv", source_type="mercadopago_account_money", status="committed")
        self.db.add(batch)
        self.db.flush()
        purchase = ImportLine(import_batch_id=batch.id, home_group_id=self.home.id, date=date(2026, 6, 5), description="Compra común", kind=ImportLineKind.purchase, currency=Currency.ARS, original_amount=Decimal("15000"), status="committed", fingerprint="mp-purchase", raw_text="{}")
        income = ImportLine(import_batch_id=batch.id, home_group_id=self.home.id, date=date(2026, 6, 3), description="Ingreso", kind=ImportLineKind.income, currency=Currency.ARS, original_amount=Decimal("10000"), status="committed", fingerprint="mp-income", raw_text="{}")
        self.db.add_all([purchase, income])
        self.db.flush()
        self._expense("15000", source=ExpenseSource.mercadopago, import_line_id=purchase.id)
        self.db.add(Earning(home_group_id=self.home.id, date=date(2026, 6, 3), description="Ingreso", user_id=self.mauro.id, uploaded_by_user_id=self.mauro.id, currency=Currency.ARS, original_amount=Decimal("10000"), amount_ars=Decimal("10000"), import_line_id=income.id))
        self.db.commit()

        result = calculate_fund_summary(self.db, self.home.id, "2026-06")
        mauro = next(item for item in result["positions"] if item["user_id"] == self.mauro.id)
        self.assertEqual(mauro["direct_paid"], "0.00")
        self.assertEqual(result["totals"]["verified_balance"], "-5000.00")
        self.assertEqual(result["mp_contributions"][0]["classification"], "pending")
        income.mercadopago_origin_id = "payer_document:dni:test"
        self.db.commit()
        refreshed = calculate_fund_summary(self.db, self.home.id, "2026-06")
        self.assertEqual(refreshed["mp_contributions"][0]["stable_origin_id"], "payer_document:dni:test")
        self.assertTrue(refreshed["mp_contributions"][0]["can_remember_origin"])

    def test_personal_purchase_in_common_mp_account_requires_owner_repayment(self):
        integration = MercadoPagoIntegration(home_group_id=self.home.id, user_id=self.mauro.id, access_token="secret", fund_role="fondo_comun")
        self.db.add(integration)
        self.db.flush()
        batch = ImportBatch(home_group_id=self.home.id, uploaded_by_user_id=self.mauro.id, filename="mp.csv", source_type="mercadopago_account_money", status="committed")
        self.db.add(batch)
        self.db.flush()
        line = ImportLine(import_batch_id=batch.id, home_group_id=self.home.id, date=date(2026, 6, 5), description="Compra personal", kind=ImportLineKind.purchase, currency=Currency.ARS, original_amount=Decimal("2000"), status="committed", fingerprint="mp-personal", raw_text="{}")
        self.db.add(line)
        self.db.flush()
        self._expense("2000", payer=self.mica, source=ExpenseSource.mercadopago, import_line_id=line.id, is_shared=False)

        initial = calculate_fund_summary(self.db, self.home.id, "2026-06")
        self.assertEqual(initial["totals"]["shared_expenses"], "0.00")
        self.assertEqual(initial["totals"]["personal_outflows"], "2000.00")
        self.assertEqual(initial["totals"]["personal_to_repay"], "2000.00")
        self.assertEqual(initial["totals"]["verified_balance"], "-2000.00")
        self.assertEqual(next(row for row in initial["positions"] if row["user_id"] == self.mauro.id)["personal_to_repay"], "2000.00")
        self.assertEqual(len([row for row in initial["plan"] if row.get("reason") == "personal_mp_outflow"]), 1)

        self.db.add(FundManualMovement(home_group_id=self.home.id, date=date(2026, 6, 20), from_user_id=self.mauro.id, to_user_id=None, amount=Decimal("2000"), created_by_user_id=self.mauro.id))
        self.db.commit()
        repaid = calculate_fund_summary(self.db, self.home.id, "2026-06")
        self.assertEqual(repaid["totals"]["personal_to_repay"], "0.00")
        self.assertEqual(repaid["totals"]["verified_balance"], "0.00")
        self.assertEqual(next(row for row in repaid["positions"] if row["user_id"] == self.mauro.id)["contributed"], "0.00")
        self.assertFalse(any(row.get("reason") == "personal_mp_outflow" for row in repaid["plan"]))

        self.db.add(FundMonthClosure(home_group_id=self.home.id, period="2026-06", status="cerrado", snapshot=repaid, input_hash=repaid["input_hash"], agreed_closing_balance=Decimal(repaid["totals"]["agreed_balance"]), created_by_user_id=self.mauro.id))
        self.db.commit()
        line_expense = self.db.query(Expense).filter_by(import_line_id=line.id).one()
        line_expense.is_shared = True
        self.db.commit()
        self.assertEqual(calculate_fund_summary(self.db, self.home.id, "2026-06")["status"], "desactualizado")

    def test_closed_month_is_marked_stale_when_an_input_changes(self):
        expense = self._expense("3500000")
        original = calculate_fund_summary(self.db, self.home.id, "2026-06")
        self.db.add(FundMonthClosure(home_group_id=self.home.id, period="2026-06", status="cerrado", snapshot=original, input_hash=original["input_hash"], agreed_closing_balance=Decimal("500000"), created_by_user_id=self.mauro.id))
        self.db.commit()
        expense.amount_ars = Decimal("3600000")
        self.db.commit()

        changed = calculate_fund_summary(self.db, self.home.id, "2026-06")
        self.assertEqual(changed["status"], "desactualizado")


if __name__ == "__main__":
    unittest.main()
