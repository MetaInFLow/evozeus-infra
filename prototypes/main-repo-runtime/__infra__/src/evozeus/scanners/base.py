from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from evozeus.core.session import SessionEnvelope


class ScanRequest(BaseModel):
    provider: str = "auto"
    source_dir: Path | None = None
    limit: int | None = None


class SessionRef(BaseModel):
    provider: str
    session_id: str
    source_path: Path
    metadata: dict[str, str] = Field(default_factory=dict)


class SessionScanner(Protocol):
    provider: str

    def can_discover(self, request: ScanRequest) -> bool:
        ...

    def discover(self, request: ScanRequest) -> list[SessionRef]:
        ...

    def load(self, ref: SessionRef) -> SessionEnvelope:
        ...
