from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import LayerLink, Layer
from app.schemas import LayerLinkCreate, LayerLinkResponse

router = APIRouter(tags=["layer-links"])

@router.get("/api/dimensions/{dim_id}/layer-links", response_model=list[LayerLinkResponse])
def list_layer_links(dim_id: str, db: Session = Depends(get_db)):
    layer_ids = [l.id for l in db.query(Layer.id).filter(Layer.dimension_id == dim_id).all()]
    return db.query(LayerLink).filter(LayerLink.source_layer_id.in_(layer_ids)).all()

@router.post("/api/layer-links", response_model=LayerLinkResponse, status_code=201)
def create_layer_link(body: LayerLinkCreate, db: Session = Depends(get_db)):
    link = LayerLink(source_layer_id=body.source_layer_id, target_layer_id=body.target_layer_id,
                     relation_type=body.relation_type, note=body.note)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link

@router.delete("/api/layer-links/{link_id}", status_code=204)
def delete_layer_link(link_id: str, db: Session = Depends(get_db)):
    link = db.query(LayerLink).filter(LayerLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="LayerLink not found")
    db.delete(link)
    db.commit()
