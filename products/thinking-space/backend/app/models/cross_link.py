import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class CrossLink(Base):
    __tablename__ = "cross_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_entry_id: Mapped[str] = mapped_column(String(36), ForeignKey("entries.id"), nullable=False)
    target_entry_id: Mapped[str] = mapped_column(String(36), ForeignKey("entries.id"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False, default="relates_to")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    source_entry = relationship("Entry", foreign_keys=[source_entry_id], back_populates="source_links")
    target_entry = relationship("Entry", foreign_keys=[target_entry_id], back_populates="target_links")
