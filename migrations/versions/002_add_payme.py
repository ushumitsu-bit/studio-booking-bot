"""replace yukassa with payme

Revision ID: 002_add_payme
Revises: 001_initial
Create Date: 2026-05-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "002_add_payme"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("payme_id", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_payments_payme_id", "payments", ["payme_id"])
    # Переименовываем старый столбец если он существует (безопасно через try)
    try:
        op.drop_constraint("payments_yukassa_id_key", "payments", type_="unique")
        op.drop_column("payments", "yukassa_id")
    except Exception:
        pass


def downgrade() -> None:
    op.drop_constraint("uq_payments_payme_id", "payments", type_="unique")
    op.drop_column("payments", "payme_id")
    op.add_column("payments", sa.Column("yukassa_id", sa.String(64), nullable=True))
    op.create_unique_constraint("payments_yukassa_id_key", "payments", ["yukassa_id"])
