"""persist the statement owner independently from additional cardholders"""

from alembic import op
import sqlalchemy as sa

revision = "0003_statement_owner"
down_revision = "0002_household_fund"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Startup compatibility migrations may already have added the column.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("import_batches")}
    if "owner_name" not in columns:
        op.add_column("import_batches", sa.Column("owner_name", sa.String(160), nullable=True))


def downgrade() -> None:
    op.drop_column("import_batches", "owner_name")
