from __future__ import annotations

from evozeus_runtime.scanners.providers.codex import CodexScanner
from evozeus_runtime.scanners.registry import ScannerRegistry


def create_default_scanner_registry() -> ScannerRegistry:
    registry = ScannerRegistry()
    registry.register(CodexScanner())
    return registry
