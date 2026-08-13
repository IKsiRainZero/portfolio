from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.indexer import run_index_scan

router = APIRouter(prefix="/api/index", tags=["index"])

@router.post("/scan")
def trigger_scan(db: Session = Depends(get_db)):
    created = run_index_scan(db)
    return {"scanned": len(created), "new_entries": [{"id": e.id, "title": e.title, "layer_id": e.layer_id, "status": e.status} for e in created]}
