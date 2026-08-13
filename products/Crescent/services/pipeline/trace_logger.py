from __future__ import annotations
from datetime import datetime, timezone
from services.pipeline.types import EventType, TraceEvent, new_event_id


class TraceLogger:
    def __init__(self):
        self.events: list[TraceEvent] = []

    def log(self, event_type: EventType, step_name: str | None = None, data: dict | None = None):
        self.events.append(TraceEvent(
            event_id=new_event_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            step_name=step_name,
            data=data or {},
        ))

    def to_list(self) -> list[dict]:
        from dataclasses import asdict
        return [asdict(e) for e in self.events]
