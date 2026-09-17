from collections.abc import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_incremental_schema()
    ensure_postgres_enums()


def ensure_incremental_schema() -> None:
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            expense_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(expenses)"))}
            if "subcategory_id" not in expense_columns:
                connection.execute(text("ALTER TABLE expenses ADD COLUMN subcategory_id INTEGER REFERENCES subcategories(id)"))
            if "notes" not in expense_columns:
                connection.execute(text("ALTER TABLE expenses ADD COLUMN notes TEXT"))
            if "is_recurring" not in expense_columns:
                connection.execute(text("ALTER TABLE expenses ADD COLUMN is_recurring BOOLEAN NOT NULL DEFAULT 0"))
            _ensure_sqlite_mercadopago_schema(connection)
            import_batch_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(import_batches)"))}
            if "fx_rate_ars_per_usd" not in import_batch_columns:
                connection.execute(text("ALTER TABLE import_batches ADD COLUMN fx_rate_ars_per_usd NUMERIC(14, 4)"))
            if "statement_period" not in import_batch_columns:
                connection.execute(text("ALTER TABLE import_batches ADD COLUMN statement_period VARCHAR(7)"))
            import_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(import_lines)"))}
            if "suggested_subcategory_id" not in import_columns:
                connection.execute(text("ALTER TABLE import_lines ADD COLUMN suggested_subcategory_id INTEGER REFERENCES subcategories(id)"))
            if "suggested_recurring" not in import_columns:
                connection.execute(text("ALTER TABLE import_lines ADD COLUMN suggested_recurring BOOLEAN NOT NULL DEFAULT 0"))
            if "notes" not in import_columns:
                connection.execute(text("ALTER TABLE import_lines ADD COLUMN notes TEXT"))
            if "cardholder_name" not in import_columns:
                connection.execute(text("ALTER TABLE import_lines ADD COLUMN cardholder_name VARCHAR(160)"))
            if "mercadopago_merchant_key" not in import_columns:
                connection.execute(text("ALTER TABLE import_lines ADD COLUMN mercadopago_merchant_key VARCHAR(120)"))
            if "mercadopago_collector_id" not in import_columns:
                connection.execute(text("ALTER TABLE import_lines ADD COLUMN mercadopago_collector_id VARCHAR(80)"))
            if "mercadopago_store_id" not in import_columns:
                connection.execute(text("ALTER TABLE import_lines ADD COLUMN mercadopago_store_id VARCHAR(80)"))
            receipt_item_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(receipt_items)"))}
            if "status" not in receipt_item_columns:
                connection.execute(text("ALTER TABLE receipt_items ADD COLUMN status VARCHAR(40) NOT NULL DEFAULT 'accepted'"))
            receipt_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(receipt_imports)"))}
            if "category_id" not in receipt_columns:
                connection.execute(text("ALTER TABLE receipt_imports ADD COLUMN category_id INTEGER REFERENCES categories(id)"))
            if "subcategory_id" not in receipt_item_columns:
                connection.execute(text("ALTER TABLE receipt_items ADD COLUMN subcategory_id INTEGER REFERENCES subcategories(id)"))
            if "suggested_subcategory_name" not in receipt_item_columns:
                connection.execute(text("ALTER TABLE receipt_items ADD COLUMN suggested_subcategory_name VARCHAR(80)"))
            merchant_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(merchants)"))}
            if "subcategory_id" not in merchant_columns:
                connection.execute(text("ALTER TABLE merchants ADD COLUMN subcategory_id INTEGER REFERENCES subcategories(id)"))
            if "is_recurring" not in merchant_columns:
                connection.execute(text("ALTER TABLE merchants ADD COLUMN is_recurring BOOLEAN NOT NULL DEFAULT 0"))
            _backfill_import_batch_fx_rates(connection)
            _repair_bank_import_signs(connection)
    elif engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS subcategory_id INTEGER REFERENCES subcategories(id)"))
            connection.execute(text("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS notes TEXT"))
            connection.execute(text("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS is_recurring BOOLEAN NOT NULL DEFAULT FALSE"))
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS mercadopago_integrations (
                        id SERIAL PRIMARY KEY,
                        home_group_id INTEGER NOT NULL REFERENCES home_groups(id),
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        mp_user_id VARCHAR(80),
                        mp_nickname VARCHAR(160),
                        mp_site_id VARCHAR(20),
                        access_token TEXT NOT NULL,
                        enabled BOOLEAN NOT NULL DEFAULT TRUE,
                        last_sync_at TIMESTAMP,
                        last_sync_status VARCHAR(40),
                        last_sync_error TEXT,
                        last_report_file_name VARCHAR(255),
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        CONSTRAINT uq_mp_integration_home_user UNIQUE (home_group_id, user_id)
                    )
                    """
                )
            )
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_mercadopago_integrations_home_group_id ON mercadopago_integrations(home_group_id)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_mercadopago_integrations_user_id ON mercadopago_integrations(user_id)"))
            connection.execute(text("ALTER TABLE import_batches ADD COLUMN IF NOT EXISTS fx_rate_ars_per_usd NUMERIC(14, 4)"))
            connection.execute(text("ALTER TABLE import_batches ADD COLUMN IF NOT EXISTS statement_period VARCHAR(7)"))
            connection.execute(text("ALTER TABLE import_lines ADD COLUMN IF NOT EXISTS suggested_subcategory_id INTEGER REFERENCES subcategories(id)"))
            connection.execute(text("ALTER TABLE import_lines ADD COLUMN IF NOT EXISTS suggested_recurring BOOLEAN NOT NULL DEFAULT FALSE"))
            connection.execute(text("ALTER TABLE import_lines ADD COLUMN IF NOT EXISTS notes TEXT"))
            connection.execute(text("ALTER TABLE import_lines ADD COLUMN IF NOT EXISTS cardholder_name VARCHAR(160)"))
            connection.execute(text("ALTER TABLE import_lines ADD COLUMN IF NOT EXISTS mercadopago_merchant_key VARCHAR(120)"))
            connection.execute(text("ALTER TABLE import_lines ADD COLUMN IF NOT EXISTS mercadopago_collector_id VARCHAR(80)"))
            connection.execute(text("ALTER TABLE import_lines ADD COLUMN IF NOT EXISTS mercadopago_store_id VARCHAR(80)"))
            _ensure_postgres_mercadopago_runtime_schema(connection)
            connection.execute(text("ALTER TABLE receipt_items ADD COLUMN IF NOT EXISTS status VARCHAR(40) NOT NULL DEFAULT 'accepted'"))
            connection.execute(text("ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES categories(id)"))
            connection.execute(text("ALTER TABLE receipt_items ADD COLUMN IF NOT EXISTS subcategory_id INTEGER REFERENCES subcategories(id)"))
            connection.execute(text("ALTER TABLE receipt_items ADD COLUMN IF NOT EXISTS suggested_subcategory_name VARCHAR(80)"))
            connection.execute(text("ALTER TABLE merchants ADD COLUMN IF NOT EXISTS subcategory_id INTEGER REFERENCES subcategories(id)"))
            connection.execute(text("ALTER TABLE merchants ADD COLUMN IF NOT EXISTS is_recurring BOOLEAN NOT NULL DEFAULT FALSE"))
            _backfill_import_batch_fx_rates(connection)
            _repair_bank_import_signs(connection)


def _backfill_import_batch_fx_rates(connection) -> None:
    connection.execute(
        text(
            """
            UPDATE import_batches
            SET fx_rate_ars_per_usd = COALESCE(
                (
                    SELECT rate
                    FROM fx_rates
                    WHERE from_currency = 'USD'
                      AND to_currency = 'ARS'
                    ORDER BY date DESC, id DESC
                    LIMIT 1
                ),
                1500.0000
            )
            WHERE fx_rate_ars_per_usd IS NULL
            """
        )
    )


def _ensure_sqlite_mercadopago_schema(connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS mercadopago_integrations (
                id INTEGER NOT NULL PRIMARY KEY,
                home_group_id INTEGER NOT NULL REFERENCES home_groups(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                mp_user_id VARCHAR(80),
                mp_nickname VARCHAR(160),
                mp_site_id VARCHAR(20),
                access_token TEXT NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT 1,
                last_sync_at DATETIME,
                last_sync_status VARCHAR(40),
                last_sync_error TEXT,
                last_report_file_name VARCHAR(255),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_mp_integration_home_user UNIQUE (home_group_id, user_id)
            )
            """
        )
    )
    integration_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(mercadopago_integrations)"))}
    for column, definition in {
        "last_sync_started_at": "DATETIME",
        "last_sync_completed_at": "DATETIME",
        "last_sync_begin_date": "DATETIME",
        "last_sync_end_date": "DATETIME",
        "last_sync_imported": "INTEGER",
        "last_sync_ignored": "INTEGER",
        "last_sync_duplicates": "INTEGER",
    }.items():
        if column not in integration_columns:
            connection.execute(text(f"ALTER TABLE mercadopago_integrations ADD COLUMN {column} {definition}"))
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS mercadopago_merchant_rules (
                id INTEGER PRIMARY KEY,
                home_group_id INTEGER NOT NULL REFERENCES home_groups(id),
                merchant_key VARCHAR(120) NOT NULL,
                collector_id VARCHAR(80),
                store_id VARCHAR(80),
                learned_description VARCHAR(240),
                has_category_override BOOLEAN NOT NULL DEFAULT 0,
                category_id INTEGER REFERENCES categories(id),
                subcategory_id INTEGER REFERENCES subcategories(id),
                is_recurring BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_mp_merchant_rule_home_key UNIQUE (home_group_id, merchant_key)
            )
            """
        )
    )
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_mercadopago_merchant_rules_home_group_id ON mercadopago_merchant_rules(home_group_id)"))


def _ensure_postgres_mercadopago_runtime_schema(connection) -> None:
    for column, definition in {
        "last_sync_started_at": "TIMESTAMP",
        "last_sync_completed_at": "TIMESTAMP",
        "last_sync_begin_date": "TIMESTAMP",
        "last_sync_end_date": "TIMESTAMP",
        "last_sync_imported": "INTEGER",
        "last_sync_ignored": "INTEGER",
        "last_sync_duplicates": "INTEGER",
    }.items():
        connection.execute(text(f"ALTER TABLE mercadopago_integrations ADD COLUMN IF NOT EXISTS {column} {definition}"))
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS mercadopago_merchant_rules (
                id SERIAL PRIMARY KEY,
                home_group_id INTEGER NOT NULL REFERENCES home_groups(id),
                merchant_key VARCHAR(120) NOT NULL,
                collector_id VARCHAR(80),
                store_id VARCHAR(80),
                learned_description VARCHAR(240),
                has_category_override BOOLEAN NOT NULL DEFAULT FALSE,
                category_id INTEGER REFERENCES categories(id),
                subcategory_id INTEGER REFERENCES subcategories(id),
                is_recurring BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_mp_merchant_rule_home_key UNIQUE (home_group_id, merchant_key)
            )
            """
        )
    )
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_mercadopago_merchant_rules_home_group_id ON mercadopago_merchant_rules(home_group_id)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_mercadopago_integrations_home_group_id ON mercadopago_integrations(home_group_id)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_mercadopago_integrations_user_id ON mercadopago_integrations(user_id)"))


