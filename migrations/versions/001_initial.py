"""initial schema

Revision ID: 001_initial
Revises:
Create Date: 2025-04-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id",         sa.BigInteger(),  primary_key=True),
        sa.Column("username",   sa.String(64),    nullable=True),
        sa.Column("full_name",  sa.String(128),   nullable=False),
        sa.Column("phone",      sa.String(20),    nullable=True),
        sa.Column("is_admin",   sa.Boolean(),     server_default="false", nullable=False),
        sa.Column("is_active",  sa.Boolean(),     server_default="true",  nullable=False),
        sa.Column("created_at", sa.DateTime(),    server_default=sa.text("now()"), nullable=False),
    )

    # ── classes ────────────────────────────────────────────────────
    op.create_table(
        "classes",
        sa.Column("id",           sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column("title",        sa.String(128),  nullable=False),
        sa.Column("trainer",      sa.String(64),   nullable=False),
        sa.Column("starts_at",    sa.DateTime(),   nullable=False),
        sa.Column("duration_min", sa.Integer(),    server_default="60",    nullable=False),
        sa.Column("max_spots",    sa.Integer(),    server_default="8",     nullable=False),
        sa.Column("is_cancelled", sa.Boolean(),    server_default="false", nullable=False),
    )
    op.create_index("ix_classes_starts_at", "classes", ["starts_at"])

    # ── subscriptions ──────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id",            sa.Integer(),  primary_key=True, autoincrement=True),
        sa.Column("user_id",       sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sub_type",      sa.Enum("single", "pack_4", "pack_8", name="subscriptiontype"), nullable=False),
        sa.Column("classes_left",  sa.Integer(),  nullable=False),
        sa.Column("expires_at",    sa.DateTime(), nullable=True),
        sa.Column("expiry_warned", sa.Boolean(),  server_default="false", nullable=False),
        sa.Column("created_at",    sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # ── bookings ───────────────────────────────────────────────────
    op.create_table(
        "bookings",
        sa.Column("id",             sa.Integer(),  primary_key=True, autoincrement=True),
        sa.Column("user_id",        sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("class_id",       sa.Integer(),  sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status",         sa.Enum("confirmed", "cancelled", "missed", "attended", name="bookingstatus"),
                  server_default="confirmed", nullable=False),
        sa.Column("reminder_sent",  sa.Boolean(),  server_default="false", nullable=False),
        sa.Column("reminder2_sent", sa.Boolean(),  server_default="false", nullable=False),
        sa.Column("created_at",     sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "class_id", name="uq_booking_user_class"),
    )
    op.create_index("ix_bookings_user_id",  "bookings", ["user_id"])
    op.create_index("ix_bookings_class_id", "bookings", ["class_id"])
    op.create_index("ix_bookings_status",   "bookings", ["status"])

    # ── payments ───────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id",              sa.Integer(),  primary_key=True, autoincrement=True),
        sa.Column("user_id",         sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", sa.Integer(),  sa.ForeignKey("subscriptions.id"), nullable=True),
        sa.Column("yukassa_id",      sa.String(64), unique=True, nullable=True),
        sa.Column("amount",          sa.Integer(),  nullable=False),   # рубли
        sa.Column("status",          sa.Enum("pending", "succeeded", "cancelled", name="paymentstatus"),
                  server_default="pending", nullable=False),
        sa.Column("description",     sa.Text(),     nullable=True),
        sa.Column("created_at",      sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("paid_at",         sa.DateTime(), nullable=True),
    )
    op.create_index("ix_payments_yukassa_id", "payments", ["yukassa_id"])


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("bookings")
    op.drop_table("subscriptions")
    op.drop_table("classes")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS bookingstatus")
    op.execute("DROP TYPE IF EXISTS paymentstatus")
    op.execute("DROP TYPE IF EXISTS subscriptiontype")
