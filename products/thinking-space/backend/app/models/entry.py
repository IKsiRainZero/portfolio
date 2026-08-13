import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON, Float, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

entry_tags = Table(
    "entry_tags",
    Base.metadata,
    Column("entry_id", String(36), ForeignKey("entries.id"), primary_key=True),
    Column("layer_id", String(36), ForeignKey("layers.id"), primary_key=True),
)

class Entry(Base):
    __tablename__ = "entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False, default="known")
    layer_id: Mapped[str] = mapped_column(String(36), ForeignKey("layers.id"), nullable=True)
    dimension_id: Mapped[str] = mapped_column(String(36), ForeignKey("dimensions.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), default="manual")
    source_link: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="confirmed")
    tags: Mapped[dict] = mapped_column(JSON, default=list)
    confidence: Mapped[int] = mapped_column(Integer, default=100)
    x: Mapped[float] = mapped_column(Float, default=0.0)
    y: Mapped[float] = mapped_column(Float, default=0.0)
    width: Mapped[float] = mapped_column(Float, default=200.0)
    height: Mapped[float] = mapped_column(Float, default=120.0)
    z_depth: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    layer = relationship("Layer", back_populates="entries")
    dimension = relationship("Dimension", back_populates="entries")
    source_links = relationship("CrossLink", foreign_keys="CrossLink.source_entry_id", back_populates="source_entry", cascade="all, delete-orphan")
    target_links = relationship("CrossLink", foreign_keys="CrossLink.target_entry_id", back_populates="target_entry", cascade="all, delete-orphan")
    tag_layers = relationship("Layer", secondary=entry_tags)

    @property
    def tag_ids(self) -> list:
        return [l.id for l in self.tag_layers]
