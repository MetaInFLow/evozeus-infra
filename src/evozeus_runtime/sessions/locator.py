from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class EventLocator(BaseModel):
    schema_version: str = "locator.v0"
    scanner_id: str
    scanner_version: str
    locator_schema: str
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ResolvedEvent(BaseModel):
    scanner_id: str
    scanner_version: str
    session_id: str = ""
    event_id: str = ""
    source_ref: str
    content: str
    content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceResolver(Protocol):
    scanner_id: str
    scanner_version: str

    def resolve_event(self, locator: EventLocator) -> ResolvedEvent:
        ...

    def verify_hash(self, resolved: ResolvedEvent, expected_hash: str) -> bool:
        ...
