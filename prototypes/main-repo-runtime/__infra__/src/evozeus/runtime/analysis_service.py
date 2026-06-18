from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from evozeus.factors.base import FactorContext
from evozeus.factors.packs import FactorPackRepository
from evozeus.factors.runner import FactorRunner
from evozeus.runtime.paths import RuntimePaths
from evozeus.scanners.base import ScanRequest, SessionRef
from evozeus.scanners.providers.codex import CodexScanner
from evozeus.storage.file_repository import FileSessionRepository
from evozeus.storage.sqlite_result_store import SQLiteResultStore


DEFAULT_FACTOR_PACK_ROOT = Path(__file__).resolve().parents[3] / "factor_packs"


@dataclass(frozen=True)
class ScanSummary:
    session_count: int
    refs: list[SessionRef]
    sqlite_path: Path


@dataclass(frozen=True)
class AnalyzeSummary:
    session_id: str
    result_count: int
    error_count: int
    analysis_run_id: str
    sqlite_path: Path
    markdown_path: Path
    html_path: Path


def scan_sessions(
    *,
    workspace_root: Path,
    source_dir: Path | None = None,
    limit: int | None = None,
) -> ScanSummary:
    paths = RuntimePaths.for_workspace(workspace_root).ensure()
    store = SQLiteResultStore(paths)
    scanner = CodexScanner()
    refs = scanner.discover(ScanRequest(provider="codex", source_dir=source_dir, limit=limit))
    store.record_session_refs(refs)
    if _auto_load_events(paths):
        for ref in refs:
            store.record_session_envelope(scanner.load(ref))
    return ScanSummary(session_count=len(refs), refs=refs, sqlite_path=paths.result_index_db)


def analyze_session(
    *,
    workspace_root: Path,
    session_id: str,
    factor_ids: list[str] | None = None,
    pack_root: Path = DEFAULT_FACTOR_PACK_ROOT,
    write_artifacts: bool = True,
) -> AnalyzeSummary:
    paths = RuntimePaths.for_workspace(workspace_root).ensure()
    store = SQLiteResultStore(paths)
    scanner = CodexScanner()
    ref = store.get_session_ref(session_id)
    session = scanner.load(ref)

    factor_repository = FactorPackRepository(pack_root)
    packs = factor_repository.discover()
    store.record_installed_factors(packs, source="bundled")
    store.record_default_routes(packs)
    selected_packs = [factor_repository.get(factor_id) for factor_id in factor_ids] if factor_ids else packs
    selected_factor_ids = [pack.manifest.id for pack in selected_packs]

    summary = FactorRunner(selected_packs).run(FactorContext(session=session))
    analysis_run_id = store.record_factor_run(
        session,
        summary.results,
        factor_ids=selected_factor_ids,
        errors=summary.errors,
    )

    repository = FileSessionRepository(paths)
    html_path = paths.session_dir(session.session_id) / "factor-results.html"
    if write_artifacts:
        session_statuses = store.list_session_statuses(factor_ids=selected_factor_ids)
        session_events = store.list_session_events()
        repository.write_session(session)
        repository.append_factor_results(session.session_id, summary.results)
        html_path = repository.write_factor_results_html(
            session.session_id,
            summary.results,
            packs,
            selected_factor_ids=factor_ids,
            session_statuses=session_statuses,
            session_events=session_events,
        )
    return AnalyzeSummary(
        session_id=session.session_id,
        result_count=len(summary.results),
        error_count=len(summary.errors),
        analysis_run_id=analysis_run_id,
        sqlite_path=paths.result_index_db,
        markdown_path=html_path.with_name("factor-results.md"),
        html_path=html_path,
    )


def _auto_load_events(paths: RuntimePaths) -> bool:
    config_path = paths.state_root / "config.json"
    if not config_path.exists():
        return True
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True
    scan_config = config.get("scan") if isinstance(config, dict) else {}
    if not isinstance(scan_config, dict):
        return True
    return bool(scan_config.get("auto_load_events", True))
