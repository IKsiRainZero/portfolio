from __future__ import annotations
from typing import Protocol, runtime_checkable
from services.pipeline.types import StepInput, StepOutput


@runtime_checkable
class Step(Protocol):
    name: str

    def run(self, input: StepInput) -> StepOutput: ...
    def can_skip(self, input: StepInput) -> bool: ...