def _repair_bank_import_signs(connection) -> None:
    """Older XLS commits stored bank outflows as negative expenses.

    The sign is meaningful inside the bank statement, but expenses should carry
    their consumption impact. Keeping this idempotent lets existing real data be
    corrected without deleting imports, categories, or user edits.
    """
    connection.execute(
        text(
            """
            UPDATE expenses
            SET original_amount = ABS(original_amount),
                amount_ars = ABS(amount_ars)
            WHERE source = 'bank_import'
              AND (original_amount < 0 OR amount_ars < 0)
            """
        )
    )
    connection.execute(
        text(
            """
            UPDATE expenses
            SET is_recurring = FALSE
            WHERE source = 'bank_import'
              AND UPPER(description) LIKE '%TITULOS%'
            """
        )
    )
    connection.execute(
        text(
            """
            UPDATE expenses
            SET is_recurring = FALSE
            WHERE is_recurring = TRUE
              AND original_amount < 0
            """
        )
    )
    connection.execute(
        text(
            """
            UPDATE expenses AS charge
            SET is_recurring = FALSE
            WHERE charge.is_recurring = TRUE
              AND charge.original_amount > 0
              AND EXISTS (
                  SELECT 1
                  FROM expenses AS reversal
                  WHERE reversal.home_group_id = charge.home_group_id
                    AND reversal.currency = charge.currency
                    AND ABS(reversal.original_amount) = charge.original_amount
                    AND reversal.original_amount < 0
                    AND (
                        UPPER(reversal.description) = 'DEV ' || UPPER(charge.description)
                        OR UPPER(reversal.description) = 'CR ' || UPPER(charge.description)
                    )
              )
            """
        )
    )
    connection.execute(
        text(
            """
            UPDATE recurring_rules
            SET active = FALSE
            WHERE expected_amount < 0
               OR UPPER(description_pattern) LIKE 'DEV %'
               OR UPPER(description_pattern) LIKE 'CR %'
            """
        )
    )


