import asyncio
import sys
import unittest
from unittest.mock import patch
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.database import Base
from app.domain import Currency, ExpenseSource, ImportLineKind
from app.models import Category, Earning, Expense, HomeGroup, ImportLine, Membership, MercadoPagoIntegration, MercadoPagoMerchantRule, Merchant, User
from app.api import mercadopago as mercadopago_api
from app.api.expenses import delete_expense, update_expense
from app.schemas import ExpenseUpdate
from app.services.mercadopago import (
    MercadoPagoClient,
    MercadoPagoNotFoundError,
    MercadoPagoReport,
    MercadoPagoTemporaryError,
    _description_from_payment,
    _merchant_identity_from_payment,
    claim_mercadopago_sync,
    execute_mercadopago_sync_job,
    parse_report_csv,
    recover_interrupted_mercadopago_syncs,
    sync_integration,
)


class FakeMercadoPagoClient:
    def __init__(self, content: bytes, fail_download: bool = False, payments: dict[str, dict] | None = None):
        self.content = content
        self.fail_download = fail_download
        self.payments = payments or {}
        self.create_calls = 0
        self.download_calls = 0
        self.payment_calls = []
        self.ensure_config_calls = 0
        self.created_begin = None
        self.created_end = None

    async def ensure_report_config(self, mp_user_id: str | None = None):
        self.ensure_config_calls += 1
        return {}

    async def create_report(self, begin: datetime, end: datetime):
        self.create_calls += 1
        self.created_begin = begin
        self.created_end = end
        return {"file_name": "settlement-report-test.csv"}

    async def wait_for_report(self, begin: datetime, end: datetime, created_response, poll_interval_seconds: float, timeout_seconds: float):
        return MercadoPagoReport("settlement-report-test.csv", created_response)

    async def download_report(self, file_name: str):
        self.download_calls += 1
        if self.fail_download:
            raise RuntimeError("api temporalmente caida")
        return self.content

    async def get_payment(self, payment_id: str):
        self.payment_calls.append(payment_id)
        return self.payments.get(payment_id)


class TimedOutMercadoPagoClient(FakeMercadoPagoClient):
    async def wait_for_report(self, begin: datetime, end: datetime, created_response, poll_interval_seconds: float, timeout_seconds: float):
        raise MercadoPagoTemporaryError("El reporte de Mercado Pago no estuvo listo antes del timeout")


