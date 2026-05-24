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
    conn = op.get_bind()

    # ── settings ───────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS settings (
            key        VARCHAR(64) PRIMARY KEY,
            value      TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """))

    # ── classes: новые колонки (если ещё нет) ─────────────────────
    for col, definition in [
        ("location",        "VARCHAR(128) NOT NULL DEFAULT 'Студия'"),
        ("payment_enabled", "BOOLEAN NOT NULL DEFAULT true"),
        ("booking_enabled", "BOOLEAN NOT NULL DEFAULT true"),
    ]:
        conn.execute(sa.text(
            f"ALTER TABLE classes ADD COLUMN IF NOT EXISTS {col} {definition}"
        ))


def downgrade() -> None:
    op.drop_column("classes", "booking_enabled")
    op.drop_column("classes", "payment_enabled")
    op.drop_column("classes", "location")
    op.drop_table("settings")
