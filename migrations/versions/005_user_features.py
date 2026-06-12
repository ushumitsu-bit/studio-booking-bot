"""add user profile fields, waitlist, feedback, freeze, zoom_link

Revision ID: 005_user_features
Revises: 004_settings_and_class_fields
Create Date: 2026-06-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "005_user_features"
down_revision = "004_settings_and_class_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── users: новые колонки ───────────────────────────────────────
    for col, definition in [
        ("onboarding_done",  "BOOLEAN NOT NULL DEFAULT false"),
        ("language",         "VARCHAR(2) NOT NULL DEFAULT 'ru'"),
        ("gender",           "VARCHAR(8) DEFAULT NULL"),
        ("fitness_level",    "VARCHAR(16) DEFAULT NULL"),
        ("class_preference", "VARCHAR(16) DEFAULT NULL"),
        ("health_notes",     "TEXT DEFAULT NULL"),
        ("streak_count",     "INTEGER NOT NULL DEFAULT 0"),
        ("last_attended_at", "TIMESTAMP DEFAULT NULL"),
    ]:
        conn.execute(sa.text(
            f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {definition}"
        ))

    # Существующие пользователи — онбординг пройден, язык ru
    conn.execute(sa.text(
        "UPDATE users SET onboarding_done = true WHERE onboarding_done = false"
    ))

    # ── subscriptions: заморозка ───────────────────────────────────
    for col, definition in [
        ("is_frozen",    "BOOLEAN NOT NULL DEFAULT false"),
        ("frozen_until", "TIMESTAMP DEFAULT NULL"),
    ]:
        conn.execute(sa.text(
            f"ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS {col} {definition}"
        ))

    # ── bookings: feedback_sent ────────────────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS feedback_sent BOOLEAN NOT NULL DEFAULT false"
    ))

    # ── classes: zoom_link ─────────────────────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE classes ADD COLUMN IF NOT EXISTS zoom_link VARCHAR(256) DEFAULT NULL"
    ))

    # ── waitlist ───────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS waitlist (
            id         SERIAL PRIMARY KEY,
            user_id    BIGINT NOT NULL REFERENCES users(id),
            class_id   INTEGER NOT NULL REFERENCES classes(id),
            notified   BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            UNIQUE (user_id, class_id)
        )
    """))

    # ── class_feedback ─────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS class_feedback (
            id         SERIAL PRIMARY KEY,
            user_id    BIGINT NOT NULL REFERENCES users(id),
            class_id   INTEGER NOT NULL REFERENCES classes(id),
            rating     SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
            comment    TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            UNIQUE (user_id, class_id)
        )
    """))

    # Тип TRIAL для абонементов
    conn.execute(sa.text(
        "ALTER TYPE subscriptiontype ADD VALUE IF NOT EXISTS 'trial'"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS class_feedback"))
    conn.execute(sa.text("DROP TABLE IF EXISTS waitlist"))
    for col in ["zoom_link"]:
        conn.execute(sa.text(f"ALTER TABLE classes DROP COLUMN IF EXISTS {col}"))
    for col in ["feedback_sent"]:
        conn.execute(sa.text(f"ALTER TABLE bookings DROP COLUMN IF EXISTS {col}"))
    for col in ["is_frozen", "frozen_until"]:
        conn.execute(sa.text(f"ALTER TABLE subscriptions DROP COLUMN IF EXISTS {col}"))
    for col in ["onboarding_done", "language", "gender", "fitness_level",
                "class_preference", "health_notes", "streak_count", "last_attended_at"]:
        conn.execute(sa.text(f"ALTER TABLE users DROP COLUMN IF EXISTS {col}"))
