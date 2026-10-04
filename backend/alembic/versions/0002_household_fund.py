"""household common fund

Revision ID: 0002_household_fund
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_household_fund"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mercadopago_integrations", sa.Column("fund_role", sa.String(24), nullable=False, server_default="personal"))
    op.add_column("import_lines", sa.Column("mercadopago_origin_id", sa.String(120), nullable=True))
    op.create_table(
        "fund_month_configs",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("period", sa.String(7), nullable=False), sa.Column("monthly_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("home_group_id", "period", name="uq_fund_config_home_period"),
    )
    op.create_index("ix_fund_month_configs_home_group_id", "fund_month_configs", ["home_group_id"])
    op.create_index("ix_fund_month_configs_period", "fund_month_configs", ["period"])
    op.create_table(
        "fund_month_shares",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("config_id", sa.Integer(), sa.ForeignKey("fund_month_configs.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("percentage", sa.Numeric(7, 4), nullable=False),
        sa.UniqueConstraint("config_id", "user_id", name="uq_fund_share_config_user"),
    )
    op.create_index("ix_fund_month_shares_config_id", "fund_month_shares", ["config_id"])
    op.create_index("ix_fund_month_shares_user_id", "fund_month_shares", ["user_id"])
    op.create_table(
        "fund_opening_balances",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False), sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("home_group_id", name="uq_fund_opening_home"),
    )
    op.create_index("ix_fund_opening_balances_home_group_id", "fund_opening_balances", ["home_group_id"])
    op.create_table(
        "fund_month_closures",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("period", sa.String(7), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False), sa.Column("agreed_closing_balance", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("home_group_id", "period", name="uq_fund_closure_home_period"),
    )
    op.create_index("ix_fund_month_closures_home_group_id", "fund_month_closures", ["home_group_id"])
    op.create_index("ix_fund_month_closures_period", "fund_month_closures", ["period"])
    op.create_table(
        "fund_closure_approvals",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("closure_id", sa.Integer(), sa.ForeignKey("fund_month_closures.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("closure_id", "user_id", name="uq_fund_approval_closure_user"),
    )
    op.create_index("ix_fund_closure_approvals_closure_id", "fund_closure_approvals", ["closure_id"])
    op.create_index("ix_fund_closure_approvals_user_id", "fund_closure_approvals", ["user_id"])
    op.create_table(
        "fund_manual_movements",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False), sa.Column("from_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("to_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True), sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("note", sa.String(240), nullable=True), sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_fund_manual_movements_home_group_id", "fund_manual_movements", ["home_group_id"])
    op.create_index("ix_fund_manual_movements_date", "fund_manual_movements", ["date"])
    op.create_table(
        "fund_mp_assignments",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("earning_id", sa.Integer(), sa.ForeignKey("earnings.id"), nullable=False), sa.Column("integration_id", sa.Integer(), sa.ForeignKey("mercadopago_integrations.id"), nullable=False),
        sa.Column("contributor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True), sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("stable_origin_id", sa.String(120), nullable=True), sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("earning_id", name="uq_fund_mp_assignment_earning"),
    )
    op.create_index("ix_fund_mp_assignments_home_group_id", "fund_mp_assignments", ["home_group_id"])
    op.create_index("ix_fund_mp_assignments_earning_id", "fund_mp_assignments", ["earning_id"])
    op.create_index("ix_fund_mp_assignments_integration_id", "fund_mp_assignments", ["integration_id"])
    op.create_table(
        "fund_mp_origin_rules",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("home_group_id", sa.Integer(), sa.ForeignKey("home_groups.id"), nullable=False),
        sa.Column("integration_id", sa.Integer(), sa.ForeignKey("mercadopago_integrations.id"), nullable=False), sa.Column("stable_origin_id", sa.String(120), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("integration_id", "stable_origin_id", name="uq_fund_mp_origin_rule"),
    )
    op.create_index("ix_fund_mp_origin_rules_home_group_id", "fund_mp_origin_rules", ["home_group_id"])
    op.create_index("ix_fund_mp_origin_rules_integration_id", "fund_mp_origin_rules", ["integration_id"])


def downgrade() -> None:
    for table in ("fund_mp_origin_rules", "fund_mp_assignments", "fund_manual_movements", "fund_closure_approvals", "fund_month_closures", "fund_opening_balances", "fund_month_shares", "fund_month_configs"):
        op.drop_table(table)
    op.drop_column("import_lines", "mercadopago_origin_id")
    op.drop_column("mercadopago_integrations", "fund_role")
