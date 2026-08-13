import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import DiagnoseRequest
from app.services.diagnosis import DiagnosisService

router = APIRouter(prefix="/api", tags=["diagnose"])

@router.post("/diagnose")
async def diagnose(request: Request, body: DiagnoseRequest, db: Session = Depends(get_db)):
    service = DiagnosisService()

    async def event_stream():
        async for event in service.run(body.question, body.dimension_id, db):
            if await request.is_disconnected():
                break
            yield f"event: {event['event']}\ndata: {event['data']}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
