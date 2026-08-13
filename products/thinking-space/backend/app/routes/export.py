from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Entry, Layer

router = APIRouter(prefix="/api/export", tags=["export"])

@router.get("/gap-map", response_class=PlainTextResponse)
def export_gap_map(dimension_id: str = Query(...), db: Session = Depends(get_db)):
    layers = db.query(Layer).filter(Layer.dimension_id == dimension_id).order_by(Layer.level).all()
    lines = ["# 差距地图\n"]
    for layer in layers:
        entries = db.query(Entry).filter(Entry.layer_id == layer.id, Entry.status == "confirmed").all()
        known = sum(1 for e in entries if e.entry_type == "known")
        unknown = sum(1 for e in entries if e.entry_type == "unknown")
        questions = sum(1 for e in entries if e.entry_type == "question")
        lines.append(f"## {layer.name}")
        lines.append(f"- 已知: {known} | 未知缺口: {unknown} | 问题: {questions}")
        for e in entries:
            lines.append(f"  - [{e.entry_type}] {e.title}")
        lines.append("")
    return "\n".join(lines)
