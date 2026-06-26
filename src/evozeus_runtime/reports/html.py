from __future__ import annotations

from html import escape

from evozeus_runtime.factors.protocol import FactorResult

VERDICT_ARTIFACTS = {
    "Preserve": ("Accepted Case", "Preserve the evidence-backed behavior as a reviewable case."),
    "Promote to Skill": ("Skill Candidate", "Draft or refine an agent-readable instruction only after human review."),
    "Extract Factor": ("Factor Candidate", "Turn the repeated judgment signal into a reusable factor proposal."),
    "Keep as Habit": ("Habit", "Keep this as a lightweight repeated practice, not a full skill."),
    "Fix Environment": ("Environment Rule", "Fix the local path, permission, runtime, or tool boundary before retrying."),
    "Reject Pattern": ("Rejected Pattern", "Record why this behavior should not be repeated."),
    "Open Case": ("Pending Case", "Keep the case open and collect more evidence before promotion."),
}

VERDICT_NEXT_ACTIONS = {
    "Preserve": "Save a redacted case and keep the raw session local.",
    "Promote to Skill": "Draft a skill candidate after reviewer approval.",
    "Extract Factor": "Draft a factor candidate with evidence refs and counterexamples.",
    "Keep as Habit": "Record a lightweight habit and revisit after more sessions.",
    "Fix Environment": "Fix the environment boundary, then rerun the same task path.",
    "Reject Pattern": "Record the rejection reason and do not promote this pattern.",
    "Open Case": "collect more evidence before choosing an artifact route.",
}


def render_factor_results_html(session_id: str, results: list[FactorResult]) -> str:
    card = _verdict_card(session_id, results)
    rows = "\n".join(
        f"<tr><td>{escape(result.factor_id)}</td><td>{escape(result.status)}</td>"
        f"<td>{result.confidence:.2f}</td></tr>"
        for result in results
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EvoZeus Runtime Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fb;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #667085;
      --line: #d9e1ea;
      --accent: #0f766e;
      --accent-soft: #d7f5ef;
      --warn-soft: #fff7ed;
      --warn: #b45309;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }}
    main {{ max-width: 980px; margin: 0 auto; padding: 28px 18px 42px; }}
    .verdict-card {{
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: 0 18px 42px rgba(15, 23, 42, 0.08);
    }}
    .card-header {{
      border-left: 6px solid var(--accent);
      padding: 22px 24px;
      background: linear-gradient(90deg, var(--accent-soft), #fff);
    }}
    .eyebrow {{ color: var(--accent); font-size: 12px; font-weight: 760; text-transform: uppercase; }}
    h1 {{ margin: 8px 0 0; font-size: 28px; line-height: 1.15; }}
    .session-id {{ margin-top: 8px; color: var(--muted); font-size: 13px; word-break: break-all; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0; }}
    .section {{ padding: 20px 24px; border-top: 1px solid var(--line); }}
    .section:nth-child(odd) {{ border-right: 1px solid var(--line); }}
    h2 {{ margin: 0 0 12px; font-size: 15px; }}
    ul {{ margin: 0; padding-left: 20px; }}
    li {{ margin: 7px 0; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .chip {{
      border: 1px solid rgba(15, 118, 110, 0.18);
      border-radius: 999px;
      padding: 5px 8px;
      background: var(--accent-soft);
      color: #0f4f49;
      font-size: 12px;
      font-weight: 680;
    }}
    .route {{ font-size: 24px; font-weight: 760; }}
    .muted {{ color: var(--muted); }}
    .privacy {{ background: var(--warn-soft); color: var(--warn); }}
    table {{
      width: 100%;
      margin-top: 22px;
      border-collapse: collapse;
      border: 1px solid var(--line);
      background: var(--panel);
      font-size: 13px;
    }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; }}
    th {{ color: var(--muted); background: #eef2f6; }}
    @media (max-width: 720px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .section:nth-child(odd) {{ border-right: none; }}
    }}
  </style>
</head>
<body>
  <main>
    {card}
    <table aria-label="Factor results">
      <thead><tr><th>Factor</th><th>Status</th><th>Confidence</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </main>
</body>
</html>"""


def _verdict_card(session_id: str, results: list[FactorResult]) -> str:
    proposed_verdict = _proposed_verdict(results)
    artifact, route_reason = VERDICT_ARTIFACTS[proposed_verdict]
    next_action = VERDICT_NEXT_ACTIONS[proposed_verdict]
    evidence_items = _evidence_items(results)
    signal_items = _signal_items(results)
    evidence_html = _list_or_empty(evidence_items, "No evidence refs found")
    signals_html = _chips_or_empty(signal_items, "No judgment signals found")
    return f"""
    <article class="verdict-card">
      <header class="card-header">
        <div class="eyebrow">Session Verdict Card</div>
        <h1><span class="muted">Proposed Verdict:</span> {escape(proposed_verdict)}</h1>
        <div class="session-id">session_id: {escape(session_id)}</div>
      </header>
      <div class="grid">
        <section class="section">
          <h2>Evidence</h2>
          {evidence_html}
        </section>
        <section class="section">
          <h2>Judgment Signals</h2>
          {signals_html}
        </section>
        <section class="section">
          <h2>Artifact Route</h2>
          <div class="route">{escape(artifact)}</div>
          <p class="muted">{escape(route_reason)}</p>
        </section>
        <section class="section privacy">
          <h2>Privacy</h2>
          <p>raw session stays local; publish only redacted evidence refs and review summaries.</p>
        </section>
        <section class="section">
          <h2>Next Action</h2>
          <p>{escape(next_action)}</p>
        </section>
        <section class="section">
          <h2>Boundary</h2>
          <p class="muted">Factor output is a proposed signal. Human review decides whether this becomes a Case, Factor, Skill, Environment Rule, or Rejected Pattern.</p>
        </section>
      </div>
    </article>"""


def _proposed_verdict(results: list[FactorResult]) -> str:
    for verdict in VERDICT_ARTIFACTS:
        if any(verdict in result.verdict_signals for result in results):
            return verdict
    return "Open Case"


def _evidence_items(results: list[FactorResult]) -> list[str]:
    items: list[str] = []
    for result in results:
        for evidence in result.evidence_refs:
            ref_id = evidence.get("ref_id", "")
            kind = evidence.get("kind", "evidence")
            if ref_id:
                items.append(f"{kind}: {ref_id}")
    return _dedupe(items)


def _signal_items(results: list[FactorResult]) -> list[str]:
    items: list[str] = []
    for result in results:
        items.extend(result.verdict_signals)
        items.extend(f"{tag.get('type')}: {tag.get('value')}" for tag in result.tags if tag.get("type") or tag.get("value"))
    return _dedupe(items)


def _list_or_empty(items: list[str], empty: str) -> str:
    visible = items or [empty]
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in visible) + "</ul>"


def _chips_or_empty(items: list[str], empty: str) -> str:
    visible = items or [empty]
    return '<div class="chips">' + "".join(f'<span class="chip">{escape(item)}</span>' for item in visible) + "</div>"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped
