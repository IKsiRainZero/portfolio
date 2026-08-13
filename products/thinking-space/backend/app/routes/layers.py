from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Dimension, Layer, LayerLink
from app.models.entry import entry_tags
from app.schemas import LayerResponse, LayerCreate, LayerUpdate, LayerReorderRequest

router = APIRouter(tags=["layers"])

def _to_response(l: Layer) -> LayerResponse:
    return LayerResponse(id=l.id, dimension_id=l.dimension_id, name=l.name, level=l.level,
                         description=l.description or "", entry_count=len(l.entries) if l.entries else 0)

@router.post("/api/dimensions/{dim_id}/layers", response_model=LayerResponse, status_code=201)
def create_layer(dim_id: str, body: LayerCreate, db: Session = Depends(get_db)):
    dim = db.query(Dimension).filter(Dimension.id == dim_id).first()
    if not dim:
        raise HTTPException(status_code=404, detail="Dimension not found")
    next_level = db.query(Layer).filter(Layer.dimension_id == dim_id).count()
    layer = Layer(dimension_id=dim_id, name=body.name, level=next_level,
                  description=body.description, sort_order=next_level)
    db.add(layer)
    db.commit()
    db.refresh(layer)
    return _to_response(layer)

@router.put("/api/layers/{layer_id}", response_model=LayerResponse)
def update_layer(layer_id: str, body: LayerUpdate, db: Session = Depends(get_db)):
    layer = db.query(Layer).filter(Layer.id == layer_id).first()
    if not layer:
        raise HTTPException(status_code=404, detail="Layer not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(layer, key, value)
    db.commit()
    db.refresh(layer)
    return _to_response(layer)

@router.delete("/api/layers/{layer_id}", status_code=204)
def delete_layer(layer_id: str, db: Session = Depends(get_db)):
    layer = db.query(Layer).filter(Layer.id == layer_id).first()
    if not layer:
        raise HTTPException(status_code=404, detail="Layer not found")
    # Clean orphan rows before deleting the layer
    db.query(LayerLink).filter(
        (LayerLink.source_layer_id == layer_id) | (LayerLink.target_layer_id == layer_id)
    ).delete()
    db.execute(entry_tags.delete().where(entry_tags.c.layer_id == layer_id))
    db.delete(layer)
    db.commit()

@router.put("/api/dimensions/{dim_id}/layers/reorder")
def reorder_layers(dim_id: str, body: LayerReorderRequest, db: Session = Depends(get_db)):
    for index, lid in enumerate(body.layer_ids):
        layer = db.query(Layer).filter(Layer.id == lid, Layer.dimension_id == dim_id).first()
        if layer:
            layer.level = index
            layer.sort_order = index
    db.commit()
    return {"reordered": len(body.layer_ids)}
