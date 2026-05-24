"""add settings table and missing class columns

Revision ID: 004_settings_and_class_fields
Revises: 003_subscription_plans
Create Date: 2026-05-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "004_settings_and_class_fields"
down_revision = "003_subscription_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── settings ───────────────────────────────────────────────────
    op.create_table(
        "settings",
        sa.Column("key",        sa.String(64),  primary_key=True),
        sa.Column("value",      sa.Text(),      nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(),  server_default=sa.text("now()"), nullable=False),
    )

    # ── classes: новые колонки ─────────────────────────────────────
    op.add_column("classes", sa.Column(
        "location", sa.String(128), server_default="Студия", nullable=False,
    ))
    op.add_column("classes", sa.Column(
        "payment_enabled", sa.Boolean(), server_default="true", nullable=False,
    ))
    op.add_column("classes", sa.Column(
        "booking_enabled", sa.Boolean(), server_default="true", nullable=False,
    ))


def downgrade() -> None:
    op.drop_column("classes", "booking_enabled")
    op.drop_column("classes", "payment_enabled")
    op.drop_column("classes", "location")
    op.drop_table("settings")
