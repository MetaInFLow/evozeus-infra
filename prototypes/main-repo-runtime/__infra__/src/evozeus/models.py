from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Verdict(StrEnum):
    PRESERVE = "Preserve"
    PROMOTE_TO_SKILL = "Promote to Skill"
    EXTRACT_FACTOR = "Extract Factor"
    KEEP_AS_HABIT = "Keep as Habit"
    FIX_ENVIRONMENT = "Fix Environment"
    REJECT_PATTERN = "Reject Pattern"
    OPEN_CASE = "Open Case"


class SessionEvent(BaseModel):
    event_id: str
    role: str
    content: str = ""
    tool_name: str | None = None
    tool_result: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionVerdictCard(BaseModel):
    task_context: str
    key_evidence: list[str] = Field(default_factory=list)
    judgment_signals: list[str] = Field(default_factory=list)
    proposed_verdict: Verdict
    suggested_next_action: str
    privacy_note: str
    optional_next_steps: list[str] = Field(default_factory=list)
