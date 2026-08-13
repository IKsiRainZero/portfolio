from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class LayerLink(Base):
    __tablename__ = "layer_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_layer_id: Mapped[str] = mapped_column(String(36), ForeignKey("layers.id"), nullable=False)
    target_layer_id: Mapped[str] = mapped_column(String(36), ForeignKey("layers.id"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False, default="leads_to")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
