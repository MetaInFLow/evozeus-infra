from __future__ import annotations

from evozeus_runtime.factors.protocol import FactorResult


def render_factor_results_markdown(session_id: str, results: list[FactorResult]) -> str:
    lines = [
        "# EvoZeus Runtime Report",
        "",
        f"- session_id: {session_id}",
        "",
        "## Factor Results",
        "",
    ]
    for result in results:
        tags = ", ".join(f"{tag.get('type')}={tag.get('value')}" for tag in result.tags) or "None"
        signals = ", ".join(result.verdict_signals) or "None"
        lines.extend(
            [
                f"### {result.factor_id}",
                "",
                f"- factor_version: {result.factor_version or 'unknown'}",
                f"- run_id: {result.run_id}",
                f"- status: {result.status}",
                f"- confidence: {result.confidence}",
                f"- verdict_signals: {signals}",
                f"- tags: {tags}",
                "",
            ]
        )
    return "\n".join(lines)

