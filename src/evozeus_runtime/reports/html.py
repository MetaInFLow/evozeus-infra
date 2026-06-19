from __future__ import annotations

from html import escape

from evozeus_runtime.factors.protocol import FactorResult


def render_factor_results_html(session_id: str, results: list[FactorResult]) -> str:
    rows = "\n".join(
        f"<tr><td>{escape(result.factor_id)}</td><td>{escape(result.status)}</td>"
        f"<td>{result.confidence:.2f}</td></tr>"
        for result in results
    )
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        "<title>EvoZeus Runtime Report</title></head>"
        f"<body><h1>EvoZeus Runtime Report</h1><p>session_id: {escape(session_id)}</p>"
        "<table><thead><tr><th>Factor</th><th>Status</th><th>Confidence</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></body></html>"
    )

