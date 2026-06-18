from __future__ import annotations

from evozeus.core.session import SessionEnvelope
from evozeus.scanners.base import ScanRequest, SessionRef, SessionScanner


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

    def discover(self, request: ScanRequest) -> list[SessionRef]:
        if request.provider != "auto":
            return self.get(request.provider).discover(request)

        for scanner in self._scanners.values():
            if scanner.can_discover(request):
                return scanner.discover(request)
        return []

    def load(self, ref: SessionRef) -> SessionEnvelope:
        return self.get(ref.provider).load(ref)
