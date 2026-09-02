import sys
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.database import Base
from app.domain import Currency, ExpenseSource, ImportLineKind
from app.models import Category, Earning, Expense, HomeGroup, ImportLine, Membership, MercadoPagoIntegration, Merchant, User
from app.api import mercadopago as mercadopago_api
from app.services.mercadopago import MercadoPagoReport, parse_report_csv, sync_integration


class FakeMercadoPagoClient:
    def __init__(self, content: bytes, fail_download: bool = False):
        self.content = content
        self.fail_download = fail_download
        self.create_calls = 0
        self.download_calls = 0

    async def create_report(self, begin: datetime, end: datetime):
        self.create_calls += 1
        return {"file_name": "settlement-report-test.csv"}

    async def wait_for_report(self, begin: datetime, end: datetime, created_response, poll_interval_seconds: float, timeout_seconds: float):
        return MercadoPagoReport("settlement-report-test.csv", created_response)

    async def download_report(self, file_name: str):
        self.download_calls += 1
        if self.fail_download:
            raise RuntimeError("api temporalmente caida")
        return self.content


class FakeIdentityClient:
    should_fail = False

    def __init__(self, access_token: str, api_base_url: str, identity_base_url: str):
        self.access_token = access_token

    async def validate_token(self):
        if self.should_fail:
            raise mercadopago_api.MercadoPagoError("Token de Mercado Pago invalido")
        return SimpleNamespace(mp_user_id="123456", nickname="mauro-mp", site_id="MLA")


class MercadoPagoSyncTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(email="mauro@example.test", display_name="Mauro")
        self.other_user = User(email="mica@example.test", display_name="Mica")
        self.home = HomeGroup(name="Casa")
        self.db.add_all([self.user, self.other_user, self.home])
        self.db.flush()
        self.db.add_all([
            Membership(user_id=self.user.id, home_group_id=self.home.id, role="owner"),
            Membership(user_id=self.other_user.id, home_group_id=self.home.id, role="member"),
        ])
        self.delivery = Category(home_group_id=self.home.id, name="Delivery", color="#41b6e6", icon="utensils")
        self.db.add(self.delivery)
        self.db.flush()
        self.integration = MercadoPagoIntegration(
            home_group_id=self.home.id,
            user_id=self.other_user.id,
            mp_user_id="123456",
            access_token="APP_USR-secret",
        )
        self.db.add(self.integration)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    async def test_parser_classifies_balance_transfer_income_refund_and_card_ignored(self):
        movements = parse_report_csv(_csv_bytes())

        self.assertEqual([movement.kind for movement in movements], [
            ImportLineKind.purchase,
            ImportLineKind.transfer,
            ImportLineKind.income,
            ImportLineKind.reimbursement,
            ImportLineKind.card_payment,
        ])
        self.assertEqual(movements[0].amount, Decimal("4500.00"))
        self.assertEqual(movements[3].amount, Decimal("-1200.00"))
        self.assertEqual(movements[4].ignored_reason, "Operacion financiada con tarjeta vinculada")

    async def test_sync_imports_supported_movements_maps_user_and_is_idempotent(self):
        now = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
        result = await sync_integration(
            self.db,
            self.integration,
            client=FakeMercadoPagoClient(_csv_bytes()),
            poll_interval_seconds=0,
            poll_timeout_seconds=1,
            now=now,
        )

        self.assertEqual(result.imported, 4)
        self.assertEqual(result.ignored, 1)
        self.assertEqual(result.duplicates, 0)
        expenses = list(self.db.scalars(select(Expense).where(Expense.source == ExpenseSource.mercadopago).order_by(Expense.description)))
        earnings = list(self.db.scalars(select(Earning)))
        ignored = self.db.scalar(select(ImportLine).where(ImportLine.kind == ImportLineKind.card_payment))
        self.assertEqual(len(expenses), 3)
        self.assertEqual(len(earnings), 1)
        self.assertTrue(all(expense.paid_by_user_id == self.other_user.id for expense in expenses))
        self.assertEqual(earnings[0].user_id, self.other_user.id)
        self.assertEqual(ignored.status, "ignored")
        self.assertEqual(self.integration.last_sync_at, now.replace(tzinfo=None))

        second = await sync_integration(
            self.db,
            self.integration,
            client=FakeMercadoPagoClient(_csv_bytes()),
            poll_interval_seconds=0,
            poll_timeout_seconds=1,
            now=now,
        )

        self.assertEqual(second.imported, 0)
        self.assertEqual(second.ignored, 0)
        self.assertEqual(second.duplicates, 5)
        self.assertEqual(len(list(self.db.scalars(select(Expense).where(Expense.source == ExpenseSource.mercadopago)))), 3)
        self.assertEqual(len(list(self.db.scalars(select(Earning)))), 1)

    async def test_sync_does_not_advance_last_sync_at_when_download_fails(self):
        original_last_sync_at = self.integration.last_sync_at

        with self.assertRaises(RuntimeError):
            await sync_integration(
                self.db,
                self.integration,
                client=FakeMercadoPagoClient(_csv_bytes(), fail_download=True),
                poll_interval_seconds=0,
                poll_timeout_seconds=1,
                now=datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc),
            )

        self.assertEqual(self.integration.last_sync_at, original_last_sync_at)

    async def test_sync_uses_merchant_learning_for_category(self):
        self.db.add(
            Merchant(
                home_group_id=self.home.id,
                display_name="PEDIDOSYA MARKET",
                normalized_name="PEDIDOSYA MARKET - ACCOUNT_MONEY - PAYMENT",
                category_id=self.delivery.id,
            )
        )
        self.db.commit()

        await sync_integration(
            self.db,
            self.integration,
            client=FakeMercadoPagoClient(_csv_bytes()),
            poll_interval_seconds=0,
            poll_timeout_seconds=1,
            now=datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc),
        )

        expense = self.db.scalar(select(Expense).where(Expense.description.like("PEDIDOSYA%")))
        self.assertEqual(expense.category_id, self.delivery.id)

    async def test_api_connect_replaces_token_without_returning_it_and_disconnects(self):
        original_client = mercadopago_api.MercadoPagoClient
        mercadopago_api.MercadoPagoClient = FakeIdentityClient
        try:
            read = await mercadopago_api.upsert_integration(
                self.home.id,
                self.user.id,
                mercadopago_api.MercadoPagoTokenUpdate(access_token="APP_USR-new-token"),
                self.user,
                self.db,
            )
        finally:
            mercadopago_api.MercadoPagoClient = original_client

        integration = self.db.scalar(
            select(MercadoPagoIntegration).where(
                MercadoPagoIntegration.home_group_id == self.home.id,
                MercadoPagoIntegration.user_id == self.user.id,
            )
        )
        self.assertTrue(read.connected)
        self.assertEqual(read.mp_user_id, "123456")
        self.assertFalse(hasattr(read, "access_token"))
        self.assertEqual(integration.access_token, "APP_USR-new-token")

        result = mercadopago_api.delete_integration(self.home.id, self.user.id, self.user, self.db)
        self.assertEqual(result, {"ok": True})
        self.assertIsNone(
            self.db.scalar(
                select(MercadoPagoIntegration).where(
                    MercadoPagoIntegration.home_group_id == self.home.id,
                    MercadoPagoIntegration.user_id == self.user.id,
                )
            )
        )

    async def test_api_rejects_invalid_token(self):
        original_client = mercadopago_api.MercadoPagoClient
        FakeIdentityClient.should_fail = True
        mercadopago_api.MercadoPagoClient = FakeIdentityClient
        try:
            with self.assertRaises(HTTPException) as raised:
                await mercadopago_api.upsert_integration(
                    self.home.id,
                    self.user.id,
                    mercadopago_api.MercadoPagoTokenUpdate(access_token="APP_USR-bad-token"),
                    self.user,
                    self.db,
                )
        finally:
            FakeIdentityClient.should_fail = False
            mercadopago_api.MercadoPagoClient = original_client

        self.assertEqual(raised.exception.status_code, 400)


def _csv_bytes() -> bytes:
    return (
        "EXTERNAL_REFERENCE;SOURCE_ID;USER_ID;PAYMENT_METHOD_TYPE;PAYMENT_METHOD;SITE;TRANSACTION_TYPE;TRANSACTION_AMOUNT;TRANSACTION_CURRENCY;TRANSACTION_DATE;REAL_AMOUNT\n"
        "PEDIDOSYA MARKET;SRC-001;123456;account_money;account_money;MLA;PAYMENT;-4500.00;ARS;2026-08-25T10:15:00.000-03:00;-4500.00\n"
        "MP-002;SRC-002;123456;account_money;account_money;MLA;TRANSFER;-15000.00;ARS;2026-08-25T11:15:00.000-03:00;-15000.00\n"
        "MP-003;SRC-003;123456;account_money;account_money;MLA;TRANSFER;23000.00;ARS;2026-08-25T12:15:00.000-03:00;23000.00\n"
        "MP-004;SRC-004;123456;account_money;account_money;MLA;REFUND;1200.00;ARS;2026-08-25T13:15:00.000-03:00;1200.00\n"
        "MP-005;SRC-005;123456;credit_card;visa;MLA;PAYMENT;-9999.00;ARS;2026-08-25T14:15:00.000-03:00;-9999.00\n"
    ).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
