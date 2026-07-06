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
            import_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(import_lines)"))}
            if "suggested_subcategory_id" not in import_columns:
                connection.execute(text("ALTER TABLE import_lines ADD COLUMN suggested_subcategory_id INTEGER REFERENCES subcategories(id)"))
            if "suggested_recurring" not in import_columns:
                connection.execute(text("ALTER TABLE import_lines ADD COLUMN suggested_recurring BOOLEAN NOT NULL DEFAULT 0"))
    elif engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS subcategory_id INTEGER REFERENCES subcategories(id)"))
            connection.execute(text("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS notes TEXT"))
            connection.execute(text("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS is_recurring BOOLEAN NOT NULL DEFAULT FALSE"))
            connection.execute(text("ALTER TABLE import_lines ADD COLUMN IF NOT EXISTS suggested_subcategory_id INTEGER REFERENCES subcategories(id)"))
            connection.execute(text("ALTER TABLE import_lines ADD COLUMN IF NOT EXISTS suggested_recurring BOOLEAN NOT NULL DEFAULT FALSE"))


def ensure_postgres_enums() -> None:
    if engine.dialect.name != "postgresql":
        return
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("ALTER TYPE expensesource ADD VALUE IF NOT EXISTS 'transfer'"))
        connection.execute(text("ALTER TYPE expensesource ADD VALUE IF NOT EXISTS 'other'"))
        connection.execute(text("ALTER TYPE expensesource ADD VALUE IF NOT EXISTS 'bank_import'"))
        connection.execute(text("ALTER TYPE importlinekind ADD VALUE IF NOT EXISTS 'debit_purchase'"))
        connection.execute(text("ALTER TYPE importlinekind ADD VALUE IF NOT EXISTS 'cash_withdrawal'"))
        connection.execute(text("ALTER TYPE importlinekind ADD VALUE IF NOT EXISTS 'card_payment'"))
        connection.execute(text("ALTER TYPE importlinekind ADD VALUE IF NOT EXISTS 'transfer'"))
        connection.execute(text("ALTER TYPE importlinekind ADD VALUE IF NOT EXISTS 'income'"))
        connection.execute(text("ALTER TYPE importlinekind ADD VALUE IF NOT EXISTS 'previous_payment'"))
