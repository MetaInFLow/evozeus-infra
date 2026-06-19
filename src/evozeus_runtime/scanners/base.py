from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel, Field

from evozeus_runtime.sessions.schema import SessionEnvelope
from evozeus_runtime.sessions.schema import SessionEvent

SCANNER_DESIGN_PRINCIPLES = (
    "scan_discovers_ids_only",
    "scan_records_session_and_message_ids",
    "load_materializes_content_for_factor_runtime",
    "load_consumes_progressive_event_generator",
    "scanner_outputs_provider_neutral_contracts",
    "scanner_declares_read_paths_before_access",
)


class ScanRequest(BaseModel):
    provider: str = "auto"
    source_dir: Path | None = None
    limit: int | None = None


class SessionRef(BaseModel):
    provider: str
    session_id: str
    source_path: Path
    metadata: dict[str, str] = Field(default_factory=dict)


class SessionMessageRef(BaseModel):
    provider: str
    session_id: str
    message_id: str
    source_path: Path
    message_index: int
    metadata: dict[str, str] = Field(default_factory=dict)


class SessionScanner(ABC):
    provider: str

    @abstractmethod
    def source_dirs(self, request: ScanRequest) -> list[Path]:
        ...

    @abstractmethod
    def can_discover(self, request: ScanRequest) -> bool:
        ...

    @abstractmethod
    def discover(self, request: ScanRequest) -> list[SessionRef]:
        ...

    @abstractmethod
    def discover_message_refs(self, ref: SessionRef) -> list[SessionMessageRef]:
        ...

    @abstractmethod
    def iter_events(self, ref: SessionRef) -> Iterator[SessionEvent]:
        ...

    @abstractmethod
    def load(self, ref: SessionRef) -> SessionEnvelope:
        ...
