from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Dimension
from app.schemas import DimensionResponse, LayerResponse, DimensionCreate, DimensionUpdate

router = APIRouter(prefix="/api/dimensions", tags=["dimensions"])

@router.get("", response_model=list[DimensionResponse])
def list_dimensions(db: Session = Depends(get_db)):
    dims = db.query(Dimension).options(joinedload(Dimension.layers)).order_by(Dimension.sort_order).all()
    result = []
    for d in dims:
        layers = []
        for l in d.layers:
            entry_count = len(l.entries) if l.entries else 0
            layers.append(LayerResponse(id=l.id, dimension_id=l.dimension_id, name=l.name, level=l.level, description=l.description or "", entry_count=entry_count))
        result.append(DimensionResponse(id=d.id, name=d.name, description=d.description or "", sort_order=d.sort_order, layers=layers))
    return result

@router.get("/{dimension_id}", response_model=DimensionResponse)
def get_dimension(dimension_id: str, db: Session = Depends(get_db)):
    dim = db.query(Dimension).options(joinedload(Dimension.layers)).filter(Dimension.id == dimension_id).first()
    if not dim:
        raise HTTPException(status_code=404, detail="Dimension not found")
    layers = []
    for l in dim.layers:
        entry_count = len(l.entries) if l.entries else 0
        layers.append(LayerResponse(id=l.id, dimension_id=l.dimension_id, name=l.name, level=l.level, description=l.description or "", entry_count=entry_count))
    return DimensionResponse(id=dim.id, name=dim.name, description=dim.description or "", sort_order=dim.sort_order, layers=layers)


@router.post("", response_model=DimensionResponse, status_code=201)
def create_dimension(body: DimensionCreate, db: Session = Depends(get_db)):
    dim = Dimension(name=body.name, description=body.description, sort_order=body.sort_order)
    db.add(dim)
    db.commit()
    db.refresh(dim)
    return DimensionResponse(id=dim.id, name=dim.name, description=dim.description or "",
                             sort_order=dim.sort_order, layers=[])


@router.put("/{dimension_id}", response_model=DimensionResponse)
def update_dimension(dimension_id: str, body: DimensionUpdate, db: Session = Depends(get_db)):
    dim = db.query(Dimension).filter(Dimension.id == dimension_id).first()
    if not dim:
        raise HTTPException(status_code=404, detail="Dimension not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(dim, key, value)
    db.commit()
    db.refresh(dim)
    layers = [LayerResponse(id=l.id, dimension_id=l.dimension_id, name=l.name, level=l.level,
                            description=l.description or "", entry_count=len(l.entries) if l.entries else 0)
              for l in dim.layers]
    return DimensionResponse(id=dim.id, name=dim.name, description=dim.description or "",
                             sort_order=dim.sort_order, layers=layers)


@router.delete("/{dimension_id}", status_code=204)
def delete_dimension(dimension_id: str, db: Session = Depends(get_db)):
    dim = db.query(Dimension).filter(Dimension.id == dimension_id).first()
    if not dim:
        raise HTTPException(status_code=404, detail="Dimension not found")
    db.delete(dim)
    db.commit()