class FakeIdentityClient:
    should_fail = False

    def __init__(
        self,
        access_token: str,
        api_base_url: str,
        identity_base_url: str,
        debug_http: bool = False,
        debug_http_max_chars: int = 12000,
    ):
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
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
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
        client = FakeMercadoPagoClient(_csv_bytes())
        result = await sync_integration(
            self.db,
            self.integration,
            client=client,
            poll_interval_seconds=0,
            poll_timeout_seconds=1,
            now=now,
        )

        self.assertEqual(result.imported, 4)
        self.assertEqual(client.ensure_config_calls, 1)
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
        self.assertEqual(client.created_end, now)
        self.assertLessEqual(client.created_end, now)

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

    async def test_backfill_range_imports_without_advancing_last_sync_cursor(self):
        original_last_sync_at = datetime(2026, 8, 28, 12, 0)
        self.integration.last_sync_at = original_last_sync_at
        self.db.commit()
        client = FakeMercadoPagoClient(_csv_bytes())

        result = await sync_integration(
            self.db,
            self.integration,
            client=client,
            poll_interval_seconds=0,
            poll_timeout_seconds=1,
            now=datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc),
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            advance_cursor=False,
        )

        self.assertEqual(result.imported, 4)
        self.assertEqual(result.begin_date, "2026-08-01T00:00:00Z")
        self.assertEqual(result.end_date, "2026-08-31T23:59:59.999999Z")
        self.assertEqual(self.integration.last_sync_at, original_last_sync_at)
        self.assertEqual(client.created_begin.date(), date(2026, 8, 1))
        self.assertEqual(client.created_end.date(), date(2026, 8, 31))

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

    async def test_sync_enriches_payment_names_and_payout_fallbacks(self):
        client = FakeMercadoPagoClient(
            _csv_bytes_with_order_and_payout(),
            payments={
                "175294418333": {
                    "description": "Ferreteriagabriel",
                    "external_reference": "INSTORE-7a285763-0b1a-4b31-b7a7-5a93cd47a1fd",
                    "collector": {"id": 632303369},
                    "store_id": "34130551",
                },
            },
        )

        await sync_integration(
            self.db,
            self.integration,
            client=client,
            poll_interval_seconds=0,
            poll_timeout_seconds=1,
            now=datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc),
        )

        descriptions = [expense.description for expense in self.db.scalars(select(Expense).order_by(Expense.original_amount))]
        self.assertIn("Ferreteriagabriel", descriptions)
        self.assertIn("Transferencia enviada", descriptions)
        self.assertEqual(client.payment_calls, ["175294418333"])
        instore = self.db.scalar(select(Expense).where(Expense.description == "Ferreteriagabriel"))
        payout = self.db.scalar(select(Expense).where(Expense.description == "Transferencia enviada"))
        self.assertIsNone(instore.notes)
        self.assertIsNone(payout.notes)
        line = self.db.get(ImportLine, instore.import_line_id)
        self.assertEqual(line.mercadopago_merchant_key, "collector:632303369")
        self.assertEqual(line.mercadopago_store_id, "34130551")

    async def test_payment_enrichment_uses_idempotency_key_merchant_fallback(self):
        description = _description_from_payment(
            {
                "description": None,
                "idempotency_key": "idempotencyKeyPostPay_TELEPASE-459095281-account_money-1-prod_1945000207238192",
                "point_of_interaction": {"business_info": {"branch": "Transport - Tolls paygo"}},
            },
            {
                "TRANSACTION_TYPE": "SETTLEMENT",
                "PAYMENT_METHOD_TYPE": "available_money",
                "REAL_AMOUNT": "-1192.99",
            },
        )

        self.assertEqual(description, "TELEPASE")

    async def test_resync_updates_existing_generic_mercadopago_description(self):
        await sync_integration(
            self.db,
            self.integration,
            client=FakeMercadoPagoClient(_csv_bytes_with_order_and_payout()),
            poll_interval_seconds=0,
            poll_timeout_seconds=1,
            now=datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc),
        )
        self.assertIsNotNone(self.db.scalar(select(Expense).where(Expense.description == "Pago en tienda fisica")))

        result = await sync_integration(
            self.db,
            self.integration,
            client=FakeMercadoPagoClient(
                _csv_bytes_with_order_and_payout(),
                payments={"175294418333": {"description": "Ferreteria Lanin"}},
            ),
            poll_interval_seconds=0,
            poll_timeout_seconds=1,
            now=datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(result.imported, 0)
        self.assertEqual(result.duplicates, 2)
        self.assertIsNotNone(self.db.scalar(select(Expense).where(Expense.description == "Ferreteria Lanin")))
        self.assertEqual(len(list(self.db.scalars(select(Expense)))), 2)

    async def test_deleted_mercadopago_expense_can_be_reimported(self):
        await sync_integration(
            self.db,
            self.integration,
            client=FakeMercadoPagoClient(_csv_bytes_with_order_and_payout()),
            poll_interval_seconds=0,
            poll_timeout_seconds=1,
            now=datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc),
        )
        deleted = self.db.scalar(select(Expense).where(Expense.description == "Pago en tienda fisica"))
        deleted_id = deleted.id
        deleted_line_id = deleted.import_line_id

        result = delete_expense(self.home.id, deleted_id, self.user, self.db)

        self.assertEqual(result, {"ok": True})
        self.assertIsNone(self.db.get(Expense, deleted_id))
        self.assertIsNone(self.db.get(ImportLine, deleted_line_id))

        resync = await sync_integration(
            self.db,
            self.integration,
            client=FakeMercadoPagoClient(_csv_bytes_with_order_and_payout()),
            poll_interval_seconds=0,
            poll_timeout_seconds=1,
            now=datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(resync.imported, 1)
        self.assertEqual(resync.duplicates, 1)
        self.assertIsNotNone(self.db.scalar(select(Expense).where(Expense.description == "Pago en tienda fisica")))
        self.assertEqual(len(list(self.db.scalars(select(Expense)))), 2)

    async def test_stale_mercadopago_import_line_without_expense_is_reimported(self):
        await sync_integration(
            self.db,
            self.integration,
            client=FakeMercadoPagoClient(_csv_bytes_with_order_and_payout()),
            poll_interval_seconds=0,
            poll_timeout_seconds=1,
            now=datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc),
        )
        deleted = self.db.scalar(select(Expense).where(Expense.description == "Pago en tienda fisica"))
        stale_line_id = deleted.import_line_id
        self.db.delete(deleted)
        self.db.commit()

        self.assertIsNotNone(self.db.get(ImportLine, stale_line_id))
        self.assertIsNone(self.db.scalar(select(Expense).where(Expense.import_line_id == stale_line_id)))

        resync = await sync_integration(
            self.db,
            self.integration,
            client=FakeMercadoPagoClient(_csv_bytes_with_order_and_payout()),
            poll_interval_seconds=0,
            poll_timeout_seconds=1,
            now=datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(resync.imported, 1)
        self.assertEqual(resync.duplicates, 1)
        self.assertIsNotNone(self.db.scalar(select(Expense).where(Expense.description == "Pago en tienda fisica")))
        self.assertEqual(len(list(self.db.scalars(select(Expense)))), 2)

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

    async def test_api_rejects_range_sync_without_end_date(self):
        with self.assertRaises(HTTPException) as raised:
            await mercadopago_api.sync_now(
                self.home.id,
                self.integration.user_id,
                mercadopago_api.MercadoPagoSyncRequest(start_date=date(2026, 8, 1)),
                self.other_user,
                self.db,
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, "Para sincronizar un rango, completa las fechas Desde y Hasta")

    async def test_api_rejects_managing_another_users_integration(self):
        with self.assertRaises(HTTPException) as raised:
            await mercadopago_api.sync_now(
                self.home.id,
                self.integration.user_id,
                None,
                self.user,
                self.db,
            )
        self.assertEqual(raised.exception.status_code, 403)

    async def test_integration_listing_exposes_only_current_user(self):
        own_view = mercadopago_api.list_integrations(self.home.id, self.user, self.db)
        owner_view = mercadopago_api.list_integrations(self.home.id, self.other_user, self.db)

        self.assertEqual(len(own_view), 1)
        self.assertEqual(own_view[0].user_id, self.user.id)
        self.assertFalse(own_view[0].connected)
        self.assertEqual(len(owner_view), 1)
        self.assertEqual(owner_view[0].user_id, self.other_user.id)
        self.assertTrue(owner_view[0].connected)

    async def test_running_sync_blocks_token_replacement_and_disconnect(self):
        self.integration.last_sync_status = "running"
        self.db.commit()

        with self.assertRaises(HTTPException) as replace_error:
            await mercadopago_api.upsert_integration(
                self.home.id,
                self.other_user.id,
                mercadopago_api.MercadoPagoTokenUpdate(access_token="APP_USR-replacement-token"),
                self.other_user,
                self.db,
            )
        self.assertEqual(replace_error.exception.status_code, 409)

        with self.assertRaises(HTTPException) as disconnect_error:
            mercadopago_api.delete_integration(self.home.id, self.other_user.id, self.other_user, self.db)
        self.assertEqual(disconnect_error.exception.status_code, 409)

    async def test_sync_endpoint_returns_immediately_and_rejects_overlap(self):
        started = asyncio.Event()
        release = asyncio.Event()

        async def fake_job(*args, **kwargs):
            started.set()
            await release.wait()

        original_job = mercadopago_api.execute_mercadopago_sync_job
        mercadopago_api.execute_mercadopago_sync_job = fake_job
        try:
            accepted = await mercadopago_api.sync_now(
                self.home.id,
                self.integration.user_id,
                None,
                self.other_user,
                self.db,
            )
            await started.wait()
            self.assertEqual(accepted.status, "running")
            self.db.refresh(self.integration)
            self.assertEqual(self.integration.last_sync_status, "running")
            with self.assertRaises(HTTPException) as raised:
                await mercadopago_api.sync_now(
                    self.home.id,
                    self.integration.user_id,
                    None,
                    self.other_user,
                    self.db,
                )
            self.assertEqual(raised.exception.status_code, 409)
        finally:
            release.set()
            await asyncio.sleep(0)
            mercadopago_api.execute_mercadopago_sync_job = original_job

    async def test_interrupted_running_sync_is_recovered(self):
        self.integration.last_sync_status = "running"
        self.db.commit()
        self.assertEqual(recover_interrupted_mercadopago_syncs(self.db), 1)
        self.db.refresh(self.integration)
        self.assertEqual(self.integration.last_sync_status, "error")
        self.assertIn("interrumpida", self.integration.last_sync_error)

    async def test_report_matching_uses_created_id_and_rejects_covering_fallback(self):
        client = MercadoPagoClient("APP_USR-secret")
        begin = datetime(2026, 9, 16, 3, 0, tzinfo=timezone.utc)
        end = datetime(2026, 9, 18, 2, 59, 59, tzinfo=timezone.utc)
        exact = {
            "id": 103211754,
            "begin_date": begin.isoformat(),
            "end_date": end.isoformat(),
            "status": "pending",
        }
        older_covering = {
            "id": 103025772,
            "begin_date": "2026-06-02T03:00:00Z",
            "end_date": "2026-09-20T02:59:59Z",
            "status": "processed",
            "file_name": "older.csv",
        }

        self.assertIs(client._matching_report([older_covering, exact], begin, end, report_id="103211754"), exact)
        self.assertIsNone(client._matching_report([older_covering], begin, end))
        self.assertIs(client._matching_report([older_covering, exact], begin, end), exact)

    async def test_background_job_persists_success_counts(self):
        fake_client = FakeMercadoPagoClient(_csv_bytes())
        self.assertTrue(claim_mercadopago_sync(self.db, self.integration.id))
        with patch("app.services.mercadopago.MercadoPagoClient", return_value=fake_client):
            await execute_mercadopago_sync_job(
                self.session_factory,
                self.integration.id,
                api_base_url="https://api.mercadopago.test",
                identity_base_url="https://identity.mercadopago.test",
                overlap_days=3,
                poll_interval_seconds=0,
                poll_timeout_seconds=1,
            )

        self.db.expire_all()
        integration = self.db.get(MercadoPagoIntegration, self.integration.id)
        self.assertEqual(integration.last_sync_status, "ok")
        self.assertEqual(integration.last_sync_imported, 4)
        self.assertEqual(integration.last_sync_ignored, 1)
        self.assertEqual(integration.last_sync_duplicates, 0)
        self.assertIsNotNone(integration.last_sync_completed_at)
        self.assertEqual(integration.last_report_file_name, "settlement-report-test.csv")

    async def test_background_job_persists_failure(self):
        fake_client = FakeMercadoPagoClient(_csv_bytes(), fail_download=True)
        self.assertTrue(claim_mercadopago_sync(self.db, self.integration.id))
        with patch("app.services.mercadopago.MercadoPagoClient", return_value=fake_client):
            await execute_mercadopago_sync_job(
                self.session_factory,
                self.integration.id,
                api_base_url="https://api.mercadopago.test",
                identity_base_url="https://identity.mercadopago.test",
                overlap_days=3,
                poll_interval_seconds=0,
                poll_timeout_seconds=1,
            )

        self.db.expire_all()
        integration = self.db.get(MercadoPagoIntegration, self.integration.id)
        self.assertEqual(integration.last_sync_status, "error")
        self.assertIn("temporalmente caida", integration.last_sync_error)
        self.assertIsNotNone(integration.last_sync_completed_at)

    async def test_background_job_persists_report_timeout(self):
        fake_client = TimedOutMercadoPagoClient(_csv_bytes())
        self.assertTrue(claim_mercadopago_sync(self.db, self.integration.id))
        with patch("app.services.mercadopago.MercadoPagoClient", return_value=fake_client):
            await execute_mercadopago_sync_job(
                self.session_factory,
                self.integration.id,
                api_base_url="https://api.mercadopago.test",
                identity_base_url="https://identity.mercadopago.test",
                overlap_days=3,
                poll_interval_seconds=0,
                poll_timeout_seconds=180,
            )

        self.db.expire_all()
        integration = self.db.get(MercadoPagoIntegration, self.integration.id)
        self.assertEqual(integration.last_sync_status, "error")
        self.assertIn("timeout", integration.last_sync_error)
        self.assertIsNotNone(integration.last_sync_completed_at)

    async def test_merchant_identity_learning_applies_to_future_imports_only(self):
        first_client = FakeMercadoPagoClient(
            _csv_bytes_for_merchant("180000001", "2026-09-01T10:00:00.000-03:00"),
            payments={"180000001": {"description": "Varios", "collector": {"id": 777}, "store_id": "10"}},
        )
        await sync_integration(
            self.db,
            self.integration,
            client=first_client,
            poll_interval_seconds=0,
            poll_timeout_seconds=1,
            now=datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc),
        )
        first = self.db.scalar(select(Expense).where(Expense.description == "Varios"))
        update_expense(
            self.home.id,
            first.id,
            ExpenseUpdate(description="Supermercado", category_id=self.delivery.id, subcategory_id=None, is_recurring=False, is_shared=True),
            self.user,
            self.db,
        )
        rule = self.db.scalar(select(MercadoPagoMerchantRule).where(MercadoPagoMerchantRule.merchant_key == "collector:777"))
        self.assertEqual(rule.learned_description, "Supermercado")
        self.assertEqual(rule.category_id, self.delivery.id)
        self.assertTrue(rule.has_shared_override)
        self.assertTrue(rule.is_shared)
        first.notes = 'Tipo Mercado Pago: "Varios"'
        self.db.commit()

        await sync_integration(
            self.db,
            self.integration,
            client=FakeMercadoPagoClient(
                _csv_bytes_for_merchant("180000001", "2026-09-01T10:00:00.000-03:00"),
                payments={"180000001": {"description": "Nombre nuevo del proveedor", "collector": {"id": 777}}},
            ),
            poll_interval_seconds=0,
            poll_timeout_seconds=1,
            now=datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc),
        )
        self.db.refresh(first)
        self.assertEqual(first.description, "Supermercado")
        self.assertEqual(first.notes, 'Tipo Mercado Pago: "Varios"')

        household_integration = MercadoPagoIntegration(
            home_group_id=self.home.id,
            user_id=self.user.id,
            access_token="APP_USR-household-token",
            mp_user_id="654321",
            enabled=True,
        )
        self.db.add(household_integration)
        self.db.commit()

        second_client = FakeMercadoPagoClient(
            _csv_bytes_for_merchant("180000002", "2026-09-02T10:00:00.000-03:00"),
            payments={"180000002": {"description": "Varios", "collector": {"id": 777}, "store_id": "11"}},
        )
        await sync_integration(
            self.db,
            household_integration,
            client=second_client,
            poll_interval_seconds=0,
            poll_timeout_seconds=1,
            now=datetime(2026, 9, 3, 20, 0, tzinfo=timezone.utc),
        )
        descriptions = [expense.description for expense in self.db.scalars(select(Expense).order_by(Expense.id))]
        self.assertEqual(descriptions, ["Supermercado", "Supermercado"])
        newest = self.db.scalar(select(Expense).where(Expense.import_line_id != first.import_line_id))
        self.assertEqual(newest.category_id, self.delivery.id)
        self.assertTrue(newest.is_shared)
        self.assertIsNone(newest.notes)

        await sync_integration(
            self.db,
            household_integration,
            client=FakeMercadoPagoClient(
                _csv_bytes_for_merchant("180000003", "2026-09-03T10:00:00.000-03:00"),
                payments={"180000003": {"description": "Varios", "collector": {"id": 888}}},
            ),
            poll_interval_seconds=0,
            poll_timeout_seconds=1,
            now=datetime(2026, 9, 4, 20, 0, tzinfo=timezone.utc),
        )
        independent = self.db.scalar(select(Expense).where(Expense.description == "Varios"))
        self.assertIsNotNone(independent)
        self.assertIsNone(independent.category_id)

    async def test_store_id_is_used_only_when_collector_is_missing(self):
        self.assertEqual(_merchant_identity_from_payment({"collector": {"id": 12}, "store_id": "34"}), ("collector:12", "12", "34"))
        self.assertEqual(_merchant_identity_from_payment({"store_id": "34"}), ("store:34", None, "34"))

    async def test_client_creates_missing_report_config_before_sync(self):
        client = RecordingMercadoPagoClient()

        config = await client.ensure_report_config("123456")

        self.assertEqual(config, {"configured": True})
        self.assertEqual([call[0] for call in client.calls], ["GET", "POST"])
        self.assertEqual(client.calls[0][1], "https://api.mercadopago.com/v1/account/settlement_report/config")
        self.assertEqual(client.calls[1][1], "https://api.mercadopago.com/v1/account/settlement_report/config")
        payload = client.calls[1][2]
        self.assertEqual(payload["header_language"], "en")
        self.assertEqual(payload["separator"], ";")
        self.assertTrue(payload["include_withdraw"])
        self.assertIn({"key": "PAYMENT_METHOD_TYPE"}, payload["columns"])
        self.assertIn({"key": "REAL_AMOUNT"}, payload["columns"])
        self.assertIn({"key": "SALE_DETAIL"}, payload["columns"])
        self.assertIn({"key": "BUSINESS_UNIT"}, payload["columns"])
        self.assertIn({"key": "SUB_UNIT"}, payload["columns"])


