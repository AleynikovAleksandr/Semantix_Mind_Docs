from sqlalchemy import ForeignKey, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Text
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from app.database import Base


class Vector768(UserDefinedType):
    def get_col_spec(self, **kw):
        return "VECTOR(768)"


class DocumentSearchIndex(Base):
    __tablename__ = "document_search_index"

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)


class TopicSearchIndex(Base):
    __tablename__ = "topic_search_index"

    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    theme_index: Mapped[int] = mapped_column(Integer, nullable=False)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    embedding: Mapped[str | None] = mapped_column(Vector768(), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("document_id", "theme_index", name="pk_topic_search_index"),
        ForeignKeyConstraint(
            ["document_id", "theme_index"],
            ["document_themes.document_id", "document_themes.order"],
            ondelete="CASCADE",
            name="fk_topic_search_index_theme",
        ),
    )
