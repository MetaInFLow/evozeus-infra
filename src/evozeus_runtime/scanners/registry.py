from __future__ import annotations

from pathlib import Path

from evozeus_runtime.sessions.schema import SessionEnvelope
from evozeus_runtime.scanners.base import ScanRequest, SessionMessageRef, SessionRef, SessionScanner


class ScannerRegistry:
    def __init__(self) -> None:
        self._scanners: dict[str, SessionScanner] = {}

    def register(self, scanner: SessionScanner) -> None:
        self._scanners[scanner.provider] = scanner

    def get(self, provider: str) -> SessionScanner:
        try:
            return self._scanners[provider]
        except KeyError as exc:
            raise KeyError(f"unknown scanner provider: {provider}") from exc

    def source_dirs(self, request: ScanRequest) -> list[Path]:
        if request.provider != "auto":
            return self.get(request.provider).source_dirs(request)

        source_dirs: list[Path] = []
        for scanner in self._scanners.values():
            source_dirs.extend(scanner.source_dirs(request))
        return source_dirs

    def discover(self, request: ScanRequest) -> list[SessionRef]:
        if request.provider != "auto":
            return self.get(request.provider).discover(request)

        for scanner in self._scanners.values():
            if scanner.can_discover(request):
                return scanner.discover(request)
        return []

    def discover_message_refs(self, ref: SessionRef) -> list[SessionMessageRef]:
        return self.get(ref.provider).discover_message_refs(ref)

    def load(self, ref: SessionRef) -> SessionEnvelope:
        return self.get(ref.provider).load(ref)