class RecordingMercadoPagoClient(MercadoPagoClient):
    def __init__(self):
        super().__init__("APP_USR-secret")
        self.calls = []

    async def _request_json(self, method, url, json=None, accepted_statuses=None):
        self.calls.append((method, url, json, accepted_statuses))
        if method == "GET" and url.endswith("/config"):
            raise MercadoPagoNotFoundError("missing config")
        return {"configured": True}


def _csv_bytes() -> bytes:
    return (
        "EXTERNAL_REFERENCE;SOURCE_ID;USER_ID;PAYMENT_METHOD_TYPE;PAYMENT_METHOD;SITE;TRANSACTION_TYPE;TRANSACTION_AMOUNT;TRANSACTION_CURRENCY;TRANSACTION_DATE;REAL_AMOUNT\n"
        "PEDIDOSYA MARKET;SRC-001;123456;account_money;account_money;MLA;PAYMENT;-4500.00;ARS;2026-08-25T10:15:00.000-03:00;-4500.00\n"
        "MP-002;SRC-002;123456;account_money;account_money;MLA;TRANSFER;-15000.00;ARS;2026-08-25T11:15:00.000-03:00;-15000.00\n"
        "MP-003;SRC-003;123456;account_money;account_money;MLA;TRANSFER;23000.00;ARS;2026-08-25T12:15:00.000-03:00;23000.00\n"
        "MP-004;SRC-004;123456;account_money;account_money;MLA;REFUND;1200.00;ARS;2026-08-25T13:15:00.000-03:00;1200.00\n"
        "MP-005;SRC-005;123456;credit_card;visa;MLA;PAYMENT;-9999.00;ARS;2026-08-25T14:15:00.000-03:00;-9999.00\n"
    ).encode("utf-8")


