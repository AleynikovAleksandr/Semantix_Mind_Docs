"""Add fulltext and semantic search index tables.

Revision ID: 002
Revises: 001
Create Date: 2026-04-28
"""

from alembic import op


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS vector;')

    op.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS uq_document_themes_doc_order '
        'ON document_themes(document_id, "order");'
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_search_index (
            document_id INTEGER PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
            search_vector TSVECTOR
        );
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_search_gin
        ON document_search_index USING GIN(search_vector);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS topic_search_index (
            document_id INTEGER NOT NULL,
            theme_index INTEGER NOT NULL,
            search_vector TSVECTOR,
            keywords TEXT[],
            embedding VECTOR(768),
            PRIMARY KEY (document_id, theme_index),
            FOREIGN KEY (document_id, theme_index)
                REFERENCES document_themes(document_id, "order") ON DELETE CASCADE
        );
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_topic_search_gin
        ON topic_search_index USING GIN(search_vector);
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_topic_embedding_hnsw
        ON topic_search_index USING hnsw (embedding vector_cosine_ops);
        """
    )


def downgrade():
    op.execute('DROP INDEX IF EXISTS idx_topic_embedding_hnsw;')
    op.execute('DROP INDEX IF EXISTS idx_topic_search_gin;')
    op.execute('DROP TABLE IF EXISTS topic_search_index;')
    op.execute('DROP INDEX IF EXISTS idx_document_search_gin;')
    op.execute('DROP TABLE IF EXISTS document_search_index;')
    op.execute('DROP INDEX IF EXISTS uq_document_themes_doc_order;')
