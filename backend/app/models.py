from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.domain import Currency, ExpenseSource, ImportLineKind


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")


class HomeGroup(Base):
    __tablename__ = "home_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="home_group")
    categories: Mapped[list["Category"]] = relationship(back_populates="home_group")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "home_group_id", name="uq_membership_user_home"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    home_group_id: Mapped[int] = mapped_column(ForeignKey("home_groups.id"))
    role: Mapped[str] = mapped_column(String(40), default="member")

    user: Mapped[User] = relationship(back_populates="memberships")
    home_group: Mapped[HomeGroup] = relationship(back_populates="memberships")


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("home_group_id", "name", name="uq_category_home_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    home_group_id: Mapped[int] = mapped_column(ForeignKey("home_groups.id"))
    name: Mapped[str] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(24), default="#38bdf8")
    icon: Mapped[str] = mapped_column(String(40), default="tag")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)

    home_group: Mapped[HomeGroup] = relationship(back_populates="categories")


class Subcategory(Base):
    __tablename__ = "subcategories"
    __table_args__ = (UniqueConstraint("category_id", "name", name="uq_subcategory_category_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    home_group_id: Mapped[int] = mapped_column(ForeignKey("home_groups.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)


class Merchant(Base):
    __tablename__ = "merchants"
    __table_args__ = (UniqueConstraint("home_group_id", "normalized_name", name="uq_merchant_home_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    home_group_id: Mapped[int] = mapped_column(ForeignKey("home_groups.id"))
    display_name: Mapped[str] = mapped_column(String(160))
    normalized_name: Mapped[str] = mapped_column(String(160))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    subcategory_id: Mapped[int | None] = mapped_column(ForeignKey("subcategories.id"), nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    home_group_id: Mapped[int] = mapped_column(ForeignKey("home_groups.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(240))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    subcategory_id: Mapped[int | None] = mapped_column(ForeignKey("subcategories.id"), nullable=True)
    paid_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source: Mapped[ExpenseSource] = mapped_column(SAEnum(ExpenseSource), default=ExpenseSource.manual)
    currency: Mapped[Currency] = mapped_column(SAEnum(Currency), default=Currency.ARS)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    amount_ars: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    import_line_id: Mapped[int | None] = mapped_column(ForeignKey("import_lines.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Earning(Base):
    __tablename__ = "earnings"

    id: Mapped[int] = mapped_column(primary_key=True)
    home_group_id: Mapped[int] = mapped_column(ForeignKey("home_groups.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(240))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    currency: Mapped[Currency] = mapped_column(SAEnum(Currency), default=Currency.ARS)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    amount_ars: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    import_line_id: Mapped[int | None] = mapped_column(ForeignKey("import_lines.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    home_group_id: Mapped[int] = mapped_column(ForeignKey("home_groups.id"), index=True)
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(80), default="bbva_visa_pdf")
    statement_account: Mapped[str | None] = mapped_column(String(80), nullable=True)
    period_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="parsed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ImportLine(Base):
    __tablename__ = "import_lines"
    __table_args__ = (UniqueConstraint("home_group_id", "fingerprint", name="uq_import_line_fingerprint"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"))
    home_group_id: Mapped[int] = mapped_column(ForeignKey("home_groups.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(240))
    cardholder_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    coupon: Mapped[str | None] = mapped_column(String(60), nullable=True)
    kind: Mapped[ImportLineKind] = mapped_column(SAEnum(ImportLineKind))
    currency: Mapped[Currency] = mapped_column(SAEnum(Currency))
    original_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    suggested_category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    suggested_subcategory_id: Mapped[int | None] = mapped_column(ForeignKey("subcategories.id"), nullable=True)
    suggested_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    fingerprint: Mapped[str] = mapped_column(String(128))
    raw_text: Mapped[str] = mapped_column(Text)


class CashWalletEntry(Base):
    __tablename__ = "cash_wallet_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    home_group_id: Mapped[int] = mapped_column(ForeignKey("home_groups.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(240))
    currency: Mapped[Currency] = mapped_column(SAEnum(Currency), default=Currency.ARS)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FxRate(Base):
    __tablename__ = "fx_rates"
    __table_args__ = (UniqueConstraint("date", "source", "from_currency", "to_currency", name="uq_fx_rate"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    source: Mapped[str] = mapped_column(String(80), default="blue_average")
    from_currency: Mapped[Currency] = mapped_column(SAEnum(Currency), default=Currency.USD)
    to_currency: Mapped[Currency] = mapped_column(SAEnum(Currency), default=Currency.ARS)
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 4))


class RecurringRule(Base):
    __tablename__ = "recurring_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    home_group_id: Mapped[int] = mapped_column(ForeignKey("home_groups.id"), index=True)
    description_pattern: Mapped[str] = mapped_column(String(160))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    currency: Mapped[Currency] = mapped_column(SAEnum(Currency), default=Currency.ARS)
    expected_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    cadence: Mapped[str] = mapped_column(String(40), default="monthly")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    home_group_id: Mapped[int] = mapped_column(ForeignKey("home_groups.id"), index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(String(240))
    currency: Mapped[Currency | None] = mapped_column(SAEnum(Currency), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ReceiptImport(Base):
    __tablename__ = "receipt_imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    home_group_id: Mapped[int] = mapped_column(ForeignKey("home_groups.id"), index=True)
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"), nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40), default="uploaded")
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReceiptItem(Base):
    __tablename__ = "receipt_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_import_id: Mapped[int] = mapped_column(ForeignKey("receipt_imports.id"), index=True)
    description: Mapped[str] = mapped_column(String(240))
    subcategory_id: Mapped[int | None] = mapped_column(ForeignKey("subcategories.id"), nullable=True)
    suggested_subcategory_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(40), default="accepted")