def _csv_bytes_with_order_and_payout() -> bytes:
    return (
        "EXTERNAL_REFERENCE;SOURCE_ID;USER_ID;PAYMENT_METHOD_TYPE;PAYMENT_METHOD;SITE;TRANSACTION_TYPE;TRANSACTION_AMOUNT;TRANSACTION_CURRENCY;TRANSACTION_DATE;REAL_AMOUNT;ORDER_ID\n"
        '"INSTORE-7a285763-0b1a-4b31-b7a7-5a93cd47a1fd";175294418333;123456;available_money;available_money;MLA;SETTLEMENT;-3500.00;ARS;2026-08-29T15:15:02.000-03:00;-3500.00;44033131806\n'
        ";174784928487;123456;;;MLA;PAYOUTS;-11214.00;ARS;2026-08-26T13:14:59.000-03:00;-11214.00;\n"
    ).encode("utf-8")


def _csv_bytes_for_merchant(source_id: str, transaction_date: str) -> bytes:
    return (
        "EXTERNAL_REFERENCE;SOURCE_ID;USER_ID;PAYMENT_METHOD_TYPE;PAYMENT_METHOD;SITE;TRANSACTION_TYPE;TRANSACTION_AMOUNT;TRANSACTION_CURRENCY;TRANSACTION_DATE;REAL_AMOUNT\n"
        f'"INSTORE-test";{source_id};123456;available_money;available_money;MLA;SETTLEMENT;-2500.00;ARS;{transaction_date};-2500.00\n'
    ).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
