"""Initial schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    currency = sa.Enum("ARS", "USD", name="currency")
    expense_source = sa.Enum("manual", "import_pdf", "bank_import", "cash", "transfer", "other", name="expensesource")
    import_line_kind = sa.Enum(
        "purchase",
        "refund",
        "payment",
        "tax",
        "fee",
        "adjustment",
        "debit_purchase",
        "cash_withdrawal",
        "card_payment",
        "transfer",
        "income",
        "reimbursement",
        "previous_payment",
        name="importlinekind",
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("google_sub", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("google_sub"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)

    op.create_table(
        "home_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.UniqueConstraint("user_id", "home_group_id", name="uq_membership_user_home"),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("color", sa.String(length=24), nullable=False),
        sa.Column("icon", sa.String(length=40), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("home_group_id", "name", name="uq_category_home_name"),
    )

    op.create_table(
        "subcategories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("category_id", "name", name="uq_subcategory_category_name"),
    )
    op.create_index(op.f("ix_subcategories_home_group_id"), "subcategories", ["home_group_id"], unique=False)
    op.create_index(op.f("ix_subcategories_category_id"), "subcategories", ["category_id"], unique=False)

    op.create_table(
        "merchants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("subcategory_id", sa.Integer(), sa.ForeignKey("subcategories.id"), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("home_group_id", "normalized_name", name="uq_merchant_home_name"),
    )

    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("statement_account", sa.String(length=80), nullable=True),
        sa.Column("period_label", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_import_batches_home_group_id"), "import_batches", ["home_group_id"], unique=False)

    op.create_table(
        "import_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("import_batch_id", sa.Integer(), sa.ForeignKey("import_batches.id"), nullable=False),
        sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("cardholder_name", sa.String(length=160), nullable=True),
        sa.Column("coupon", sa.String(length=60), nullable=True),
        sa.Column("kind", import_line_kind, nullable=False),
        sa.Column("currency", currency, nullable=False),
        sa.Column("original_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("suggested_category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("suggested_subcategory_id", sa.Integer(), sa.ForeignKey("subcategories.id"), nullable=True),
        sa.Column("suggested_recurring", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.UniqueConstraint("home_group_id", "fingerprint", name="uq_import_line_fingerprint"),
    )
    op.create_index(op.f("ix_import_lines_home_group_id"), "import_lines", ["home_group_id"], unique=False)

    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("subcategory_id", sa.Integer(), sa.ForeignKey("subcategories.id"), nullable=True),
        sa.Column("paid_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source", expense_source, nullable=False),
        sa.Column("currency", currency, nullable=False),
        sa.Column("original_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_ars", sa.Numeric(14, 2), nullable=False),
        sa.Column("import_line_id", sa.Integer(), sa.ForeignKey("import_lines.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_expenses_home_group_id"), "expenses", ["home_group_id"], unique=False)
    op.create_index(op.f("ix_expenses_date"), "expenses", ["date"], unique=False)

    op.create_table(
        "earnings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("currency", currency, nullable=False),
        sa.Column("original_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_ars", sa.Numeric(14, 2), nullable=False),
        sa.Column("import_line_id", sa.Integer(), sa.ForeignKey("import_lines.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_earnings_home_group_id"), "earnings", ["home_group_id"], unique=False)
    op.create_index(op.f("ix_earnings_date"), "earnings", ["date"], unique=False)

    op.create_table(
        "cash_wallet_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("currency", currency, nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("expense_id", sa.Integer(), sa.ForeignKey("expenses.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_cash_wallet_entries_home_group_id"), "cash_wallet_entries", ["home_group_id"], unique=False)

    op.create_table(
        "fx_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("from_currency", currency, nullable=False),
        sa.Column("to_currency", currency, nullable=False),
        sa.Column("rate", sa.Numeric(14, 4), nullable=False),
        sa.UniqueConstraint("date", "source", "from_currency", "to_currency", name="uq_fx_rate"),
    )
    op.create_index(op.f("ix_fx_rates_date"), "fx_rates", ["date"], unique=False)

    op.create_table(
        "recurring_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("description_pattern", sa.String(length=160), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("currency", currency, nullable=False),
        sa.Column("expected_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("cadence", sa.String(length=40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_index(op.f("ix_recurring_rules_home_group_id"), "recurring_rules", ["home_group_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("currency", currency, nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_audit_logs_home_group_id"), "audit_logs", ["home_group_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)

    op.create_table(
        "receipt_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expense_id", sa.Integer(), sa.ForeignKey("expenses.id"), nullable=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_receipt_imports_home_group_id"), "receipt_imports", ["home_group_id"], unique=False)

    op.create_table(
        "receipt_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("receipt_import_id", sa.Integer(), sa.ForeignKey("receipt_imports.id"), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("subcategory_id", sa.Integer(), sa.ForeignKey("subcategories.id"), nullable=True),
        sa.Column("suggested_subcategory_name", sa.String(length=80), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
    )
    op.create_index(op.f("ix_receipt_items_receipt_import_id"), "receipt_items", ["receipt_import_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_receipt_items_receipt_import_id"), table_name="receipt_items")
    op.drop_table("receipt_items")
    op.drop_index(op.f("ix_receipt_imports_home_group_id"), table_name="receipt_imports")
    op.drop_table("receipt_imports")
    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_home_group_id"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index(op.f("ix_recurring_rules_home_group_id"), table_name="recurring_rules")
    op.drop_table("recurring_rules")
    op.drop_index(op.f("ix_fx_rates_date"), table_name="fx_rates")
    op.drop_table("fx_rates")
    op.drop_index(op.f("ix_cash_wallet_entries_home_group_id"), table_name="cash_wallet_entries")
    op.drop_table("cash_wallet_entries")
    op.drop_index(op.f("ix_earnings_date"), table_name="earnings")
    op.drop_index(op.f("ix_earnings_home_group_id"), table_name="earnings")
    op.drop_table("earnings")
    op.drop_index(op.f("ix_expenses_date"), table_name="expenses")
    op.drop_index(op.f("ix_expenses_home_group_id"), table_name="expenses")
    op.drop_table("expenses")
    op.drop_index(op.f("ix_import_lines_home_group_id"), table_name="import_lines")
    op.drop_table("import_lines")
    op.drop_index(op.f("ix_import_batches_home_group_id"), table_name="import_batches")
    op.drop_table("import_batches")
    op.drop_table("merchants")
    op.drop_index(op.f("ix_subcategories_category_id"), table_name="subcategories")
    op.drop_index(op.f("ix_subcategories_home_group_id"), table_name="subcategories")
    op.drop_table("subcategories")
    op.drop_table("categories")
    op.drop_table("memberships")
    op.drop_table("home_groups")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
