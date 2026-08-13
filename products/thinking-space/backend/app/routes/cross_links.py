from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CrossLink
from app.schemas import CrossLinkCreate, CrossLinkResponse

router = APIRouter(prefix="/api/cross-links", tags=["cross-links"])

@router.post("", response_model=CrossLinkResponse, status_code=201)
def create_cross_link(body: CrossLinkCreate, db: Session = Depends(get_db)):
    link = CrossLink(source_entry_id=body.source_entry_id, target_entry_id=body.target_entry_id, relation_type=body.relation_type, note=body.note)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link

@router.delete("/{link_id}", status_code=204)
def delete_cross_link(link_id: str, db: Session = Depends(get_db)):
    link = db.query(CrossLink).filter(CrossLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="CrossLink not found")
    db.delete(link)
    db.commit()
