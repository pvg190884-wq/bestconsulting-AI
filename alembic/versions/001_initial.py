"""Initial migration — clients, chat_sessions, chat_messages, knowledge_items.

Revision ID: 001
Revises:
Create Date: 2026-07-27 04:51:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # clients
    op.create_table(
        "clients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("external_id", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("channel", sa.String(50), nullable=False, server_default="web"),
        sa.Column("preferences", sa.JSON(), default=dict),
        sa.Column("metadata", sa.JSON(), default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # chat_sessions
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("client_id", sa.String(36), sa.ForeignKey("clients.id"), nullable=False, index=True),
        sa.Column("channel", sa.String(50), nullable=False, server_default="web"),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("metadata", sa.JSON(), default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # chat_messages
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("chat_sessions.id"), nullable=False, index=True),
        sa.Column("role", sa.Enum("user", "assistant", "system", name="messageroleenum"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # knowledge_items
    op.create_table(
        "knowledge_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("type", sa.Enum("document", "faq", "scenario", "instruction", "client_preference", "learned", name="knowledgetypeenum"), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), default=list),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0"),
        sa.Column("verified", sa.Boolean(), server_default="false"),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_knowledge_type_verified", "knowledge_items", ["type", "verified"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_type_verified", table_name="knowledge_items")
    op.drop_table("knowledge_items")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("clients")
    op.execute("DROP TYPE IF EXISTS messageroleenum")
    op.execute("DROP TYPE IF EXISTS knowledgetypeenum")
