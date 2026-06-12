"""add streak_updated column to bookings

Revision ID: 006_booking_streak_updated
Revises: 005_user_features
Create Date: 2026-06-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "006_booking_streak_updated"
down_revision = "005_user_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS "
        "streak_updated BOOLEAN NOT NULL DEFAULT false"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE bookings DROP COLUMN IF EXISTS streak_updated"
    ))