def ensure_postgres_enums() -> None:
    if engine.dialect.name != "postgresql":
        return
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("ALTER TYPE expensesource ADD VALUE IF NOT EXISTS 'transfer'"))
        connection.execute(text("ALTER TYPE expensesource ADD VALUE IF NOT EXISTS 'other'"))
        connection.execute(text("ALTER TYPE expensesource ADD VALUE IF NOT EXISTS 'bank_import'"))
        connection.execute(text("ALTER TYPE expensesource ADD VALUE IF NOT EXISTS 'mercadopago'"))
        connection.execute(text("ALTER TYPE importlinekind ADD VALUE IF NOT EXISTS 'debit_purchase'"))
        connection.execute(text("ALTER TYPE importlinekind ADD VALUE IF NOT EXISTS 'cash_withdrawal'"))
        connection.execute(text("ALTER TYPE importlinekind ADD VALUE IF NOT EXISTS 'card_payment'"))
        connection.execute(text("ALTER TYPE importlinekind ADD VALUE IF NOT EXISTS 'transfer'"))
        connection.execute(text("ALTER TYPE importlinekind ADD VALUE IF NOT EXISTS 'income'"))
        connection.execute(text("ALTER TYPE importlinekind ADD VALUE IF NOT EXISTS 'previous_payment'"))
