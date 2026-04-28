"""Initial migration with indexes

Revision ID: 001
Revises: 
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Таблицы создаются автоматически через SQLAlchemy metadata,
    # но добавляем составные индексы для производительности

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_user_status
        ON documents(user_id, status);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_themes_document_order
        ON document_themes(document_id, "order");
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_segments_theme_order
        ON topic_segments(theme_id, "order");
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_request_logs_created
        ON request_logs(created_at DESC);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_keys_user_active
        ON api_keys(user_id, is_active);
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_documents_user_status;")
    op.execute("DROP INDEX IF EXISTS idx_themes_document_order;")
    op.execute("DROP INDEX IF EXISTS idx_segments_theme_order;")
    op.execute("DROP INDEX IF EXISTS idx_request_logs_created;")
    op.execute("DROP INDEX IF EXISTS idx_api_keys_user_active;")
