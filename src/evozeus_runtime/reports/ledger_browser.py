from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from html import escape
from pathlib import Path

from evozeus_runtime.ledger.repository import SessionAnalysisStatus, SessionEventRecord


def render_ledger_browser_html(
    *,
    statuses: list[SessionAnalysisStatus],
    events: list[SessionEventRecord],
    ledger_path: Path | str | None = None,
) -> str:
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    events_by_session: dict[str, list[SessionEventRecord]] = defaultdict(list)
    for event in events:
        events_by_session[event.session_id].append(event)

    providers: dict[str, dict[tuple[str, str], list[SessionAnalysisStatus]]] = defaultdict(lambda: defaultdict(list))
    for status in sorted(statuses, key=lambda item: (item.provider, _project_label(item), item.session_id)):
        project_key = status.project_key or status.session_group_key or "unassigned"
        project_label = _project_label(status)
        providers[status.provider][(project_key, project_label)].append(status)

    project_count = len({(status.provider, status.project_key or status.session_group_key) for status in statuses})
    sidebar = _render_sidebar(providers)
    body = _render_providers(providers, events_by_session)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EvoZeus SQLite Visualizer</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8f5;
      --panel: #ffffff;
      --ink: #17201c;
      --muted: #65726b;
      --line: #dce2dc;
      --accent: #0f766e;
      --accent-soft: #e3f3ef;
      --warn: #9a3412;
      --warn-soft: #fff1e6;
      --code: #29312d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.5;
    }}
    .shell {{
      display: grid;
      grid-template-columns: minmax(240px, 300px) minmax(0, 1fr);
      min-height: 100vh;
    }}
    aside {{
      position: sticky;
      top: 0;
      height: 100vh;
      overflow: auto;
      padding: 20px;
      border-right: 1px solid var(--line);
      background: #fbfcf9;
    }}
    main {{
      padding: 24px;
      overflow: hidden;
    }}
    h1, h2, h3 {{ margin: 0; line-height: 1.2; }}
    h1 {{ font-size: 24px; }}
    h2 {{ font-size: 18px; }}
    h3 {{ font-size: 15px; }}
    code {{
      color: var(--code);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      word-break: break-all;
    }}
    .topbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 20px;
    }}
    .meta {{
      color: var(--muted);
      margin-top: 6px;
      max-width: 960px;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(110px, 1fr));
      gap: 10px;
      margin: 18px 0 22px;
    }}
    .stat, .panel, .session {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
    }}
    .stat {{ padding: 12px; }}
    .stat strong {{ display: block; font-size: 22px; }}
    .stat span {{ color: var(--muted); font-size: 12px; }}
    .search {{
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px 10px;
      background: #fff;
      color: var(--ink);
    }}
    .nav-group {{ margin-top: 16px; }}
    .nav-provider {{ font-weight: 700; margin: 12px 0 6px; }}
    .nav-project {{
      display: block;
      color: var(--muted);
      text-decoration: none;
      padding: 5px 0;
      word-break: break-word;
    }}
    .provider {{
      margin-bottom: 22px;
    }}
    .provider-header, .project-header {{
      display: flex;
      gap: 10px;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 10px;
    }}
    .project {{
      margin-top: 14px;
      padding: 16px;
    }}
    .project-key {{
      color: var(--muted);
      margin-top: 4px;
      word-break: break-all;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 2px 8px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 12px;
      font-weight: 650;
      white-space: nowrap;
    }}
    .session {{
      margin-top: 10px;
      overflow: hidden;
    }}
    .session summary {{
      cursor: pointer;
      list-style: none;
      padding: 12px 14px;
    }}
    .session summary::-webkit-details-marker {{ display: none; }}
    .session summary:hover {{ background: #f8faf7; }}
    .session-title {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      font-weight: 700;
    }}
    .session-subtitle {{
      margin-top: 6px;
      color: var(--muted);
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .chat {{
      border-top: 1px solid var(--line);
      margin: 0;
      padding: 0;
      list-style: none;
    }}
    .event {{
      display: grid;
      grid-template-columns: 74px minmax(0, 1fr);
      gap: 12px;
      padding: 12px 14px;
      border-top: 1px solid #eef1ed;
    }}
    .event:first-child {{ border-top: 0; }}
    .event-index {{
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }}
    .event-body {{ min-width: 0; }}
    .event-line {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    .role {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 1px 6px;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }}
    .content {{
      margin-top: 6px;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .empty {{
      color: var(--warn);
      background: var(--warn-soft);
      border-radius: 6px;
      padding: 6px 8px;
      display: inline-block;
    }}
    .source {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 12px;
      word-break: break-all;
    }}
    .hidden {{ display: none !important; }}
    @media (max-width: 860px) {{
      .shell {{ grid-template-columns: 1fr; }}
      aside {{
        position: static;
        height: auto;
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }}
      main {{ padding: 16px; }}
      .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .event {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <h2>SQLite 导航</h2>
      <p class="meta">按 provider 和 project 浏览 session，再展开查看 chat/message index。</p>
      <input class="search" id="search" type="search" placeholder="过滤 provider / project / session / message">
      {sidebar}
    </aside>
    <main>
      <section class="topbar">
        <div>
          <h1>EvoZeus SQLite Visualizer</h1>
          <p class="meta">Ledger: <code>{_esc(str(ledger_path or ""))}</code><br>Generated: {_esc(generated_at)}</p>
        </div>
      </section>
      <section class="stats" aria-label="summary">
        <div class="stat"><strong>{len(providers)}</strong><span>Providers</span></div>
        <div class="stat"><strong>{project_count}</strong><span>Projects</span></div>
        <div class="stat"><strong>{len(statuses)}</strong><span>Sessions</span></div>
        <div class="stat"><strong>{len(events)}</strong><span>Chat messages</span></div>
      </section>
      {body}
    </main>
  </div>
  <script>
    const input = document.getElementById("search");
    const filterable = Array.from(document.querySelectorAll("[data-search]"));
    input.addEventListener("input", () => {{
      const term = input.value.trim().toLowerCase();
      for (const node of filterable) {{
        const haystack = node.getAttribute("data-search") || "";
        node.classList.toggle("hidden", Boolean(term) && !haystack.includes(term));
      }}
    }});
  </script>
</body>
</html>
"""


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
                provider_chunks.append(_render_session(status, events_by_session.get(status.session_id, [])))
            provider_chunks.append("</section>")
        provider_chunks.append("</section>")
    return "\n".join(provider_chunks)


def _render_session(status: SessionAnalysisStatus, events: list[SessionEventRecord]) -> str:
    title = status.session_title or status.session_id
    search = _search_blob(
        status.provider,
        status.project_key,
        status.project_label,
        [status],
        *(_event_search(event) for event in events),
    )
    chunks = [
        f'<details class="session" data-search="{_attr(search)}">',
        "<summary>",
        '<div class="session-title">',
        f'<span>{_esc(title)}</span>',
        f'<span class="badge">{len(events) or status.event_count} messages</span>',
        f'<span class="badge">{status.analyzed_factor_count} factors</span>',
        "</div>",
        '<div class="session-subtitle">',
        f'<code>{_esc(status.session_id)}</code>',
        f'<span>updated {_esc(status.session_updated_at or status.discovered_at)}</span>',
        f'<span>source <code>{_esc(status.source_ref)}</code></span>',
        "</div>",
        "</summary>",
    ]
    if events:
        chunks.append('<ol class="chat">')
        chunks.extend(_render_event(event) for event in events)
        chunks.append("</ol>")
    else:
        chunks.append('<div class="event"><div></div><div class="empty">没有 message index。先运行 scanner。</div></div>')
    chunks.append("</details>")
    return "\n".join(chunks)


def _render_event(event: SessionEventRecord) -> str:
    content = event.content or event.tool_result_preview
    if not content:
        content_html = '<span class="empty">scan-only id record: content not materialized</span>'
    else:
        content_html = _esc(content)
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
        ]
    ).lower()


def _esc(value: object) -> str:
    return escape(str(value), quote=False)


def _attr(value: object) -> str:
    return escape(str(value), quote=True)
