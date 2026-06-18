from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from evozeus.core.session import SessionEnvelope
from evozeus.factors.packs import FactorPack
from evozeus.factors.protocol import FactorResult
from evozeus.reports.html_report import render_factor_results_html
from evozeus.runtime.paths import RuntimePaths


class FileSessionRepository:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths

    def write_session(self, envelope: SessionEnvelope) -> None:
        session_dir = self.paths.session_dir(envelope.session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "session-envelope.json").write_text(
            envelope.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        with (session_dir / "events.jsonl").open("w", encoding="utf-8") as handle:
            for event in envelope.events:
                handle.write(event.model_dump_json() + "\n")

    def append_factor_results(self, session_id: str, results: list[FactorResult]) -> None:
        session_dir = self.paths.session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        path = session_dir / "factor-results.md"
        existing = path.read_text(encoding="utf-8") if path.exists() else "## Factor Results\n\n"
        sections = [_render_factor_result(result) for result in results]
        path.write_text(existing + "".join(sections), encoding="utf-8")

    def write_factor_results_html(
        self,
        session_id: str,
        results: list[FactorResult],
        factor_packs: list[FactorPack],
        selected_factor_ids: Iterable[str] | None = None,
        session_statuses: Iterable[object] | None = None,
        session_events: Iterable[object] | None = None,
    ) -> Path:
        session_dir = self.paths.session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        path = session_dir / "factor-results.html"
        path.write_text(
            render_factor_results_html(
                session_id,
                results,
                factor_packs,
                selected_factor_ids=selected_factor_ids,
                session_statuses=session_statuses,
                session_events=session_events,
            ),
            encoding="utf-8",
        )
        return path


def _render_factor_result(result: FactorResult) -> str:
    tags = ", ".join(f"{tag.get('type')}={tag.get('value')}" for tag in result.tags) or "None"
    evidence_refs = ", ".join(
        f"{ref.get('ref_id') or ref.get('event_id')}({ref.get('kind') or ref.get('source')})"
        for ref in result.evidence_refs
    ) or "None"
    verdict_signals = ", ".join(result.verdict_signals) or "None"
    return "\n".join(
        [
            f"## {result.factor_id}",
            "",
            f"- factor_version: {result.factor_version or 'unknown'}",
            f"- run_id: {result.run_id}",
            f"- stage: {result.stage}",
            f"- status: {result.status}",
            f"- confidence: {result.confidence}",
            f"- verdict_signals: {verdict_signals}",
            f"- tags: {tags}",
            f"- evidence_refs: {evidence_refs}",
            "",
        ]
    )
