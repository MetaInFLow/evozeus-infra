from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from evozeus_runtime.ledger.paths import RuntimePaths
from evozeus_runtime.ledger.repository import LedgerRepository
from evozeus_runtime.reports.html import render_factor_results_html
from evozeus_runtime.reports.json_report import render_factor_results_json
from evozeus_runtime.reports.markdown import render_factor_results_markdown


@dataclass(frozen=True)
class GenerateReportResult:
    markdown_path: Path
    json_path: Path
    html_path: Path


def generate_report(
    *,
    workspace_root: Path,
    session_id: str,
    formats: list[str],
) -> GenerateReportResult:
    paths = RuntimePaths.for_workspace(workspace_root).ensure()
    ledger = LedgerRepository(paths)
    results = ledger.list_factor_results(session_id=session_id)
    session_dir = paths.session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = session_dir / "factor-results.md"
    json_path = session_dir / "factor-results.json"
    html_path = session_dir / "factor-results.html"

    if "markdown" in formats:
        markdown_path.write_text(
            render_factor_results_markdown(session_id, results) + "\n",
            encoding="utf-8",
        )
    if "json" in formats:
        json_path.write_text(
            json.dumps(render_factor_results_json(session_id, results), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if "html" in formats:
        html_path.write_text(render_factor_results_html(session_id, results), encoding="utf-8")

    return GenerateReportResult(markdown_path=markdown_path, json_path=json_path, html_path=html_path)

