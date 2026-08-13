from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Any
import uuid


@dataclass
class StepSpec:
    step_name: str
    enabled: bool = True
    needs_human: bool = False
    config: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)


@dataclass
class PipelineSpec:
    steps: list[StepSpec]
    version: int = 1
    created_at: str = ""
    updated_at: str = ""


@dataclass
class StepInput:
    query: str
    previous_outputs: dict[str, Any] = field(default_factory=dict)
    pipeline_spec: PipelineSpec | None = None
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepOutput:
    step_name: str
    status: Literal["ok", "skipped", "needs_human", "error"]
    data: dict[str, Any] = field(default_factory=dict)
    human_question: str | None = None
    confidence: float = 0.5


EventType = Literal[
    "step_start", "step_end", "step_error",
    "spec_changed", "human_asked", "human_answered",
    "info_ingested", "credibility_scored"
]


@dataclass
class TraceEvent:
    event_id: str
    timestamp: str
    event_type: EventType
    step_name: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestedDocument:
    id: str
    text: str
    source_url: str
    source_type: str              # webpage | pdf | arxiv | news | api | file
    credibility_score: float = 0.5
    tags: list[str] = field(default_factory=list)
    fetched_at: str = ""
    structured: dict[str, Any] | None = None
    embedding: list[float] | None = None


def new_event_id() -> str:
    return str(uuid.uuid4())[:12]
