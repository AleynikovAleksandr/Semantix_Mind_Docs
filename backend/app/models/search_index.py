from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from app.database import Base


class Vector384(UserDefinedType):
    def get_col_spec(self, **kw):
        return "VECTOR(384)"


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
    theme_id: Mapped[int] = mapped_column(
        ForeignKey("document_themes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    embedding: Mapped[str | None] = mapped_column(Vector384(), nullable=True)


