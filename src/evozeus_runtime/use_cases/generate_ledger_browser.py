from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from evozeus_runtime.ledger.paths import RuntimePaths
from evozeus_runtime.ledger.repository import LedgerRepository
from evozeus_runtime.reports.ledger_browser import render_ledger_browser_html


@dataclass(frozen=True)
class GenerateLedgerBrowserResult:
    html_path: Path
    ledger_path: Path
    provider_count: int
    project_count: int
    session_count: int
    event_count: int


def generate_ledger_browser(
    *,
    workspace_root: Path,
    output_path: Path | None = None,
) -> GenerateLedgerBrowserResult:
    paths = RuntimePaths.for_workspace(workspace_root).ensure()
    ledger = LedgerRepository(paths)
    statuses = ledger.list_session_statuses()
    events = ledger.list_session_events()

    html_path = output_path or (paths.runtime_root / "reports" / "evozeus-sqlite.html")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(
        render_ledger_browser_html(
            statuses=statuses,
            events=events,
            ledger_path=paths.result_index_db,
        ),
        encoding="utf-8",
    )

    return GenerateLedgerBrowserResult(
        html_path=html_path,
        ledger_path=paths.result_index_db,
        provider_count=len({status.provider for status in statuses}),
        project_count=len({(status.provider, status.project_key or status.session_group_key) for status in statuses}),
        session_count=len(statuses),
        event_count=len(events),
    )
