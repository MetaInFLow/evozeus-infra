from pathlib import Path

from evozeus.core.session import SessionEnvelope
from evozeus.models import SessionEvent
from evozeus.scanners.base import ScanRequest, SessionRef
from evozeus.scanners.registry import ScannerRegistry


class DummyScanner:
    provider = "dummy"

    def can_discover(self, request: ScanRequest) -> bool:
        return request.source_dir == Path("/tmp/dummy")

    def discover(self, request: ScanRequest) -> list[SessionRef]:
        return [
            SessionRef(
                provider=self.provider,
                session_id="ezs_dummy",
                source_path=Path("/tmp/dummy/session.jsonl"),
            )
        ]

    def load(self, ref: SessionRef) -> SessionEnvelope:
        return SessionEnvelope(
            session_id=ref.session_id,
            provider=ref.provider,
            source_ref=str(ref.source_path),
            events=[SessionEvent(event_id="evt_1", role="user", content="hello")],
        )


def test_scanner_registry_routes_by_provider():
    registry = ScannerRegistry()
    registry.register(DummyScanner())

    refs = registry.discover(ScanRequest(provider="dummy", source_dir=Path("/tmp/other")))

    assert refs[0].session_id == "ezs_dummy"
    assert registry.load(refs[0]).events[0].content == "hello"


def test_scanner_registry_auto_detects_provider():
    registry = ScannerRegistry()
    registry.register(DummyScanner())

    refs = registry.discover(ScanRequest(provider="auto", source_dir=Path("/tmp/dummy")))

    assert refs[0].provider == "dummy"
