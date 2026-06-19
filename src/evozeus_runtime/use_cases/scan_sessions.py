from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from evozeus_runtime.ledger.paths import RuntimePaths
from evozeus_runtime.ledger.repository import LedgerRepository
from evozeus_runtime.policy.permissions import PermissionDeclaration, PermissionGate
from evozeus_runtime.scanners.base import ScanRequest
from evozeus_runtime.scanners.builtins import create_default_scanner_registry


@dataclass(frozen=True)
class ScanSessionsResult:
    session_count: int
    ledger_path: Path


def scan_sessions(*, workspace_root: Path, provider: str, source_dir: Path | None = None) -> ScanSessionsResult:
    scanner_registry = create_default_scanner_registry()
    request = ScanRequest(provider=provider, source_dir=source_dir)
    decision = PermissionGate().approve(PermissionDeclaration(files_read=scanner_registry.source_dirs(request)))
    if not decision.ok:
        raise PermissionError(decision.reason)

    paths = RuntimePaths.for_workspace(workspace_root).ensure()
    refs = scanner_registry.discover(request)
    ledger = LedgerRepository(paths)
    ledger.record_session_refs(refs)
    for ref in refs:
        ledger.record_session_message_refs(scanner_registry.discover_message_refs(ref))
    return ScanSessionsResult(session_count=len(refs), ledger_path=paths.result_index_db)
