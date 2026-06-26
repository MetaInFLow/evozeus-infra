from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from evozeus_runtime.factors.official_bridge import OfficialFactorPackBuilder
from evozeus_runtime.ledger.paths import RuntimePaths
from evozeus_runtime.ledger.repository import LedgerRepository
from evozeus_runtime.use_cases.generate_ledger_browser import generate_ledger_browser
from evozeus_runtime.use_cases.run_factors import run_factors
from evozeus_runtime.use_cases.scan_sessions import scan_sessions


@dataclass(frozen=True)
class CodexOfficialVisualizationResult:
    workspace_root: Path
    ledger_path: Path
    html_path: Path
    session_count: int
    factor_count: int
    ran_count: int
    skipped_count: int
    error_count: int
    db_size_bytes: int


def run_codex_official_visualization(
    *,
    workspace_root: Path,
    official_repo_root: Path,
    force: bool = False,
    skip_fresh: bool = True,
    output_path: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> CodexOfficialVisualizationResult:
    started_at = perf_counter()
    paths = RuntimePaths.for_workspace(workspace_root).ensure()
    _emit(progress, f"runtime_root={paths.runtime_root}")
    _emit(progress, "scan_start provider=codex")
    scan_result = scan_sessions(workspace_root=workspace_root, provider="codex", source_dir=None)
    _emit(progress, f"scan_done sessions={scan_result.session_count}")

    pack_root = paths.installed_factors_dir / "official-generated"
    _emit(progress, f"official_pack_start output={pack_root}")
    pack_result = OfficialFactorPackBuilder(
        official_repo_root=official_repo_root,
        output_pack_root=pack_root,
    ).build()
    factor_ids = pack_result.factor_ids
    _emit(progress, f"official_pack_done factors={len(factor_ids)}")

    ledger = LedgerRepository(paths)
    statuses = ledger.list_session_statuses(factor_ids=factor_ids)
    total_sessions = len(statuses)
    _emit(progress, f"run_start sessions={total_sessions} factors={len(factor_ids)} force={force} skip_fresh={skip_fresh}")
    ran_count = 0
    skipped_count = 0
    error_count = 0
    for index, status in enumerate(statuses, start=1):
        if skip_fresh and not force and status.pending_factor_count == 0:
            skipped_count += len(factor_ids)
            if index == total_sessions or index % 100 == 0:
                _emit(
                    progress,
                    f"run_progress index={index}/{total_sessions} ran={ran_count} "
                    f"skipped={skipped_count} errors={error_count}",
                )
            continue
        session_started_at = perf_counter()
        pending_count = status.pending_factor_count if not force else len(factor_ids)
        _emit(
            progress,
            f"session_start index={index}/{total_sessions} session_id={status.session_id} pending={pending_count}",
        )
        run_result = run_factors(
            workspace_root=workspace_root,
            session_id=status.session_id,
            factor_ids=factor_ids,
            pack_root=pack_root,
            progress=progress,
        )
        ran_count += len(factor_ids)
        error_count += run_result.error_count
        elapsed = perf_counter() - session_started_at
        _emit(
            progress,
            f"session_done index={index}/{total_sessions} session_id={status.session_id} "
            f"results={run_result.result_count} errors={run_result.error_count} elapsed={elapsed:.2f}s",
        )

    html_path = output_path or (paths.runtime_root / "reports" / "codex-factor-visualization.html")
    _emit(progress, f"html_start output={html_path}")
    html_result = generate_ledger_browser(workspace_root=workspace_root, output_path=html_path)
    db_size = html_result.ledger_path.stat().st_size if html_result.ledger_path.exists() else 0
    elapsed = perf_counter() - started_at
    _emit(
        progress,
        f"run_done sessions={scan_result.session_count} factors={len(factor_ids)} "
        f"ran={ran_count} skipped={skipped_count} errors={error_count} "
        f"db_size_bytes={db_size} elapsed={elapsed:.2f}s",
    )
    return CodexOfficialVisualizationResult(
        workspace_root=workspace_root,
        ledger_path=html_result.ledger_path,
        html_path=html_result.html_path,
        session_count=scan_result.session_count,
        factor_count=len(factor_ids),
        ran_count=ran_count,
        skipped_count=skipped_count,
        error_count=error_count,
        db_size_bytes=db_size,
    )


def _emit(progress: Callable[[str], None] | None, message: str) -> None:
    if progress is not None:
        progress(message)
