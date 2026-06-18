from __future__ import annotations

from pydantic import BaseModel, Field

from evozeus.models import SessionEvent


class SessionEnvelope(BaseModel):
    schema_version: str = "session_envelope.v0"
    session_id: str
    provider: str
    source_ref: str
    events: list[SessionEvent] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
