"""add pack_12, pack_16 subscription types and low_classes_warned flag

Revision ID: 003_subscription_plans
Revises: 002_add_payme
Create Date: 2026-05-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "003_subscription_plans"
down_revision = "002_add_payme"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL: добавляем новые значения в enum (необратимо, но безопасно)
    op.execute("ALTER TYPE subscriptiontype ADD VALUE IF NOT EXISTS 'pack_12'")
    op.execute("ALTER TYPE subscriptiontype ADD VALUE IF NOT EXISTS 'pack_16'")

    # Новый флаг напоминания о малом остатке занятий
    op.add_column(
        "subscriptions",
        sa.Column("low_classes_warned", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "low_classes_warned")
    # Удалить значения из PostgreSQL enum невозможно без пересоздания типа
