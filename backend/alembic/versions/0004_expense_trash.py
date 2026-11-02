"""preserve deleted expenses for manual restoration"""

from alembic import op
import sqlalchemy as sa

revision = "0004_expense_trash"
down_revision = "0003_statement_owner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("expenses")}
    if "deleted_at" not in columns:
        op.add_column("expenses", sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("expenses", "deleted_at")
