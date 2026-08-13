from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.entry import Entry
from app.models.layer import Layer
from app.schemas import EntryCreate, EntryUpdate, EntryResponse, EntryGeometryUpdate

router = APIRouter(prefix="/api/entries", tags=["entries"])

@router.get("", response_model=list[EntryResponse])
def list_entries(
    dimension_id: Optional[str] = Query(None),
    layer_id: Optional[str] = Query(None),
    entry_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Entry)
    if dimension_id:
        query = query.filter(Entry.dimension_id == dimension_id)
    if layer_id:
        query = query.filter(Entry.layer_id == layer_id)
    if entry_type:
        query = query.filter(Entry.entry_type == entry_type)
    if status:
        query = query.filter(Entry.status == status)
    if q:
        query = query.filter(Entry.title.contains(q) | Entry.content.contains(q))
    return query.order_by(Entry.created_at.desc()).all()

@router.post("", response_model=EntryResponse, status_code=201)
def create_entry(body: EntryCreate, db: Session = Depends(get_db)):
    entry = Entry(
        title=body.title, content=body.content, entry_type=body.entry_type,
        layer_id=body.layer_id, dimension_id=body.dimension_id,
        source_type=body.source_type, source_link=body.source_link,
        tags=body.tags, confidence=body.confidence,
        x=body.x, y=body.y, width=body.width, height=body.height, z_depth=body.z_depth,
        status="pending" if body.source_type == "portfolio_index" else "confirmed",
    )
    db.add(entry)
    if body.tag_ids:
        entry.tag_layers = db.query(Layer).filter(Layer.id.in_(body.tag_ids)).all()
    db.commit()
    db.refresh(entry)
    return entry

@router.put("/{entry_id}", response_model=EntryResponse)
def update_entry(entry_id: str, body: EntryUpdate, db: Session = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    update_data = body.model_dump(exclude_unset=True)
    tag_ids = update_data.pop("tag_ids", None)
    for key, value in update_data.items():
        setattr(entry, key, value)
    if tag_ids is not None:
        entry.tag_layers = db.query(Layer).filter(Layer.id.in_(tag_ids)).all()
    db.commit()
    db.refresh(entry)
    return entry

@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: str, db: Session = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()

@router.put("/{entry_id}/geometry", response_model=EntryResponse)
def update_geometry(entry_id: str, body: EntryGeometryUpdate, db: Session = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    db.commit()
    db.refresh(entry)
    return entry

@router.put("/{entry_id}/confirm", response_model=EntryResponse)
def confirm_entry(entry_id: str, db: Session = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    entry.status = "confirmed"
    entry.confidence = 100
    db.commit()
    db.refresh(entry)
    return entry

@router.put("/{entry_id}/ignore", response_model=EntryResponse)
def ignore_entry(entry_id: str, db: Session = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    entry.status = "ignored"
    db.commit()
    db.refresh(entry)
    return entry
