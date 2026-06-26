from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from html import escape
import json
from pathlib import Path
from typing import Any

from evozeus_runtime.factors.protocol import FactorResult
from evozeus_runtime.ledger.repository import SessionAnalysisStatus, SessionEventRecord


MAX_RENDERED_EVENTS_PER_SESSION = 80
CONTEXT_EVENTS_PER_EDGE = 20
QUALITY_TABLE_LIMIT = 120
OFFICIAL_QUALITY_FACTOR_IDS = (
    "official.user-input-sentiment",
    "official.task-completion",
    "official.repeated-request",
    "official.tool-failure-frequency",
    "official.session-resource-usage",
    "official.key-sentence-trends",
    "official.usage-sentence-cloud",
)
NEGATIVE_SENTIMENT_VALUES = {"dissatisfaction", "problem_report", "correction_request"}
QUALITY_LABELS = {
    "success_skill_candidate": "好案例：可沉淀",
    "problem_skill_candidate": "问题案例：用户不满/纠错",
    "failure_skill_candidate": "问题案例：阻塞/失败",
    "repeat_skill_candidate": "问题案例：重复请求",
    "workflow_skill_candidate": "流程模式：可沉淀",
    "review_needed": "人工判断",
    "not_skill_candidate": "暂不沉淀",
}
SENTIMENT_SEARCH_ALIASES = {
    "dissatisfaction": "sentiment:negative 不满意 负面 dissatisfaction user_sentiment",
    "problem_report": "sentiment:negative 不满意 负面 问题反馈 problem_report user_sentiment",
    "correction_request": "sentiment:negative 不满意 负面 纠正请求 correction_request user_sentiment",
    "positive_feedback": "满意 正面 positive_feedback user_sentiment",
    "neutral_request": "neutral_request user_sentiment",
}


