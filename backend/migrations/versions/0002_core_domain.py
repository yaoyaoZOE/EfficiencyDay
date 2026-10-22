"""Add core domain tables.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "timezone", sa.String(length=100), server_default="Asia/Shanghai", nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("csrf_token", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=False), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"], unique=False)
    op.create_table(
        "work_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("urgency", sa.Boolean(), nullable=True),
        sa.Column("importance", sa.Boolean(), nullable=True),
        sa.Column("color_key", sa.String(length=20), nullable=True),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("completed_on", sa.Date(), nullable=True),
        sa.Column("background", sa.Text(), nullable=True),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("reflection", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled')",
            name="ck_work_items_status",
        ),
        sa.CheckConstraint(
            "urgency IS NULL OR urgency IN (0, 1)", name="ck_work_items_urgency_boolean"
        ),
        sa.CheckConstraint(
            "importance IS NULL OR importance IN (0, 1)",
            name="ck_work_items_importance_boolean",
        ),
        sa.CheckConstraint(
            "color_key IS NULL OR color_key IN "
            "('gray', 'blue', 'green', 'yellow', 'orange', 'red', 'purple')",
            name="ck_work_items_color_key",
        ),
        sa.CheckConstraint("version > 0", name="ck_work_items_positive_version"),
        sa.CheckConstraint(
            "(status = 'completed' AND completed_on IS NOT NULL) OR "
            "(status != 'completed' AND completed_on IS NULL)",
            name="ck_work_items_completion_date",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_items_user_id", "work_items", ["user_id"], unique=False)
    op.create_index(
        "ix_work_items_user_status", "work_items", ["user_id", "status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_work_items_user_status", table_name="work_items")
    op.drop_index("ix_work_items_user_id", table_name="work_items")
    op.drop_table("work_items")
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
