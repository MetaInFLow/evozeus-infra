from pathlib import Path

from evozeus_runtime.scanners.base import ScanRequest
from evozeus_runtime.scanners.builtins import create_default_scanner_registry
from evozeus_runtime.scanners.registry import ScannerRegistry


class FakeScanner:
    provider = "fake"

    def can_discover(self, request: ScanRequest) -> bool:
        return request.source_dir == Path("fake-source")

    def discover(self, request: ScanRequest):
        return []

    def load(self, ref):
        raise NotImplementedError


def test_scanner_registry_routes_by_provider():
    registry = ScannerRegistry()
    scanner = FakeScanner()

    registry.register(scanner)

    assert registry.get("fake") is scanner
    assert registry.discover(ScanRequest(provider="fake", source_dir=Path("anything"))) == []


def test_scanner_registry_auto_uses_scanner_capability():
    registry = ScannerRegistry()
    registry.register(FakeScanner())

    assert registry.discover(ScanRequest(provider="auto", source_dir=Path("fake-source"))) == []


def test_default_scanner_registry_includes_codex_scanner():
    registry = create_default_scanner_registry()

    assert registry.get("codex").provider == "codex"