def render_ledger_browser_html(
    *,
    statuses: list[SessionAnalysisStatus],
    events: list[SessionEventRecord],
    factor_results: list[FactorResult] | None = None,
    ledger_path: Path | str | None = None,
) -> str:
    factor_results = factor_results or []
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    events_by_session: dict[str, list[SessionEventRecord]] = defaultdict(list)
    for event in events:
        events_by_session[event.session_id].append(event)

    results_by_session: dict[str, list[FactorResult]] = defaultdict(list)
    for result in factor_results:
        results_by_session[result.session_id].append(result)
    quality_signals = _build_quality_signals(statuses, events_by_session, results_by_session)
    quality_by_session = {signal["session_id"]: signal for signal in quality_signals}

    providers: dict[str, dict[tuple[str, str], list[SessionAnalysisStatus]]] = defaultdict(lambda: defaultdict(list))
    for status in sorted(statuses, key=lambda item: (item.provider, _project_label(item), item.session_id)):
        project_key = status.project_key or status.session_group_key or "unassigned"
        project_label = _project_label(status)
        providers[status.provider][(project_key, project_label)].append(status)

    project_count = len({(status.provider, status.project_key or status.session_group_key) for status in statuses})
    sidebar = _render_sidebar(providers)
    quality_body = _render_quality_signals(quality_signals)
    sessions_body = _render_providers(providers, events_by_session, results_by_session, quality_by_session)
    canvas_body = _render_global_canvas(factor_results)
    health_body = _render_run_health(
        statuses=statuses,
        events=events,
        factor_results=factor_results,
        ledger_path=ledger_path,
        generated_at=generated_at,
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>Codex SKILL Candidate Finder · EvoZeus SQLite Visualizer</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f3f5ef;
      --sidebar: #fbfcf7;
      --panel: #fffefb;
      --panel-soft: #f8faf4;
      --ink: #16211c;
      --muted: #667267;
      --muted-2: #879184;
      --line: #dbe2d8;
      --line-soft: #edf1e9;
      --accent: #0f766e;
      --accent-ink: #0b5e58;
      --accent-soft: #dff1ec;
      --warn: #9a3412;
      --warn-soft: #fff1e6;
      --code: #28342f;
      --track: #e7ede5;
      --shadow: 0 18px 48px rgba(39, 58, 48, .08);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.5;
      font-variant-numeric: tabular-nums;
    }}
    .shell {{
      display: grid;
      grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
      min-height: 100dvh;
    }}
    aside {{
      position: sticky;
      top: 0;
      height: 100dvh;
      overflow: auto;
      padding: 24px 20px;
      border-right: 1px solid var(--line);
      background: var(--sidebar);
    }}
    main {{
      min-width: 0;
      padding: 28px;
      overflow: hidden;
    }}
    .workspace {{
      width: min(100%, 1680px);
      margin: 0 auto;
    }}
    h1, h2, h3, h4 {{ margin: 0; line-height: 1.2; }}
    h1 {{ font-size: clamp(28px, 3vw, 42px); letter-spacing: 0; }}
    h2 {{ font-size: 19px; }}
    h3 {{ font-size: 15px; }}
    h4 {{ font-size: 13px; }}
    code {{
      color: var(--code);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      word-break: break-all;
    }}
    .report-header {{
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(340px, .75fr);
      gap: 16px;
      align-items: stretch;
      margin-bottom: 18px;
    }}
    .report-title {{
      min-width: 0;
      padding: 24px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: linear-gradient(135deg, rgba(255, 254, 251, .95), rgba(244, 249, 244, .95));
      box-shadow: var(--shadow);
    }}
    .report-kicker {{
      color: var(--accent-ink);
      font-weight: 700;
      margin-bottom: 8px;
    }}
    .report-title code {{ display: inline-block; max-width: 100%; }}
    .header-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 18px;
      box-shadow: var(--shadow);
    }}
    .meta {{ color: var(--muted); margin-top: 6px; max-width: 960px; }}
    .tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      position: sticky;
      top: 0;
      z-index: 2;
      margin: 0 0 22px;
      border-bottom: 1px solid var(--line);
      padding: 10px 0 12px;
      background: color-mix(in srgb, var(--bg) 88%, transparent);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
    }}
    .tab-button {{
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      border-radius: 8px;
      min-height: 36px;
      padding: 7px 12px;
      cursor: pointer;
      font: inherit;
      transition: background .16s ease, border-color .16s ease, transform .16s ease;
    }}
    .tab-button:hover {{ border-color: #b8c8bd; }}
    .tab-button:active {{ transform: translateY(1px); }}
    .tab-button.active {{ background: var(--accent-soft); color: var(--accent-ink); border-color: #a8d3ca; }}
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(110px, 1fr));
      gap: 10px;
      margin: 0;
    }}
    .header-card .stats {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
      height: 100%;
    }}
    .header-card .stat {{
      min-height: 100px;
    }}
    .stat, .panel:not(.project), .session, .widget, .factor-result {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
    }}
    .stat {{
      min-width: 0;
      padding: 13px 14px;
      background: var(--panel);
      border-color: var(--line-soft);
    }}
    .stat strong {{ display: block; font-size: 23px; letter-spacing: 0; }}
    .stat span {{ color: var(--muted); font-size: 12px; }}
    .search {{
      width: 100%;
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px 10px;
      background: var(--panel);
      color: var(--ink);
      outline: none;
    }}
    .search:focus {{
      border-color: #90c9c0;
      box-shadow: 0 0 0 3px rgba(15, 118, 110, .14);
    }}
    .quick-filters {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 10px;
    }}
    .filter-chip {{
      border: 1px solid var(--line);
      border-radius: 999px;
      min-height: 30px;
      padding: 4px 9px;
      background: var(--panel);
      color: var(--muted);
      cursor: pointer;
      font: inherit;
      font-size: 12px;
    }}
    .filter-chip:hover {{
      border-color: #a8d3ca;
      color: var(--accent-ink);
      background: var(--accent-soft);
    }}
    .nav-group {{ margin-top: 16px; }}
    .nav-provider {{ font-weight: 700; margin: 12px 0 6px; }}
    .nav-project {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      color: var(--muted);
      text-decoration: none;
      padding: 8px 0;
      border-top: 1px solid var(--line-soft);
      word-break: break-word;
    }}
    .nav-project:hover {{ color: var(--accent-ink); }}
    .provider {{ margin-bottom: 30px; }}
    .provider-header, .project-header, .widget-header {{
      display: flex;
      gap: 10px;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 10px;
    }}
    .provider-header {{
      padding: 0 0 12px;
      border-bottom: 1px solid var(--line);
    }}
    .project {{
      margin-top: 24px;
      padding: 2px 0 0;
      border-top: 1px solid var(--line);
      background: transparent;
      border-radius: 0;
    }}
    .project-header {{
      position: sticky;
      top: 62px;
      z-index: 1;
      padding: 14px 0;
      background: color-mix(in srgb, var(--bg) 92%, transparent);
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
    }}
    .project-key {{ color: var(--muted); margin-top: 4px; word-break: break-all; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 2px 8px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent-ink);
      font-size: 12px;
      font-weight: 650;
      white-space: nowrap;
    }}
    .session {{
      margin-top: 10px;
      overflow: hidden;
      box-shadow: 0 10px 28px rgba(39, 58, 48, .05);
    }}
    .session summary, .factor-result summary {{
      cursor: pointer;
      list-style: none;
      padding: 13px 16px;
    }}
    .session summary::-webkit-details-marker, .factor-result summary::-webkit-details-marker {{ display: none; }}
    .session summary:hover, .factor-result summary:hover {{ background: var(--panel-soft); }}
    .session-title {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-weight: 700; }}
    .session-subtitle {{ margin-top: 6px; color: var(--muted); display: flex; flex-wrap: wrap; gap: 10px; }}
    .chat {{ border-top: 1px solid var(--line); margin: 0; padding: 0; list-style: none; }}
    .event {{
      display: grid;
      grid-template-columns: 82px minmax(0, 1fr);
      gap: 12px;
      padding: 13px 16px;
      border-top: 1px solid var(--line-soft);
    }}
    .event:first-child {{ border-top: 0; }}
    .event-index {{
      color: var(--muted-2);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      padding-top: 2px;
    }}
    .event-body {{ min-width: 0; }}
    .event-line {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    .role {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 1px 6px;
      color: var(--muted);
      background: color-mix(in srgb, var(--panel) 78%, var(--bg));
      font-size: 12px;
      white-space: nowrap;
    }}
    .content {{
      margin-top: 7px;
      white-space: pre-wrap;
      word-break: break-word;
      max-width: 1100px;
    }}
    .empty {{
      color: var(--warn);
      background: var(--warn-soft);
      border-radius: 6px;
      padding: 6px 8px;
      display: inline-block;
    }}
    .source {{ margin-top: 6px; color: var(--muted); font-size: 12px; word-break: break-all; }}
    .factor-drawer {{
      border-top: 1px solid var(--line);
      padding: 14px 16px 16px;
      background: var(--panel-soft);
    }}
    .factor-result {{ margin-top: 8px; overflow: hidden; }}
    .factor-body {{ border-top: 1px solid var(--line); padding: 12px 14px; }}
    .dataset-summary {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 8px 0; border-top: 1px solid var(--line-soft); }}
    .kv {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
    .quality-grid {{
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 14px;
      align-items: start;
    }}
    .quality-card {{
      grid-column: span 6;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 16px;
      box-shadow: 0 12px 34px rgba(39, 58, 48, .06);
    }}
    .quality-card--wide {{ grid-column: span 12; }}
    .method-list {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 10px;
      margin-top: 12px;
    }}
    .method-item {{
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      padding: 10px;
      background: var(--panel-soft);
    }}
    .score-pill {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 48px;
      min-height: 26px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent-ink);
      font-weight: 750;
    }}
    .widget-grid {{
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 14px;
      align-items: start;
    }}
    .widget {{
      grid-column: span 6;
      padding: 16px;
      min-width: 0;
      box-shadow: 0 12px 34px rgba(39, 58, 48, .06);
    }}
    .widget--word-cloud {{ grid-column: span 7; }}
    .widget--bar-chart {{ grid-column: span 5; }}
    .widget--table, .widget--json, .widget--heatmap, .widget--line-chart {{ grid-column: span 12; }}
    .factor-body .widget-grid {{ grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }}
    .factor-body .widget {{ grid-column: auto; box-shadow: none; }}
    .widget-title {{ display: flex; flex-direction: column; gap: 4px; min-width: 0; }}
    .component-ref {{ color: var(--muted); font-size: 12px; }}
    .bars {{ display: grid; gap: 8px; margin-top: 12px; }}
    .bar-row {{ display: grid; grid-template-columns: minmax(110px, 34%) minmax(0, 1fr) 56px; gap: 10px; align-items: center; }}
    .bar-label {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .bar-track {{ height: 8px; border-radius: 999px; background: var(--track); overflow: hidden; }}
    .bar-fill {{ height: 100%; border-radius: 999px; background: var(--accent); }}
    .cloud {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; margin-top: 12px; line-height: 1.25; }}
    .cloud-word {{ color: var(--accent-ink); background: var(--accent-soft); border-radius: 8px; padding: 4px 7px; }}
    [data-filter-value] {{ cursor: pointer; }}
    [data-filter-value]:hover {{ outline: 2px solid color-mix(in srgb, var(--accent) 38%, transparent); outline-offset: 2px; }}
    .table-wrap {{ max-width: 100%; overflow: auto; margin-top: 12px; border: 1px solid var(--line-soft); border-radius: 8px; }}
    .data-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    .data-table th, .data-table td {{ border-top: 1px solid var(--line-soft); padding: 8px; text-align: left; vertical-align: top; }}
    .data-table tr:first-child td {{ border-top: 1px solid var(--line); }}
    .data-table th {{ color: var(--muted); font-weight: 650; }}
    .data-table tbody tr:hover {{ background: var(--panel-soft); }}
    .skill-candidate-table {{ table-layout: fixed; min-width: 1320px; }}
    .skill-candidate-table th:nth-child(1), .skill-candidate-table td:nth-child(1) {{ width: 140px; }}
    .skill-candidate-table th:nth-child(2), .skill-candidate-table td:nth-child(2) {{ width: 250px; }}
    .skill-candidate-table th:nth-child(3), .skill-candidate-table td:nth-child(3) {{ width: 250px; }}
    .skill-candidate-table th:nth-child(4), .skill-candidate-table td:nth-child(4) {{ width: 310px; }}
    .skill-candidate-table th:nth-child(5), .skill-candidate-table td:nth-child(5) {{ width: 160px; }}
    .skill-candidate-table th:nth-child(6), .skill-candidate-table td:nth-child(6) {{ width: 260px; }}
    .skill-candidate-table th:nth-child(7), .skill-candidate-table td:nth-child(7) {{ width: 250px; }}
    .skill-candidate-table td {{ word-break: break-word; overflow-wrap: anywhere; }}
    .hidden {{ display: none !important; }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #141a17;
        --sidebar: #171f1b;
        --panel: #1e2722;
        --panel-soft: #19221e;
        --ink: #eef4ed;
        --muted: #a6b2a8;
        --muted-2: #7e8b81;
        --line: #334138;
        --line-soft: #28342d;
        --accent: #2dd4bf;
        --accent-ink: #5eead4;
        --accent-soft: #153b36;
        --warn: #fdba74;
        --warn-soft: #3a2617;
        --code: #d5e1d8;
        --track: #2a3630;
        --shadow: none;
      }}
    }}
    @media (max-width: 1180px) {{
      .report-header {{ grid-template-columns: 1fr; }}
      .quality-card {{ grid-column: span 12; }}
      .widget, .widget--word-cloud, .widget--bar-chart, .widget--table, .widget--json, .widget--heatmap, .widget--line-chart {{ grid-column: span 12; }}
    }}
    @media (max-width: 860px) {{
      .shell {{ grid-template-columns: 1fr; }}
      aside {{ position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--line); }}
      main {{ padding: 16px; }}
      .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .project-header {{ position: static; }}
      .event, .bar-row {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <h2>SQLite 导航</h2>
      <p class="meta">按 provider 和 project 浏览 session，再展开查看 chat/message index。</p>
      <input class="search" id="search" type="search" placeholder="过滤 provider / project / session">
      <div class="quick-filters" aria-label="quick filters">
        <button class="filter-chip" type="button" data-filter-value="skill_candidate">成 SKILL 候选</button>
        <button class="filter-chip" type="button" data-filter-value="success_skill_candidate">好案例</button>
        <button class="filter-chip" type="button" data-filter-value="problem_skill_candidate">问题案例</button>
        <button class="filter-chip" type="button" data-filter-value="sentiment:negative">不满意 chat</button>
        <button class="filter-chip" type="button" data-filter-value="failure_skill_candidate">阻塞/失败</button>
        <button class="filter-chip" type="button" data-filter-value="repeat_skill_candidate">重复请求</button>
        <button class="filter-chip" type="button" data-filter-value="dissatisfaction">dissatisfaction</button>
        <button class="filter-chip" type="button" data-filter-value="problem_report">problem report</button>
        <button class="filter-chip" type="button" data-filter-value="correction_request">correction request</button>
      </div>
      {sidebar}
    </aside>
    <main>
      <div class="workspace">
        <section class="report-header">
          <div class="report-title">
            <div class="report-kicker">找到需要被总结成 SKILL 的 sessions</div>
            <h1>Codex SKILL Candidate Finder</h1>
            <p class="meta">Official factors 分析聊天记录并产出结构化信号；SKILL.md 方法层判断哪些 session 值得沉淀成 workflow、troubleshooting、guardrail 或 checklist。好案例和问题案例都会进入候选队列。</p>
            <p class="meta">Ledger: <code>{_esc(str(ledger_path or ""))}</code><br>Generated: {_esc(generated_at)}</p>
          </div>
          <div class="header-card">
            <section class="stats" aria-label="summary">
              <div class="stat"><strong>{len(providers)}</strong><span>Providers</span></div>
              <div class="stat"><strong>{project_count}</strong><span>Projects</span></div>
              <div class="stat"><strong>{len(statuses)}</strong><span>Sessions</span></div>
              <div class="stat"><strong>{len(factor_results)}</strong><span>Factor results</span></div>
            </section>
          </div>
        </section>
        <nav class="tabs" aria-label="workspace tabs">
          <button class="tab-button active" type="button" data-tab-target="skill-candidates">SKILL Candidates</button>
          <button class="tab-button" type="button" data-tab-target="sessions">Sessions</button>
          <button class="tab-button" type="button" data-tab-target="global-canvas">Global Canvas</button>
          <button class="tab-button" type="button" data-tab-target="run-health">Run Health</button>
        </nav>
        <section id="skill-candidates" class="tab-panel active">{quality_body}</section>
        <section id="sessions" class="tab-panel">{sessions_body}</section>
        <section id="global-canvas" class="tab-panel">{canvas_body}</section>
        <section id="run-health" class="tab-panel">{health_body}</section>
      </div>
    </main>
  </div>
  <script>
    const input = document.getElementById("search");
    const providers = Array.from(document.querySelectorAll(".provider[data-search]"));
    const projects = Array.from(document.querySelectorAll(".project[data-search]"));
    const sessions = Array.from(document.querySelectorAll(".session[data-search]"));
    const events = Array.from(document.querySelectorAll(".event[data-search]"));
    const factorResults = Array.from(document.querySelectorAll(".factor-result[data-search]"));
    const widgets = Array.from(document.querySelectorAll(".widget[data-search]"));
    const qualityRows = Array.from(document.querySelectorAll(".quality-row[data-search]"));
    const filterable = [...providers, ...projects, ...sessions, ...events, ...factorResults, ...widgets, ...qualityRows];
    const aliases = new Map([
      ["成skill", "skill_candidate"],
      ["成 skill", "skill_candidate"],
      ["总结成skill", "skill_candidate"],
      ["总结成 skill", "skill_candidate"],
      ["好案例", "success_skill_candidate"],
      ["问题案例", "problem_skill_candidate"],
      ["人工判断", "review_needed"],
      ["不满意", "sentiment:negative"],
      ["负面", "sentiment:negative"],
      ["阻塞", "failure_skill_candidate"],
      ["未完成", "failure_skill_candidate"],
      ["重复请求", "repeat_skill_candidate"],
      ["问题反馈", "problem_report"],
      ["纠正请求", "correction_request"],
    ]);
    function normalizedTerms() {{
      const raw = input.value.trim().toLowerCase();
      if (!raw) return [];
      const expanded = aliases.get(raw) || raw;
      return expanded.split(/\\s+/).filter(Boolean);
    }}
    function matches(node, terms) {{
      if (!terms.length) return true;
      const haystack = node.getAttribute("data-search") || "";
      return terms.every((term) => haystack.includes(term));
    }}
    input.addEventListener("input", () => {{
      const terms = normalizedTerms();
      const hasFilter = terms.length > 0;
      for (const node of filterable) {{
        node.classList.toggle("hidden", hasFilter && !matches(node, terms));
      }}
      for (const session of sessions) {{
        const childMatch = Array.from(session.querySelectorAll(".event[data-search], .factor-result[data-search]"))
          .some((node) => !node.classList.contains("hidden"));
        const sessionMatch = matches(session, terms) || childMatch;
        session.classList.toggle("hidden", hasFilter && !sessionMatch);
        if (hasFilter && sessionMatch) session.open = true;
      }}
      for (const project of projects) {{
        const hasVisibleSession = Boolean(project.querySelector(".session:not(.hidden)"));
        project.classList.toggle("hidden", hasFilter && !hasVisibleSession && !matches(project, terms));
      }}
      for (const provider of providers) {{
        const hasVisibleProject = Boolean(provider.querySelector(".project:not(.hidden)"));
        provider.classList.toggle("hidden", hasFilter && !hasVisibleProject && !matches(provider, terms));
      }}
    }});
    for (const button of document.querySelectorAll("[data-tab-target]")) {{
      button.addEventListener("click", () => {{
        const target = button.getAttribute("data-tab-target");
        document.querySelectorAll("[data-tab-target]").forEach((item) => item.classList.toggle("active", item === button));
        document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === target));
      }});
    }}
    for (const node of document.querySelectorAll("[data-filter-value]")) {{
      node.addEventListener("click", () => {{
        input.value = node.getAttribute("data-filter-value") || "";
        input.dispatchEvent(new Event("input"));
        document.querySelector('[data-tab-target="sessions"]').click();
        input.focus();
      }});
    }}
  </script>
