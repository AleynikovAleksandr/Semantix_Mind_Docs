from sqlalchemy import String, Text, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class DocumentTheme(Base):
    __tablename__ = "document_themes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    theme_label: Mapped[str] = mapped_column(String(500), nullable=False)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    document: Mapped["Document"] = relationship("Document", back_populates="themes")
    segments: Mapped[list["TopicSegment"]] = relationship(
        "TopicSegment", back_populates="theme",
        cascade="all, delete-orphan", order_by="TopicSegment.order"
    )


class TopicSegment(Base):
    __tablename__ = "topic_segments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    theme_id: Mapped[int] = mapped_column(
        ForeignKey("document_themes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    segment_text: Mapped[str] = mapped_column(Text, nullable=False)
    start_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)

    theme: Mapped["DocumentTheme"] = relationship("DocumentTheme", back_populates="segments")