</body>
</html>
"""


def _build_quality_signals(
    statuses: list[SessionAnalysisStatus],
    events_by_session: dict[str, list[SessionEventRecord]],
    results_by_session: dict[str, list[FactorResult]],
) -> list[dict[str, Any]]:
    return [
        _quality_signal_for(
            status,
            events_by_session.get(status.session_id, []),
            results_by_session.get(status.session_id, []),
        )
        for status in statuses
    ]


def _quality_signal_for(
    status: SessionAnalysisStatus,
    events: list[SessionEventRecord],
    results: list[FactorResult],
) -> dict[str, Any]:
    result_by_factor = {result.factor_id: result for result in results}
    present_factors = [factor_id for factor_id in OFFICIAL_QUALITY_FACTOR_IDS if factor_id in result_by_factor]
    metrics = _quality_metrics(result_by_factor)
    score = 0.12
    positives: list[str] = []
    risks: list[str] = []
    diagnostics: list[str] = []

    completion = str(metrics["completion_verdict"])
    if completion == "completed":
        score += 0.12
        positives.append("任务完成信号明确")
    elif completion == "blocked":
        score += 0.30
        risks.append("任务被阻塞")
    elif completion == "not_completed":
        score += 0.34
        risks.append("任务未完成")
    else:
        score += 0.08
        diagnostics.append("任务完成状态未知")

    negative_turns = int(metrics["negative_turn_count"])
    if negative_turns:
        score += min(0.34, 0.20 + 0.04 * negative_turns)
        risks.append(f"用户不满/纠错/问题反馈 {negative_turns} 次")
    elif "official.user-input-sentiment" in result_by_factor:
        score += 0.04
        positives.append("没有发现用户不满信号")

    positive_turns = int(metrics["positive_turn_count"])
    if positive_turns:
        score += min(0.08, 0.03 * positive_turns)
        positives.append(f"用户正向反馈 {positive_turns} 次")

    repeated_count = int(metrics["repeated_request_count"])
    if repeated_count:
        score += min(0.30, 0.18 + 0.04 * repeated_count)
        risks.append(f"重复请求链 {repeated_count} 条")
    elif "official.repeated-request" in result_by_factor:
        score += 0.03
        positives.append("没有发现未解决重复请求")

    failure_count = int(metrics["tool_failure_count"])
    if failure_count:
        if completion != "completed" or failure_count >= 3:
            risks.append(f"工具失败 {failure_count} 次")
        else:
            diagnostics.append(f"工具失败 {failure_count} 次，但未直接推翻完成信号")
        score += min(0.28, 0.07 * failure_count)
    elif "official.tool-failure-frequency" in result_by_factor:
        score += 0.02
        positives.append("没有发现工具失败")

    key_sentence_count = int(metrics["key_sentence_count"])
    if key_sentence_count:
        score += min(0.16, 0.025 * key_sentence_count)
        positives.append("存在可追踪的关键行动/产出句")
    else:
        diagnostics.append("关键句密度不足或未命中")

    resource_count = int(metrics["resource_count"])
    if resource_count:
        score += min(0.08, 0.018 * resource_count)
        diagnostics.append(f"识别到 {resource_count} 类资源使用")

    usage_sentence_count = int(metrics["usage_sentence_count"])
    if usage_sentence_count:
        score += min(0.05, 0.01 * usage_sentence_count)
        diagnostics.append(f"识别到 {usage_sentence_count} 个高频表达/沟通模式")

    coverage = len(present_factors) / float(len(OFFICIAL_QUALITY_FACTOR_IDS))
    score += (coverage - 0.5) * 0.04
    score = round(max(0.0, min(1.0, score)), 2)
    confidence = round(min(0.95, 0.35 + 0.6 * coverage), 2)

    label = _quality_label(metrics, score)
    label_zh = QUALITY_LABELS[label]
    recommendation = _skill_recommendation(label, metrics)
    next_action = _skill_next_action(label)
    conclusion = _skill_conclusion(label, recommendation)
    evidence_refs = _quality_evidence_refs(results)
    previews = _quality_evidence_previews(events, evidence_refs)
    reasons = (risks or positives or diagnostics)[:4]
    if not reasons:
        reasons = ["factor 信号不足，暂不直接沉淀"]

    signal = {
        "session_id": status.session_id,
        "title": status.session_title or status.session_id,
        "project_label": _project_label(status),
        "provider": status.provider,
        "source_ref": status.source_ref,
        "updated_at": status.session_updated_at or status.discovered_at,
        "score": score,
        "confidence": confidence,
        "label": label,
        "label_zh": label_zh,
        "recommendation": recommendation,
        "next_action": next_action,
        "conclusion": conclusion,
        "is_skill_candidate": label not in {"not_skill_candidate", "review_needed"},
        "present_factor_count": len(present_factors),
        "factor_coverage": round(coverage, 2),
        "positives": positives,
        "risks": risks,
        "diagnostics": diagnostics,
        "reasons": reasons,
        "evidence_refs": evidence_refs,
        "evidence_previews": previews,
        **metrics,
    }
    signal["search"] = _quality_search(signal)
    return signal


def _quality_metrics(result_by_factor: dict[str, FactorResult]) -> dict[str, Any]:
    sentiment = result_by_factor.get("official.user-input-sentiment")
    completion = result_by_factor.get("official.task-completion")
    repeated = result_by_factor.get("official.repeated-request")
    failure = result_by_factor.get("official.tool-failure-frequency")
    resource = result_by_factor.get("official.session-resource-usage")
    key_sentence = result_by_factor.get("official.key-sentence-trends")
    usage_sentence = result_by_factor.get("official.usage-sentence-cloud")

    sentiment_records = _dataset_records(sentiment, "user_input_sentiment")
    sentiment_values = [
        str(record.get("sentiment_kind") or "")
        for record in sentiment_records
        if str(record.get("sentiment_kind") or "")
    ]
    dominant_sentiment = (
        str(sentiment.statistics.get("dominant_sentiment_kind") or "")
        if sentiment is not None
        else ""
    )
    tag_sentiment = _first_tag_value(sentiment, "user_sentiment")
    dissatisfaction_count = sum(1 for value in sentiment_values if value == "dissatisfaction")
    problem_report_count = sum(1 for value in sentiment_values if value == "problem_report")
    correction_request_count = sum(1 for value in sentiment_values if value == "correction_request")
    negative_count = dissatisfaction_count + problem_report_count + correction_request_count
    if sentiment is not None and not sentiment_values:
        negative_count = int(_float_value(sentiment.statistics.get("dissatisfaction_turn_count"), 0.0))
    if sentiment is not None and negative_count == 0 and (tag_sentiment in NEGATIVE_SENTIMENT_VALUES or dominant_sentiment in NEGATIVE_SENTIMENT_VALUES):
        negative_count = 1
        if tag_sentiment == "problem_report" or dominant_sentiment == "problem_report":
            problem_report_count = 1
        elif tag_sentiment == "correction_request" or dominant_sentiment == "correction_request":
            correction_request_count = 1
        else:
            dissatisfaction_count = 1
    max_dissatisfaction = max(
        [_float_value(record.get("dissatisfaction_score"), 0.0) for record in sentiment_records] or [0.0]
    )

    completion_verdict = _first_tag_value(completion, "task_completion") or (
        str(completion.statistics.get("verdict") or "") if completion is not None else ""
    )
    completion_score = _score_value(completion, "task_completion_score", 0.0)

    return {
        "dominant_sentiment": dominant_sentiment or "unknown",
        "negative_turn_count": negative_count,
        "dissatisfaction_turn_count": dissatisfaction_count,
        "problem_report_count": problem_report_count,
        "correction_request_count": correction_request_count,
        "positive_turn_count": sum(1 for value in sentiment_values if value == "positive_feedback")
        or int(tag_sentiment == "positive_feedback" or dominant_sentiment == "positive_feedback"),
        "max_dissatisfaction_score": round(max_dissatisfaction, 4),
        "completion_verdict": completion_verdict or "unknown",
        "completion_score": completion_score,
        "repeated_request_count": int(_score_value(repeated, "repeated_request_count", 0.0)),
        "tool_failure_count": int(_score_value(failure, "tool_failure_count", 0.0)),
        "resource_count": int(_score_value(resource, "resource_count", 0.0)),
        "key_sentence_count": int(_score_value(key_sentence, "key_sentence_cluster_count", 0.0)),
        "usage_sentence_count": int(_score_value(usage_sentence, "usage_sentence_count", 0.0)),
    }


def _quality_label(metrics: dict[str, Any], score: float) -> str:
    negative_count = int(metrics["negative_turn_count"])
    strong_user_problem = int(metrics["problem_report_count"]) > 0 or int(metrics["correction_request_count"]) > 0
    completion = str(metrics["completion_verdict"])
    repeated_count = int(metrics["repeated_request_count"])
    failure_count = int(metrics["tool_failure_count"])
    key_sentence_count = int(metrics["key_sentence_count"])
    resource_count = int(metrics["resource_count"])
    usage_sentence_count = int(metrics["usage_sentence_count"])

    if strong_user_problem or negative_count >= 2 or (negative_count and (completion in {"blocked", "not_completed"} or repeated_count or failure_count >= 2)):
        return "problem_skill_candidate"
    if repeated_count >= 2 or (repeated_count and (negative_count or completion != "completed")):
        return "repeat_skill_candidate"
    if completion in {"blocked", "not_completed"} or failure_count >= 3:
        return "failure_skill_candidate"
    if (
        completion == "completed"
        and key_sentence_count >= 5
        and resource_count >= 1
        and failure_count <= 2
        and negative_count == 0
        and repeated_count == 0
    ):
        return "success_skill_candidate"
    if (key_sentence_count >= 10 and resource_count >= 1) or usage_sentence_count >= 15:
        return "workflow_skill_candidate"
    if score >= 0.45:
        return "review_needed"
    return "not_skill_candidate"


def _skill_recommendation(label: str, metrics: dict[str, Any]) -> str:
    if label == "success_skill_candidate":
        return "总结成 workflow SKILL：抽取触发条件、稳定步骤、工具顺序、验收标准"
    if label == "problem_skill_candidate":
        return "更新或新建 guardrail SKILL：补充用户不满、纠错、问题反馈的处理规则"
    if label == "failure_skill_candidate":
        if int(metrics["tool_failure_count"]) >= 3:
            return "总结成 troubleshooting SKILL：沉淀工具失败诊断、环境检查、恢复路径"
        return "总结成 failure-review SKILL：记录阻塞原因、前置检查、退出条件"
    if label == "repeat_skill_candidate":
        return "补充需求澄清/checklist SKILL：避免同一请求被反复提出"
    if label == "workflow_skill_candidate":
        return "总结成 workflow/checklist SKILL：提炼可复用流程和关键句模式"
    if label == "review_needed":
        return "人工复核后决定：信号存在但不足以直接沉淀"
    return "暂不沉淀：常规完成或信号不足"


def _skill_next_action(label: str) -> str:
    if label == "not_skill_candidate":
        return "跳过，除非人工检索时需要查看"
    if label == "review_needed":
        return "打开 session，确认是否有可迁移规则；没有就跳过"
    return "打开 session，抽取触发条件、操作步骤、失败/成功证据、验证命令，写入对应 SKILL"


def _skill_conclusion(label: str, recommendation: str) -> str:
    if label == "not_skill_candidate":
        return "结论：暂不需要总结成 SKILL"
    if label == "review_needed":
        return "结论：需要人工判断是否总结成 SKILL"
    return f"结论：建议总结成 SKILL。{recommendation}"


def _render_quality_signals(signals: list[dict[str, Any]]) -> str:
    if not signals:
        return '<section class="panel project"><h2>SKILL 候选识别结果</h2><p class="meta">还没有可分析的 session。</p></section>'

    by_label = defaultdict(int)
    for signal in signals:
        by_label[str(signal["label"])] += 1
    candidates = [signal for signal in signals if signal.get("is_skill_candidate")]
    success_queue = [signal for signal in candidates if signal["label"] == "success_skill_candidate"]
    problem_queue = [
        signal
        for signal in candidates
        if signal["label"] in {"problem_skill_candidate", "failure_skill_candidate", "repeat_skill_candidate"}
    ]
    review_queue = [signal for signal in signals if signal["label"] == "review_needed"]
    candidates_sorted = sorted(candidates, key=lambda item: (-float(item["score"]), item["session_id"]))
    success_sorted = sorted(success_queue, key=lambda item: (-float(item["score"]), item["session_id"]))
    problem_sorted = sorted(problem_queue, key=lambda item: (-float(item["score"]), item["session_id"]))
    review_sorted = sorted(review_queue, key=lambda item: (-float(item["score"]), item["session_id"]))
    all_sorted = sorted(signals, key=lambda item: (-float(item["score"]), item["session_id"]))

    return (
        '<section class="provider" data-search="skill candidates skill_candidate success_skill_candidate problem_skill_candidate failure_skill_candidate repeat_skill_candidate workflow_skill_candidate">'
        '<div class="provider-header"><div><h2>SKILL 候选识别结果</h2>'
        '<p class="meta">目标是找到需要被总结成 SKILL 的 sessions。好案例用于沉淀 workflow，问题案例用于沉淀 troubleshooting、guardrail 和 checklist。这里不新增 ledger 数据，只在 HTML 生成时派生候选结论。</p></div>'
        f'<span class="badge">{len(signals)} sessions</span></div>'
        '<div class="stats">'
        f'<div class="stat"><strong>{min(len(candidates), QUALITY_TABLE_LIMIT)}</strong><span>优先沉淀队列</span></div>'
        f'<div class="stat"><strong>{len(candidates)}</strong><span>候选证据池</span></div>'
        f'<div class="stat"><strong>{by_label["problem_skill_candidate"]}</strong><span>用户不满/纠错</span></div>'
        f'<div class="stat"><strong>{by_label["success_skill_candidate"]}</strong><span>好案例 workflow</span></div>'
        f'<div class="stat"><strong>{by_label["failure_skill_candidate"]}</strong><span>阻塞/失败</span></div>'
        f'<div class="stat"><strong>{by_label["repeat_skill_candidate"]}</strong><span>重复请求</span></div>'
        "</div>"
        '<div class="quality-grid" style="margin-top:14px">'
        f'{_render_quality_method_card(by_label, len(candidates))}'
        f'{_render_quality_table("优先沉淀队列", "先看这批 evidence sessions，不是一条 session 写一个 SKILL，而是从这里聚类抽取规则、步骤和反例。", candidates_sorted)}'
        f'{_render_quality_table("好案例候选", "完成闭环且有可迁移流程证据，适合总结成 workflow SKILL。", success_sorted)}'
        f'{_render_quality_table("问题案例候选", "用户不满、阻塞、工具失败或重复请求，适合总结成 troubleshooting / guardrail。", problem_sorted)}'
        f'{_render_quality_table("人工判断队列", "信号存在但结论不够强，打开 session 后决定是否沉淀。", review_sorted)}'
        f'{_render_quality_table("全量矩阵", "所有 session 的派生 SKILL 候选结论和核心 factor 指标。", all_sorted)}'
        "</div></section>"
    )


def _render_quality_method_card(by_label: dict[str, int], candidate_count: int) -> str:
    items = [
        ("好案例", "`task-completion` completed 且没有明显不满/重复请求时，看 key sentence 和 resource 是否能抽成稳定 workflow。"),
        ("用户纠错", "`user-input-sentiment` 命中 dissatisfaction/problem_report/correction_request 时，优先沉淀 guardrail。"),
        ("重复请求", "`repeated-request` 命中时，沉淀需求澄清、验收标准或防返工 checklist。"),
        ("阻塞失败", "`task-completion` blocked/not_completed 或工具失败集中时，沉淀 troubleshooting 和环境前置检查。"),
        ("流程证据", "`session-resource-usage` 解释 tool/skill/MCP 使用路径，帮助写 SKILL 的步骤和依赖。"),
        ("表达模式", "`key-sentence-trends` 和 `usage-sentence-cloud` 提供触发语、关键动作、输出对象和反例。"),
    ]
    body = "".join(
        '<div class="method-item">'
        f'<strong>{_esc(title)}</strong>'
        f'<p class="meta">{_esc(text)}</p>'
        "</div>"
        for title, text in items
    )
    return (
        '<article class="quality-card quality-card--wide">'
        '<h3>结论：先聚类沉淀成几类 SKILL，不是一条 session 写一个 SKILL</h3>'
        f'<p class="meta">当前候选证据池有 {candidate_count} 个 sessions。优先从前 {min(candidate_count, QUALITY_TABLE_LIMIT)} 条抽样，按用户纠错、好案例 workflow、阻塞失败、重复请求四类聚类沉淀。问题案例可沉淀 guardrail/troubleshooting，好案例可沉淀 workflow。</p>'
        '<div class="kv">'
        f'<span class="role">guardrail evidence={by_label["problem_skill_candidate"]}</span>'
        f'<span class="role">workflow evidence={by_label["success_skill_candidate"] + by_label["workflow_skill_candidate"]}</span>'
        f'<span class="role">troubleshooting evidence={by_label["failure_skill_candidate"]}</span>'
        f'<span class="role">clarification evidence={by_label["repeat_skill_candidate"]}</span>'
        '</div>'
        f'<div class="method-list">{body}</div>'
        "</article>"
    )


def _render_quality_table(title: str, description: str, signals: list[dict[str, Any]]) -> str:
    if not signals:
        return (
            '<article class="quality-card quality-card--wide">'
            f'<h3>{_esc(title)}</h3><p class="meta">{_esc(description)}</p>'
            '<p class="meta">没有命中的 session。</p></article>'
        )
    rows = signals[:QUALITY_TABLE_LIMIT]
    chunks = [
        '<article class="quality-card quality-card--wide">',
        '<div class="widget-header">',
        f'<div><h3>{_esc(title)}</h3><p class="meta">{_esc(description)}</p></div>',
        f'<span class="badge">{len(signals)} sessions</span>',
        "</div>",
        '<div class="table-wrap"><table class="data-table skill-candidate-table"><thead><tr>',
        "<th>结论</th><th>建议沉淀成</th><th>session</th><th>为什么</th><th>factor 指标</th><th>证据</th><th>下一步</th>",
        "</tr></thead><tbody>",
    ]
    for signal in rows:
        risks = "; ".join(str(item) for item in signal.get("risks", [])[:3]) or "无明显风险"
        reasons = "; ".join(str(item) for item in signal.get("reasons", [])[:3])
        evidence = "; ".join(str(item) for item in signal.get("evidence_previews", [])[:2]) or _refs_preview(signal.get("evidence_refs", []))
        signal_summary = (
            f'不满 {signal["negative_turn_count"]} / '
            f'重复 {signal["repeated_request_count"]} / '
            f'失败 {signal["tool_failure_count"]} / '
            f'关键句 {signal["key_sentence_count"]}'
        )
        chunks.append(
            f'<tr class="quality-row" data-search="{_attr(str(signal["search"]))}" data-filter-value="{_attr(str(signal["session_id"]))}">'
            f'<td><span class="score-pill">{_esc(_format_number(float(signal["score"])))}</span><br><strong>{_esc(str(signal["label_zh"]))}</strong><br><code>{_esc(str(signal["label"]))}</code></td>'
            f'<td><strong>{_esc(str(signal["recommendation"]))}</strong></td>'
            f'<td><strong>{_esc(str(signal["title"]))}</strong><br><code>{_esc(str(signal["session_id"]))}</code><br><span class="meta">{_esc(str(signal["project_label"]))}</span></td>'
            f'<td>{_esc(str(signal["conclusion"]))}<br><span class="meta">{_esc(reasons or risks)}</span></td>'
            f'<td>{_esc(signal_summary)}<br><span class="meta">completion { _esc(str(signal["completion_verdict"])) } / coverage {_esc(_format_number(float(signal["factor_coverage"])))}</span></td>'
            f'<td>{_esc(evidence)}</td>'
            f'<td>{_esc(str(signal["next_action"]))}</td>'
            "</tr>"
        )
    chunks.append("</tbody></table></div></article>")
    return "\n".join(chunks)


def _render_sidebar(
    providers: dict[str, dict[tuple[str, str], list[SessionAnalysisStatus]]],
) -> str:
    if not providers:
        return '<p class="meta">SQLite 里还没有扫描到 session。</p>'
    chunks: list[str] = ['<nav class="nav-group">']
    for provider, projects in providers.items():
        chunks.append(f'<div class="nav-provider">{_esc(provider)}</div>')
        for (project_key, project_label), sessions in projects.items():
            anchor = _anchor(provider, project_key, project_label)
            chunks.append(
                f'<a class="nav-project" href="#{anchor}">{_esc(project_label)} '
                f'<span class="badge">{len(sessions)}</span></a>'
            )
    chunks.append("</nav>")
    return "\n".join(chunks)


def _render_providers(
    providers: dict[str, dict[tuple[str, str], list[SessionAnalysisStatus]]],
    events_by_session: dict[str, list[SessionEventRecord]],
    results_by_session: dict[str, list[FactorResult]],
    quality_by_session: dict[str, dict[str, Any]],
) -> str:
    if not providers:
        return '<section class="panel project"><h2>没有数据</h2><p class="meta">先运行 scanner 写入 SQLite。</p></section>'
    provider_chunks: list[str] = []
    for provider, projects in providers.items():
        session_count = sum(len(sessions) for sessions in projects.values())
        provider_chunks.append(
            f'<section class="provider" data-provider="{_attr(provider)}" data-search="{_attr(provider.lower())}">'
            f'<div class="provider-header"><h2>{_esc(provider)}</h2><span class="badge">{session_count} sessions</span></div>'
        )
        for (project_key, project_label), sessions in projects.items():
            project_events = sum(len(events_by_session.get(status.session_id, [])) for status in sessions)
            provider_chunks.append(
                f'<section class="panel project" id="{_anchor(provider, project_key, project_label)}" '
                f'data-search="{_attr(_search_blob(provider, project_key, project_label, sessions))}">'
                f'<div class="project-header"><div><h3>{_esc(project_label)}</h3>'
                f'<div class="project-key"><code>{_esc(project_key)}</code></div></div>'
                f'<span class="badge">{len(sessions)} sessions / {project_events} messages</span></div>'
            )
            for status in sessions:
                provider_chunks.append(
                    _render_session(
                        status,
                        events_by_session.get(status.session_id, []),
                        results_by_session.get(status.session_id, []),
                        quality_by_session.get(status.session_id),
                    )
                )
            provider_chunks.append("</section>")
        provider_chunks.append("</section>")
    return "\n".join(provider_chunks)


def _render_session(
    status: SessionAnalysisStatus,
    events: list[SessionEventRecord],
    results: list[FactorResult],
    quality_signal: dict[str, Any] | None,
) -> str:
    title = status.session_title or status.session_id
    rendered_events, omitted_count = _events_for_render(events)
    search = _search_blob(
        status.provider,
        status.project_key,
        status.project_label,
        [status],
        *(_event_search(event) for event in rendered_events),
        *(_factor_search(result) for result in results),
        _quality_search(quality_signal) if quality_signal else "",
    )
    quality_badge = ""
    if quality_signal:
        quality_badge = (
            f'<span class="badge">{_esc(str(quality_signal["label_zh"]))}</span>'
            f'<span class="badge">{_esc(_format_number(float(quality_signal["score"])))} skill value</span>'
        )
    chunks = [
        f'<details class="session" data-search="{_attr(search)}">',
        "<summary>",
        '<div class="session-title">',
        f'<span>{_esc(title)}</span>',
        f'<span class="badge">{len(events) or status.event_count} messages</span>',
        f'<span class="badge">{len(results) or status.analyzed_factor_count} factors</span>',
        quality_badge,
        "</div>",
        '<div class="session-subtitle">',
        f'<code>{_esc(status.session_id)}</code>',
        f'<span>updated {_esc(status.session_updated_at or status.discovered_at)}</span>',
        f'<span>source <code>{_esc(status.source_ref)}</code></span>',
        "</div>",
        "</summary>",
    ]
    if rendered_events:
        chunks.append('<ol class="chat">')
        if omitted_count:
            chunks.append(
                '<li class="event"><div class="event-index">...</div>'
                f'<div class="event-body"><span class="empty">已省略 {_esc(omitted_count)} 条低信号事件；完整索引保留在 SQLite ledger。</span></div></li>'
            )
        chunks.extend(_render_event(event) for event in rendered_events)
        chunks.append("</ol>")
    else:
        chunks.append('<div class="event"><div></div><div class="empty">没有 message index。先运行 scanner。</div></div>')
    if results:
        chunks.append(_render_session_results(results))
    chunks.append("</details>")
    return "\n".join(chunks)


def _events_for_render(events: list[SessionEventRecord]) -> tuple[list[SessionEventRecord], int]:
    if len(events) <= MAX_RENDERED_EVENTS_PER_SESSION:
        return events, 0

    selected: dict[tuple[str, str], SessionEventRecord] = {}
    for event in events:
        if event.tags:
            selected[(event.session_id, event.event_id)] = event

    for event in events[:CONTEXT_EVENTS_PER_EDGE]:
        selected[(event.session_id, event.event_id)] = event
    for event in events[-CONTEXT_EVENTS_PER_EDGE:]:
        selected[(event.session_id, event.event_id)] = event

    rendered = sorted(selected.values(), key=lambda item: item.event_index)
    if len(rendered) > MAX_RENDERED_EVENTS_PER_SESSION:
        tagged = [event for event in rendered if event.tags]
        context = [event for event in rendered if not event.tags]
        rendered = sorted((tagged[:MAX_RENDERED_EVENTS_PER_SESSION] or context[:MAX_RENDERED_EVENTS_PER_SESSION]), key=lambda item: item.event_index)

    return rendered, len(events) - len(rendered)


def _render_event(event: SessionEventRecord) -> str:
    content = event.content or event.tool_result_preview
    content_html = _esc(content) if content else '<span class="empty">scan-only id record: content not materialized</span>'
    tool_html = f'<span class="role">tool: {_esc(event.tool_name)}</span>' if event.tool_name else ""
    tags_html = "".join(
        f'<span class="role">{_esc(tag.factor_id)}:{_esc(tag.tag_type)}={_esc(tag.tag_value)}</span>'
        for tag in event.tags
    )
    source = _esc(f"{event.source_ref}:{event.source_line}" if event.source_line else event.source_ref)
    return (
        f'<li class="event" data-search="{_attr(_event_search(event))}">'
        f'<div class="event-index">#{event.event_index}</div>'
        '<div class="event-body">'
        '<div class="event-line">'
        f'<span class="role">{_esc(event.role or "unknown")}</span>'
        f'<code>{_esc(event.event_id)}</code>'
        f"{tool_html}{tags_html}"
        "</div>"
        f'<div class="content">{content_html}</div>'
        f'<div class="source">source <code>{source}</code></div>'
        "</div>"
        "</li>"
    )


def _render_session_results(results: list[FactorResult]) -> str:
    chunks = ['<section class="factor-drawer"><h4>Session Detail · Factor Results</h4>']
    for result in sorted(results, key=lambda item: item.factor_id):
        chunks.append(
            f'<details class="factor-result" data-search="{_attr(_factor_search(result))}"><summary><strong>{_esc(result.factor_id)}</strong> '
            f'<span class="badge">{_esc(result.status)}</span></summary>'
            '<div class="factor-body">'
            f'<div class="kv">{_render_tags(result.tags)}</div>'
            f'{_render_scores(result.scores)}'
            f'{_render_result_datasets(result)}'
            "</div></details>"
        )
    chunks.append("</section>")
    return "\n".join(chunks)


def _render_result_datasets(result: FactorResult) -> str:
    chunks: list[str] = []
    for dataset in result.datasets:
        records = dataset.get("records") if isinstance(dataset.get("records"), list) else []
        title = str(dataset.get("id") or "dataset")
        semantic_type = str(dataset.get("semantic_type") or "")
        chunks.append(
            '<div class="dataset-summary">'
            f'<span class="role">{_esc(title)}</span>'
            f'<span class="meta">{_esc(semantic_type)}</span>'
            f'<span class="badge">{len(records)} records</span>'
            "</div>"
        )
    return "\n".join(chunks)


def _render_global_canvas(factor_results: list[FactorResult]) -> str:
    widgets = _global_widgets(factor_results)
    if not widgets:
        return '<section class="panel project"><h2>Global Canvas</h2><p class="meta">还没有可展示的 factor presentation。</p></section>'
    chunks = ['<section class="provider"><div class="provider-header"><h2>Global Canvas</h2><span class="badge">可插拔 widget</span></div><div class="widget-grid">']
    for widget in widgets:
        chunks.append(
            _render_widget(
                str(widget["factor_id"]),
                widget["presentation"],
                widget["dataset"],
                widget["records"],
                compact=False,
            )
        )
    chunks.append("</div></section>")
    return "\n".join(chunks)


def _global_widgets(factor_results: list[FactorResult]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for result in factor_results:
        for presentation in result.presentations:
            routes = presentation.get("routes") if isinstance(presentation.get("routes"), list) else []
            if routes and "canvas.global.insights" not in routes:
                continue
            dataset = _dataset_for(result, str(presentation.get("data_ref") or ""))
            if dataset is None:
                continue
            key = (result.factor_id, str(presentation.get("id") or presentation.get("data_ref") or "presentation"))
            entry = grouped.setdefault(
                key,
                {
                    "factor_id": result.factor_id,
                    "presentation": presentation,
                    "dataset": {**dataset, "records": []},
                    "records": [],
                },
            )
            records = dataset.get("records")
            if isinstance(records, list):
                entry["records"].extend(record for record in records if isinstance(record, dict))
    widgets = []
    for entry in grouped.values():
        records = _aggregate_records(entry["records"], entry["presentation"])
        dataset = {**entry["dataset"], "records": records}
        widgets.append({**entry, "dataset": dataset, "records": records})
    return sorted(widgets, key=lambda item: _int_value(item["presentation"].get("priority"), 100))[:30]


def _aggregate_records(records: list[dict[str, Any]], presentation: dict[str, Any]) -> list[dict[str, Any]]:
    bindings = presentation.get("bindings") if isinstance(presentation.get("bindings"), dict) else {}
    word_field = str(bindings.get("word") or "")
    weight_field = str(bindings.get("weight") or "")
    x_field = str(bindings.get("x") or "")
    y_field = str(bindings.get("y") or "")
    color_field = str(bindings.get("color") or "")
    series_field = str(bindings.get("series") or "")
    group_field = str(bindings.get("group") or "")

    if word_field and weight_field:
        totals: dict[str, float] = defaultdict(float)
        labels: dict[str, str] = {}
        colors: dict[str, str] = {}
        for record in records:
            word = str(record.get(word_field) or "")
            color = str(record.get(color_field) or "") if color_field else ""
            if word:
                key = f"{color}:{word}" if color else word
                labels[key] = word
                if color:
                    colors[key] = color
                totals[key] += _float_value(record.get(weight_field), 1.0)
        return [
            {
                word_field: labels.get(key, key),
                weight_field: round(value, 4),
                **({color_field: colors[key]} if color_field and key in colors else {}),
            }
            for key, value in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:50]
        ]

    if x_field and y_field and color_field:
        totals = defaultdict(float)
        for record in records:
            key = (str(record.get(x_field) or ""), str(record.get(y_field) or ""))
            if key[0] or key[1]:
                totals[key] += _float_value(record.get(color_field), 0.0)
        return [
            {x_field: key[0], y_field: key[1], color_field: round(value, 4)}
            for key, value in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:50]
        ]

    if x_field and y_field and series_field:
        totals = defaultdict(float)
        for record in records:
            key = (
                str(record.get(x_field) or ""),
                str(record.get(series_field) or ""),
                str(record.get(group_field) or "") if group_field else "",
            )
            if key[0] or key[1]:
                totals[key] += _float_value(record.get(y_field), 0.0)
        return [
            {
                x_field: key[0],
                series_field: key[1],
                y_field: round(value, 4),
                **({group_field: key[2]} if group_field and key[2] else {}),
            }
            for key, value in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:50]
        ]

    if x_field and y_field:
        totals = defaultdict(float)
        for record in records:
            key = str(record.get(x_field) or "")
            if key:
                totals[key] += _float_value(record.get(y_field), 0.0)
        return [
            {x_field: key, y_field: round(value, 4)}
            for key, value in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:50]
        ]

    return records[:50]


def _render_widget(
    factor_id: str,
    presentation: dict[str, Any],
    dataset: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    compact: bool,
) -> str:
    title = str(presentation.get("title") or presentation.get("id") or factor_id)
    component_ref = str(presentation.get("component_ref") or "ui.native-static.table.v1")
    component_class = _component_class(component_ref)
    body = _render_component(component_ref, presentation, records, compact=compact)
    return (
        f'<article class="widget {component_class}" data-search="{_attr(_records_search(records))}">'
        '<div class="widget-header">'
        f'<div class="widget-title"><h3>{_esc(title)}</h3>'
        f'<span class="component-ref">{_esc(factor_id)} · {_esc(component_ref)} · {_esc(str(dataset.get("semantic_type") or ""))}</span></div>'
        f'<span class="badge">{len(records)} rows</span>'
        "</div>"
        f"{body}"
        "</article>"
    )


def _render_component(component_ref: str, presentation: dict[str, Any], records: list[dict[str, Any]], *, compact: bool) -> str:
    if not records:
        return '<p class="meta">没有 dataset records。</p>'
    if component_ref.endswith("word-cloud.v1"):
        return _render_word_cloud(presentation, records)
    if component_ref.endswith("bar-chart.v1"):
        return _render_bar_chart(presentation, records)
    return _render_table(records[:8 if compact else 20])


def _component_class(component_ref: str) -> str:
    for name in ("word-cloud", "bar-chart", "line-chart", "heatmap", "table", "json"):
        if f"{name}.v1" in component_ref:
            return f"widget--{name}"
    return "widget--table"


def _render_word_cloud(presentation: dict[str, Any], records: list[dict[str, Any]]) -> str:
    bindings = presentation.get("bindings") if isinstance(presentation.get("bindings"), dict) else {}
    word_field = str(bindings.get("word") or "text")
    weight_field = str(bindings.get("weight") or "value")
    values = [_float_value(record.get(weight_field), 1.0) for record in records]
    max_value = max(values) if values else 1.0
    chunks = ['<div class="cloud">']
    for record in records[:35]:
        word = str(record.get(word_field) or "")
        if not word:
            continue
        weight = _float_value(record.get(weight_field), 1.0)
        size = 12 + int(18 * (weight / max_value if max_value else 0))
        chunks.append(
            f'<span class="cloud-word" style="font-size:{size}px" '
            f'data-filter-value="{_attr(word)}">{_esc(word)}</span>'
        )
    chunks.append("</div>")
    return "\n".join(chunks)


def _render_bar_chart(presentation: dict[str, Any], records: list[dict[str, Any]]) -> str:
    bindings = presentation.get("bindings") if isinstance(presentation.get("bindings"), dict) else {}
    x_field = str(bindings.get("x") or "label")
    y_field = str(bindings.get("y") or "count")
    values = [_float_value(record.get(y_field), 0.0) for record in records]
    max_value = max(values) if values else 1.0
    chunks = ['<div class="bars">']
    for record in records[:20]:
        label = str(record.get(x_field) or "")
        value = _float_value(record.get(y_field), 0.0)
        width = int(100 * (value / max_value if max_value else 0))
        chunks.append(
            '<div class="bar-row">'
            f'<div class="bar-label" title="{_attr(label)}" data-filter-value="{_attr(label)}">{_esc(label)}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div>'
            f'<code>{_esc(_format_number(value))}</code>'
            "</div>"
        )
    chunks.append("</div>")
    return "\n".join(chunks)


def _render_table(records: list[dict[str, Any]]) -> str:
    if not records:
        return '<p class="meta">没有 rows。</p>'
    columns = list(records[0].keys())[:8]
    chunks = ['<div class="table-wrap"><table class="data-table"><thead><tr>']
    chunks.extend(f"<th>{_esc(column)}</th>" for column in columns)
    chunks.append("</tr></thead><tbody>")
    for record in records:
        chunks.append(f'<tr data-filter-value="{_attr(_record_search(record))}">')
        for column in columns:
            chunks.append(f"<td>{_esc(_display_value(record.get(column)))}</td>")
        chunks.append("</tr>")
    chunks.append("</tbody></table></div>")
    return "\n".join(chunks)


def _render_run_health(
    *,
    statuses: list[SessionAnalysisStatus],
    events: list[SessionEventRecord],
    factor_results: list[FactorResult],
    ledger_path: Path | str | None,
    generated_at: str,
) -> str:
    matched = sum(1 for result in factor_results if result.status == "matched")
    not_matched = sum(1 for result in factor_results if result.status == "not_matched")
    factor_ids = {result.factor_id for result in factor_results}
    db_size = Path(str(ledger_path)).stat().st_size if ledger_path and Path(str(ledger_path)).exists() else 0
    return (
        '<section class="panel project"><div class="provider-header"><h2>Run Health</h2>'
        f'<span class="badge">{_esc(generated_at)}</span></div>'
        '<div class="stats">'
        f'<div class="stat"><strong>{len(statuses)}</strong><span>Sessions</span></div>'
        f'<div class="stat"><strong>{len(events)}</strong><span>Chat messages</span></div>'
        f'<div class="stat"><strong>{len(factor_ids)}</strong><span>Factors</span></div>'
        f'<div class="stat"><strong>{len(factor_results)}</strong><span>Results</span></div>'
        f'<div class="stat"><strong>{matched}</strong><span>Matched</span></div>'
        f'<div class="stat"><strong>{not_matched}</strong><span>Not matched</span></div>'
        f'<div class="stat"><strong>{_esc(_format_bytes(db_size))}</strong><span>SQLite size</span></div>'
        f'<div class="stat"><strong>{sum(1 for event in events if event.tags)}</strong><span>Tagged events</span></div>'
        "</div>"
        f'<p class="meta">Ledger: <code>{_esc(str(ledger_path or ""))}</code></p>'
        "</section>"
    )


def _dataset_records(result: FactorResult | None, dataset_id: str) -> list[dict[str, Any]]:
    if result is None:
        return []
    for dataset in result.datasets:
        if str(dataset.get("id") or "") != dataset_id:
            continue
        records = dataset.get("records")
        if isinstance(records, list):
            return [record for record in records if isinstance(record, dict)]
    return []


def _first_tag_value(result: FactorResult | None, tag_type: str) -> str:
    if result is None:
        return ""
    for tag in result.tags:
        if str(tag.get("type") or "") == tag_type:
            return str(tag.get("value") or "")
    return ""


def _score_value(result: FactorResult | None, key: str, default: float) -> float:
    if result is None:
        return default
    return _float_value(result.scores.get(key), default)


def _quality_evidence_refs(results: list[FactorResult]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    priority = {
        "official.user-input-sentiment": 0,
        "official.task-completion": 1,
        "official.repeated-request": 2,
        "official.tool-failure-frequency": 3,
        "official.key-sentence-trends": 4,
        "official.session-resource-usage": 5,
        "official.usage-sentence-cloud": 6,
    }
    for result in sorted(results, key=lambda item: priority.get(item.factor_id, 99)):
        for ref in result.evidence_refs:
            ref_id = str(ref.get("ref_id") or "")
            kind = str(ref.get("kind") or "event")
            if not ref_id or (ref_id, kind) in seen:
                continue
            seen.add((ref_id, kind))
            refs.append({"ref_id": ref_id, "kind": kind, "factor_id": result.factor_id})
            if len(refs) >= 8:
                return refs
    return refs


def _quality_evidence_previews(events: list[SessionEventRecord], refs: list[dict[str, str]]) -> list[str]:
    events_by_id = {event.event_id: event for event in events}
    previews: list[str] = []
    for ref in refs:
        event = events_by_id.get(str(ref.get("ref_id") or ""))
        if event is None:
            continue
        content = (event.content or event.tool_result_preview or "").strip()
        if not content:
            continue
        preview = content.replace("\n", " ")
        if len(preview) > 120:
            preview = f"{preview[:117]}..."
        previews.append(f"#{event.event_index} {event.role}: {preview}")
        if len(previews) >= 3:
            break
    return previews


def _refs_preview(refs: object) -> str:
    if not isinstance(refs, list):
        return ""
    values = []
    for ref in refs[:3]:
        if not isinstance(ref, dict):
            continue
        values.append(str(ref.get("ref_id") or ""))
    return ", ".join(value for value in values if value)


def _quality_search(signal: dict[str, Any] | None) -> str:
    if not signal:
        return ""
    parts = [
        str(signal.get("session_id") or ""),
        str(signal.get("title") or ""),
        str(signal.get("project_label") or ""),
        str(signal.get("provider") or ""),
        str(signal.get("label") or ""),
        str(signal.get("label_zh") or ""),
        str(signal.get("recommendation") or ""),
        str(signal.get("next_action") or ""),
        str(signal.get("conclusion") or ""),
        str(signal.get("completion_verdict") or ""),
        str(signal.get("dominant_sentiment") or ""),
        " ".join(str(item) for item in signal.get("reasons", []) if item),
        " ".join(str(item) for item in signal.get("risks", []) if item),
        " ".join(str(item) for item in signal.get("positives", []) if item),
        " ".join(str(item) for item in signal.get("diagnostics", []) if item),
    ]
    if signal.get("is_skill_candidate"):
        parts.append("skill_candidate 成skill 成 skill 总结成skill 总结成 skill")
    if int(signal.get("negative_turn_count") or 0):
        parts.append("sentiment:negative 不满意 负面 problem_skill_candidate")
    return " ".join(parts).lower()


def _render_tags(tags: list[dict[str, str]]) -> str:
    if not tags:
        return '<span class="role">no tags</span>'
    return "".join(f'<span class="role">{_esc(tag.get("type", ""))}={_esc(tag.get("value", ""))}</span>' for tag in tags)


def _render_scores(scores: dict[str, float]) -> str:
    if not scores:
        return ""
    return '<div class="kv">' + "".join(
        f'<span class="role">{_esc(key)}={_esc(_format_number(value))}</span>' for key, value in scores.items()
    ) + "</div>"


def _dataset_for(result: FactorResult, data_ref: str) -> dict[str, Any] | None:
    for dataset in result.datasets:
        if str(dataset.get("id") or "") == data_ref:
            return dataset
    return None


def _project_label(status: SessionAnalysisStatus) -> str:
    return status.project_label or status.session_group_label or status.project_key or "Unassigned Project"


def _anchor(provider: str, project_key: str, project_label: str) -> str:
    raw = f"{provider}-{project_label}-{project_key}".lower()
    return "".join(ch if ch.isalnum() else "-" for ch in raw).strip("-") or "project"


def _search_blob(*parts: object) -> str:
    flattened: list[str] = []
    for part in parts:
        if isinstance(part, list):
            flattened.extend(_status_search(status) for status in part)
        else:
            flattened.append(str(part))
    return " ".join(flattened).lower()


def _status_search(status: SessionAnalysisStatus) -> str:
    return " ".join(
        [
            status.session_id,
            status.session_title,
            status.session_cwd,
            status.source_ref,
            status.project_key,
            status.project_label,
            status.provider,
        ]
    )


def _event_search(event: SessionEventRecord) -> str:
    return " ".join(
        [
            event.session_id,
            event.event_id,
            event.role,
            event.content,
            event.tool_name,
            event.tool_result_preview,
            event.source_ref,
            *[f"{tag.factor_id} {tag.tag_type} {tag.tag_value}" for tag in event.tags],
            *[_sentiment_aliases(str(tag.tag_value)) for tag in event.tags if tag.tag_type == "user_sentiment"],
        ]
    ).lower()


def _factor_search(result: FactorResult) -> str:
    return " ".join(
        [
            result.factor_id,
            result.status,
            " ".join(f"{tag.get('type', '')} {tag.get('value', '')}" for tag in result.tags),
            json.dumps(result.scores, ensure_ascii=False),
            json.dumps(result.statistics, ensure_ascii=False),
            json.dumps(result.verdict_signals, ensure_ascii=False),
            json.dumps(result.datasets, ensure_ascii=False),
            _factor_sentiment_aliases(result),
        ]
    ).lower()


def _records_search(records: list[dict[str, Any]]) -> str:
    return " ".join(_record_search(record) for record in records).lower()


def _record_search(record: dict[str, Any]) -> str:
    values = [str(value) for value in record.values()]
    sentiment = str(record.get("sentiment_kind") or record.get("user_sentiment") or "")
    if sentiment:
        values.append(_sentiment_aliases(sentiment))
    return " ".join(values)


def _factor_sentiment_aliases(result: FactorResult) -> str:
    aliases: list[str] = []
    for tag in result.tags:
        if str(tag.get("type") or "") == "user_sentiment":
            aliases.append(_sentiment_aliases(str(tag.get("value") or "")))
    for dataset in result.datasets:
        records = dataset.get("records") if isinstance(dataset.get("records"), list) else []
        for record in records:
            if not isinstance(record, dict):
                continue
            sentiment = str(record.get("sentiment_kind") or record.get("user_sentiment") or "")
            if sentiment:
                aliases.append(_sentiment_aliases(sentiment))
    if any(alias and "sentiment:negative" in alias for alias in aliases):
        aliases.append("sentiment:negative 不满意 负面")
    return " ".join(aliases)


def _sentiment_aliases(value: str) -> str:
    return SENTIMENT_SEARCH_ALIASES.get(value, value)


def _float_value(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / float(len(values))


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


def _format_bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / (1024 * 1024):.1f} MB"


def _display_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _esc(value: object) -> str:
    return escape(str(value), quote=False)


def _attr(value: object) -> str:
    return escape(str(value), quote=True)
