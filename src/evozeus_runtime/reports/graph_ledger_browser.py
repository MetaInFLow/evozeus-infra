from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GraphLedgerBrowserSnapshot:
    graph_path: Path
    legacy_path: Path | None
    graph_size_bytes: int
    legacy_size_bytes: int
    node_counts: list[dict[str, Any]]
    edge_counts: list[dict[str, Any]]
    project_rows: list[dict[str, Any]]
    tag_rows: list[dict[str, Any]]
    factor_rows: list[dict[str, Any]]
    run_status_rows: list[dict[str, Any]]
    evidence_rows: list[dict[str, Any]]
    graph_links: list[dict[str, Any]]


def render_graph_ledger_browser_html(snapshot: GraphLedgerBrowserSnapshot) -> str:
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    node_total = sum(_int(row.get("count")) for row in snapshot.node_counts)
    edge_total = sum(_int(row.get("count")) for row in snapshot.edge_counts)
    size_delta = snapshot.legacy_size_bytes - snapshot.graph_size_bytes
    reduction_ratio = (size_delta / snapshot.legacy_size_bytes) if snapshot.legacy_size_bytes else 0.0
    graph_json = json.dumps(_flow_payload(snapshot.graph_links), ensure_ascii=False)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EvoZeus Graph Ledger Browser</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@xyflow/react@12.11.0/dist/style.css">
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --panel-soft: #f1f5f9;
      --ink: #17202a;
      --muted: #667085;
      --line: #d9e1ea;
      --accent: #0f766e;
      --accent-soft: #d7f5ef;
      --warn: #b45309;
      --bad: #b42318;
      --blue: #2563eb;
      --violet: #7c3aed;
      --shadow: 0 14px 38px rgba(15, 23, 42, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
      letter-spacing: 0;
    }}
    .shell {{
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      min-height: 100vh;
    }}
    .sidebar {{
      border-right: 1px solid var(--line);
      background: #fbfcfd;
      padding: 22px 18px;
      position: sticky;
      top: 0;
      height: 100vh;
      overflow: auto;
    }}
    .brand {{ font-size: 18px; font-weight: 760; margin-bottom: 4px; }}
    .meta {{ color: var(--muted); font-size: 13px; line-height: 1.55; word-break: break-word; }}
    .main {{ padding: 24px; min-width: 0; }}
    .topbar {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 18px;
    }}
    h1 {{ font-size: 28px; line-height: 1.15; margin: 0 0 8px; }}
    h2 {{ font-size: 16px; margin: 0 0 12px; }}
    .path {{ font-size: 12px; color: var(--muted); word-break: break-all; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(140px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .stat, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .stat {{ padding: 14px; min-height: 88px; }}
    .stat strong {{ display: block; font-size: 24px; line-height: 1; margin-bottom: 8px; }}
    .stat span {{ color: var(--muted); font-size: 12px; }}
    .stat.good strong {{ color: var(--accent); }}
    .stat.warn strong {{ color: var(--warn); }}
    .tabs {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0 14px; }}
    .tab {{
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      border-radius: 8px;
      padding: 8px 12px;
      cursor: pointer;
      font: inherit;
    }}
    .tab.active {{ border-color: var(--accent); background: var(--accent-soft); color: #0f4f49; }}
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }}
    .panel {{ padding: 16px; overflow: hidden; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ text-align: left; padding: 9px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    th {{ color: var(--muted); font-weight: 650; background: var(--panel-soft); }}
    td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .bar {{ height: 8px; background: var(--panel-soft); border-radius: 999px; overflow: hidden; min-width: 90px; }}
    .bar > i {{ display: block; height: 100%; background: var(--accent); border-radius: inherit; }}
    .flow-shell {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .flow-toolbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: #fff;
    }}
    .flow-toolbar h2 {{ margin: 0; }}
    .flow-meta {{ display: flex; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: 12px; }}
    .flow-viewport {{ height: min(68vh, 720px); min-height: 540px; background: #f8fafc; }}
    .flow-root {{ width: 100%; height: 100%; }}
    .flow-fallback {{ color: var(--muted); font-size: 13px; padding: 16px; }}
    .flow-panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.94);
      box-shadow: 0 10px 28px rgba(15, 23, 42, 0.10);
      color: var(--ink);
      min-width: 210px;
      max-width: 300px;
      padding: 10px 12px;
    }}
    .flow-panel strong {{ display: block; font-size: 13px; margin-bottom: 6px; }}
    .flow-panel-row {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      border-top: 1px solid #e2e8f0;
      padding-top: 6px;
      margin-top: 6px;
      color: var(--muted);
      font-size: 12px;
    }}
    .flow-panel code {{
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--ink);
    }}
    .react-flow__node-default {{
      border-radius: 8px;
      font-size: 12px;
      font-weight: 650;
      letter-spacing: 0;
      box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
    }}
    .ledger-node {{
      width: 196px;
      border: 1px solid var(--node-border);
      border-radius: 8px;
      background: var(--node-bg);
      color: var(--node-text);
      box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
      overflow: hidden;
    }}
    .ledger-node-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 7px 8px 6px;
    }}
    .ledger-label {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 12px;
      font-weight: 720;
      min-width: 0;
    }}
    .ledger-kind {{
      flex: 0 0 auto;
      border-radius: 999px;
      padding: 3px 6px;
      background: rgba(255, 255, 255, 0.72);
      color: var(--node-text);
      font-size: 10px;
      font-weight: 780;
      text-transform: uppercase;
    }}
    .ledger-tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      padding: 0 8px 8px;
    }}
    .ledger-tag {{
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      border: 1px solid rgba(15, 118, 110, 0.18);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.68);
      color: #0f4f49;
      padding: 2px 6px;
      font-size: 10px;
      font-weight: 680;
    }}
    .react-flow__edge-textbg {{ fill: #ffffff; }}
    .react-flow__edge-text {{ font-size: 11px; fill: var(--muted); }}
    .react-flow__controls {{ box-shadow: 0 8px 22px rgba(15, 23, 42, 0.10); }}
    .react-flow__minimap {{ border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
    .relation-browser {{ padding: 0; }}
    .relation-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 16px;
      border-bottom: 1px solid var(--line);
    }}
    .relation-head h2 {{ margin: 0; }}
    .relation-summary {{ display: flex; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: 12px; }}
    .summary-pill {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 8px;
      background: #fff;
      font-variant-numeric: tabular-nums;
    }}
    .relation-groups {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }}
    .relation-group {{ padding: 14px 14px 16px; border-left: 1px solid var(--line); }}
    .relation-group:first-child {{ border-left: 0; }}
    .relation-group h3 {{ margin: 0 0 10px; font-size: 13px; color: var(--muted); font-weight: 720; }}
    .relation-list {{
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: #fff;
      max-height: min(64vh, 680px);
      min-height: 420px;
      overflow-y: auto;
    }}
    .path-row {{
      display: grid;
      grid-template-columns: 84px minmax(0, 1fr);
      gap: 8px;
      align-items: start;
      min-height: 64px;
      padding: 9px 10px;
      border-top: 1px solid var(--line);
    }}
    .path-row:first-child {{ border-top: 0; }}
    .path-kind {{
      width: fit-content;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 11px;
      font-weight: 760;
      line-height: 1;
      text-transform: uppercase;
      background: var(--panel-soft);
      color: var(--muted);
    }}
    .path-kind.factor {{ color: #5b21b6; background: #ede9fe; }}
    .path-kind.tag {{ color: #0f4f49; background: var(--accent-soft); }}
    .path-kind.evidence {{ color: #8a3b08; background: #ffedd5; }}
    .path-chain {{ min-width: 0; }}
    .path-chain-line {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 24px minmax(0, 1fr);
      gap: 6px;
      align-items: center;
    }}
    .path-node {{ min-width: 0; }}
    .path-node small {{ display: block; margin-bottom: 3px; color: var(--muted); font-size: 11px; }}
    .path-node code {{
      display: block;
      width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      background: #f8fafc;
      padding: 5px 7px;
      color: var(--ink);
    }}
    .path-arrow {{ color: var(--muted); text-align: center; font-weight: 760; white-space: nowrap; }}
    .empty {{ color: var(--muted); font-size: 13px; padding: 12px; }}
    .search {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px 10px;
      font: inherit;
      margin: 14px 0;
      background: #fff;
    }}
    .hidden {{ display: none !important; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
    @media (max-width: 980px) {{
      .shell {{ grid-template-columns: 1fr; }}
      .sidebar {{ position: static; height: auto; }}
      .stats, .grid {{ grid-template-columns: 1fr; }}
      .topbar {{ display: block; }}
      .flow-toolbar {{ display: block; }}
      .flow-meta {{ margin-top: 10px; }}
      .relation-head {{ display: block; }}
      .relation-summary {{ margin-top: 10px; }}
      .relation-groups {{ grid-template-columns: 1fr; }}
      .relation-group {{ border-left: 0; border-top: 1px solid var(--line); }}
      .relation-group:first-child {{ border-top: 0; }}
      .relation-list {{ max-height: none; min-height: 0; }}
    }}
    @media (max-width: 720px) {{
      .path-row {{ grid-template-columns: 1fr; gap: 6px; }}
      .path-chain-line {{ grid-template-columns: 1fr; }}
      .path-arrow {{ text-align: left; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">Graph Ledger</div>
      <div class="meta">Generated: {_esc(generated_at)}</div>
      <input class="search" id="search" type="search" placeholder="过滤 project / tag / factor / session">
      <div class="meta">
        <p><strong>Graph</strong><br><code>{_esc(str(snapshot.graph_path))}</code></p>
        <p><strong>Legacy</strong><br><code>{_esc(str(snapshot.legacy_path or ""))}</code></p>
      </div>
    </aside>
    <main class="main">
      <div class="topbar">
        <div>
          <h1>EvoZeus Graph Ledger Browser</h1>
          <div class="path">GraphQLite sparse evidence graph · local-only</div>
        </div>
      </div>
      <section class="stats" aria-label="summary">
        <div class="stat"><strong>{_fmt(node_total)}</strong><span>Nodes</span></div>
        <div class="stat"><strong>{_fmt(edge_total)}</strong><span>Edges</span></div>
        <div class="stat"><strong>{_size(snapshot.graph_size_bytes)}</strong><span>Graph file</span></div>
        <div class="stat {'good' if reduction_ratio >= 0 else 'warn'}"><strong>{_pct(reduction_ratio)}</strong><span>Vs legacy SQLite</span></div>
      </section>
      <nav class="tabs" aria-label="views">
        <button class="tab active" type="button" data-tab-target="graph">Graph</button>
        <button class="tab" type="button" data-tab-target="relations">Relations</button>
        <button class="tab" type="button" data-tab-target="overview">Overview</button>
        <button class="tab" type="button" data-tab-target="projects">Projects</button>
        <button class="tab" type="button" data-tab-target="tags">Tags</button>
        <button class="tab" type="button" data-tab-target="factors">Factors</button>
        <button class="tab" type="button" data-tab-target="evidence">Evidence</button>
      </nav>
      <section id="graph" class="tab-panel active">{_render_flow_shell(snapshot.graph_links)}</section>
      <section id="relations" class="tab-panel">{_render_relationship_paths(snapshot.graph_links)}</section>
      <section id="overview" class="tab-panel">
        <div class="grid">
          {_render_count_table("Node labels", snapshot.node_counts, "label")}
          {_render_count_table("Edge types", snapshot.edge_counts, "type")}
          {_render_run_status(snapshot.run_status_rows)}
          {_render_size_panel(snapshot)}
        </div>
      </section>
      <section id="projects" class="tab-panel">{_render_project_table(snapshot.project_rows)}</section>
      <section id="tags" class="tab-panel">{_render_tag_table(snapshot.tag_rows)}</section>
      <section id="factors" class="tab-panel">{_render_factor_table(snapshot.factor_rows)}</section>
      <section id="evidence" class="tab-panel">{_render_evidence_table(snapshot.evidence_rows)}</section>
    </main>
  </div>
  <script type="importmap">
    {{
      "imports": {{
        "react": "https://esm.sh/react@18.3.1",
        "react/jsx-runtime": "https://esm.sh/react@18.3.1/jsx-runtime",
        "react-dom": "https://esm.sh/react-dom@18.3.1",
        "react-dom/client": "https://esm.sh/react-dom@18.3.1/client",
        "@xyflow/react": "https://esm.sh/@xyflow/react@12.11.0?external=react,react-dom"
      }}
    }}
  </script>
  <script>
    const search = document.getElementById("search");
    const searchable = Array.from(document.querySelectorAll("[data-search]"));
    function terms() {{
      return search.value.toLowerCase().split(/\\s+/).filter(Boolean);
    }}
    function applySearch() {{
      const activeTerms = terms();
      for (const node of searchable) {{
        const haystack = node.dataset.search || "";
        node.classList.toggle("hidden", activeTerms.length > 0 && !activeTerms.every((term) => haystack.includes(term)));
      }}
    }}
    search.addEventListener("input", applySearch);
    document.querySelectorAll("[data-tab-target]").forEach((button) => {{
      button.addEventListener("click", () => {{
        const target = button.dataset.tabTarget;
        document.querySelectorAll("[data-tab-target]").forEach((item) => item.classList.toggle("active", item === button));
        document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === target));
      }});
    }});
  </script>
  <script type="module">
    import React, {{ useEffect, useMemo, useState }} from "react";
    import {{ createRoot }} from "react-dom/client";
    import {{ ReactFlow, MiniMap, Controls, Background, Panel, Handle, Position }} from "@xyflow/react";

    const graphModel = {graph_json};
    const e = React.createElement;

    function graphTerms(query) {{
      return query.toLowerCase().split(/\\s+/).filter(Boolean);
    }}

    function filterModel(model, query) {{
      const terms = graphTerms(query);
      if (!terms.length) return model;
      const keepNodes = new Set();
      const keepEdges = new Set();
      for (const node of model.nodes) {{
        if (terms.every((term) => node.data.search.includes(term))) keepNodes.add(node.id);
      }}
      for (const edge of model.edges) {{
        const edgeMatches = terms.every((term) => edge.data.search.includes(term));
        const nodeTouches = keepNodes.has(edge.source) || keepNodes.has(edge.target);
        if (edgeMatches || nodeTouches) {{
          keepEdges.add(edge.id);
          keepNodes.add(edge.source);
          keepNodes.add(edge.target);
        }}
      }}
      return {{
        ...model,
        nodes: model.nodes.filter((node) => keepNodes.has(node.id)),
        edges: model.edges.filter((edge) => keepEdges.has(edge.id)),
      }};
    }}

    function useSidebarSearch() {{
      const [query, setQuery] = useState(() => document.getElementById("search")?.value || "");
      useEffect(() => {{
        const input = document.getElementById("search");
        if (!input) return undefined;
        const onInput = () => setQuery(input.value || "");
        input.addEventListener("input", onInput);
        return () => input.removeEventListener("input", onInput);
      }}, []);
      return query;
    }}

    function LedgerNode({{ data }}) {{
      return e(
        "div",
        {{
          className: "ledger-node",
          style: {{
            "--node-bg": data.background,
            "--node-border": data.border,
            "--node-text": data.text,
          }},
          title: data.fullLabel,
        }},
        e(Handle, {{ type: "target", position: Position.Top }}),
        e("div", {{ className: "ledger-node-head" }},
          e("span", {{ className: "ledger-label" }}, data.label),
          e("span", {{ className: "ledger-kind" }}, data.kind),
        ),
        data.tags && data.tags.length
          ? e("div", {{ className: "ledger-tags" }},
              ...data.tags.slice(0, 3).map((tag) => e("span", {{ className: "ledger-tag", key: tag, title: tag }}, tag)),
              data.tagOverflow > 0 ? e("span", {{ className: "ledger-tag", key: "__more" }}, "+" + data.tagOverflow) : null,
            )
          : null,
        e(Handle, {{ type: "source", position: Position.Bottom }}),
      );
    }}

    function FlowGraph() {{
      const query = useSidebarSearch();
      const [selectedId, setSelectedId] = useState("");
      const nodeTypes = useMemo(() => ({{ ledger: LedgerNode }}), []);
      const filtered = useMemo(() => filterModel(graphModel, query), [query]);
      const selectedNode = useMemo(
        () => graphModel.nodes.find((node) => node.id === selectedId) || null,
        [selectedId],
      );
      const selectedEdges = useMemo(() => {{
        if (!selectedId) return new Set();
        return new Set(graphModel.edges.filter((edge) => edge.source === selectedId || edge.target === selectedId).map((edge) => edge.id));
      }}, [selectedId]);
      const neighborhood = useMemo(() => {{
        if (!selectedId) return new Set();
        const ids = new Set([selectedId]);
        for (const edge of graphModel.edges) {{
          if (edge.source === selectedId) ids.add(edge.target);
          if (edge.target === selectedId) ids.add(edge.source);
        }}
        return ids;
      }}, [selectedId]);
      const nodes = useMemo(
        () =>
          filtered.nodes.map((node) => ({{
            ...node,
            style: {{
              ...node.style,
              opacity: selectedId && !neighborhood.has(node.id) ? 0.25 : 1,
              boxShadow: selectedId === node.id ? "0 0 0 3px rgba(15, 118, 110, 0.30), 0 10px 24px rgba(15, 23, 42, 0.14)" : node.style.boxShadow,
            }},
          }})),
        [filtered.nodes, neighborhood, selectedId],
      );
      const edges = useMemo(
        () =>
          filtered.edges.map((edge) => ({{
            ...edge,
            animated: selectedEdges.has(edge.id),
            style: {{
              ...edge.style,
              opacity: selectedId && !selectedEdges.has(edge.id) ? 0.18 : 1,
              strokeWidth: selectedEdges.has(edge.id) ? 2.5 : edge.style.strokeWidth,
            }},
          }})),
        [filtered.edges, selectedEdges, selectedId],
      );
      return e(
        ReactFlow,
        {{
          nodes,
          edges,
          nodeTypes,
          defaultViewport: {{ x: 70, y: 76, zoom: 0.74 }},
          minZoom: 0.04,
          maxZoom: 2.2,
          nodesDraggable: true,
          elementsSelectable: true,
          onNodeClick: (_event, node) => setSelectedId(node.id),
          onPaneClick: () => setSelectedId(""),
          proOptions: {{ hideAttribution: true }},
        }},
        e(Background, {{ gap: 22, size: 1.2 }}),
        e(Controls, {{ showInteractive: false }}),
        e(MiniMap, {{
          pannable: true,
          zoomable: true,
          nodeColor: (node) => node.data.color,
          nodeStrokeWidth: 2,
          ariaLabel: "Graph minimap",
        }}),
        e(
          Panel,
          {{ position: "top-left", className: "flow-panel" }},
          e("strong", null, selectedNode ? selectedNode.data.fullLabel : "Graph"),
          e("code", {{ title: selectedNode ? selectedNode.id : "" }}, selectedNode ? selectedNode.id : "ReactFlow / @xyflow/react"),
          e("div", {{ className: "flow-panel-row" }}, e("span", null, "Visible nodes"), e("span", null, nodes.length.toLocaleString())),
          e("div", {{ className: "flow-panel-row" }}, e("span", null, "Visible edges"), e("span", null, edges.length.toLocaleString())),
          selectedNode ? e("div", {{ className: "flow-panel-row" }}, e("span", null, "Kind"), e("span", null, selectedNode.data.kind)) : null,
        ),
      );
    }}

    const root = document.getElementById("reactFlowRoot");
    if (root) createRoot(root).render(e(FlowGraph));
  </script>
</body>
</html>"""


def _render_count_table(title: str, rows: list[dict[str, Any]], label_key: str) -> str:
    max_count = max((_int(row.get("count")) for row in rows), default=1)
    body = "\n".join(
        f"""<tr data-search="{_search(row)}"><td>{_esc(str(row.get(label_key) or ""))}</td><td class="num">{_fmt(_int(row.get("count")))}</td><td><span class="bar"><i style="width:{max(2, _int(row.get("count")) / max_count * 100):.1f}%"></i></span></td></tr>"""
        for row in rows
    )
    return f"""<section class="panel"><h2>{_esc(title)}</h2><table><thead><tr><th>Name</th><th>Count</th><th></th></tr></thead><tbody>{body}</tbody></table></section>"""


def _render_run_status(rows: list[dict[str, Any]]) -> str:
    body = "\n".join(
        f"""<tr data-search="{_search(row)}"><td>{_esc(str(row.get("status") or ""))}</td><td class="num">{_fmt(_int(row.get("count")))}</td></tr>"""
        for row in rows
    )
    return f"""<section class="panel"><h2>Run status</h2><table><thead><tr><th>Status</th><th>Count</th></tr></thead><tbody>{body}</tbody></table></section>"""


def _render_size_panel(snapshot: GraphLedgerBrowserSnapshot) -> str:
    delta = snapshot.legacy_size_bytes - snapshot.graph_size_bytes
    return f"""<section class="panel">
      <h2>Storage</h2>
      <table><tbody>
        <tr><th>Legacy SQLite</th><td class="num">{_size(snapshot.legacy_size_bytes)}</td></tr>
        <tr><th>GraphQLite</th><td class="num">{_size(snapshot.graph_size_bytes)}</td></tr>
        <tr><th>Delta</th><td class="num">{_size(abs(delta))} {'less' if delta >= 0 else 'more'}</td></tr>
      </tbody></table>
    </section>"""


def _render_project_table(rows: list[dict[str, Any]]) -> str:
    body = "\n".join(
        f"""<tr data-search="{_search(row)}"><td>{_esc(str(row.get("project") or ""))}</td><td class="num">{_fmt(_int(row.get("sessions")))}</td><td class="num">{_fmt(_int(row.get("factor_results")))}</td><td class="num">{_fmt(_int(row.get("evidence_events")))}</td></tr>"""
        for row in rows
    )
    return f"""<section class="panel"><h2>Projects</h2><table><thead><tr><th>Project</th><th>Sessions</th><th>Factor results</th><th>Evidence events</th></tr></thead><tbody>{body}</tbody></table></section>"""


def _render_tag_table(rows: list[dict[str, Any]]) -> str:
    body = "\n".join(
        f"""<tr data-search="{_search_with_extra(row, _tag_display_label_from_parts(str(row.get("type") or ""), str(row.get("value") or "")))}"><td>{_esc(_tag_type_label(str(row.get("type") or "")))}</td><td><span title="{_esc(str(row.get("type") or ""))}:{_esc(str(row.get("value") or ""))}">{_esc(_tag_value_label(str(row.get("type") or ""), str(row.get("value") or "")))}</span></td><td class="num">{_fmt(_int(row.get("sessions")))}</td><td class="num">{_fmt(_int(row.get("assertions")))}</td><td class="num">{_fmt(_int(row.get("evidence")))}</td></tr>"""
        for row in rows
    )
    return f"""<section class="panel"><h2>Tags</h2><table><thead><tr><th>Type</th><th>Value</th><th>Sessions</th><th>Assertions</th><th>Evidence</th></tr></thead><tbody>{body}</tbody></table></section>"""


def _render_factor_table(rows: list[dict[str, Any]]) -> str:
    body = "\n".join(
        f"""<tr data-search="{_search(row)}"><td>{_esc(str(row.get("factor_id") or ""))}</td><td class="num">{_fmt(_int(row.get("results")))}</td><td>{_esc(str(row.get("status") or ""))}</td></tr>"""
        for row in rows
    )
    return f"""<section class="panel"><h2>Factors</h2><table><thead><tr><th>Factor</th><th>Results</th><th>Status</th></tr></thead><tbody>{body}</tbody></table></section>"""


def _render_evidence_table(rows: list[dict[str, Any]]) -> str:
    body = "\n".join(
        f"""<tr data-search="{_search(row)}"><td>{_esc(str(row.get("session_id") or ""))}</td><td>{_esc(str(row.get("event_id") or ""))}</td><td>{_esc(str(row.get("role") or ""))}</td><td>{_esc(str(row.get("tool_name") or ""))}</td><td>{_esc(str(row.get("preview") or ""))}</td></tr>"""
        for row in rows
    )
    return f"""<section class="panel"><h2>Evidence events</h2><table><thead><tr><th>Session</th><th>Event</th><th>Role</th><th>Tool</th><th>Preview</th></tr></thead><tbody>{body}</tbody></table></section>"""


def _render_flow_shell(links: list[dict[str, Any]]) -> str:
    payload = _flow_payload(links)
    return f"""<section class="flow-shell">
      <div class="flow-toolbar">
        <h2>Graph</h2>
        <div class="flow-meta">
          <span class="summary-pill">ReactFlow</span>
          <span class="summary-pill">Nodes · {_fmt(len(payload["nodes"]))}</span>
          <span class="summary-pill">Edges · {_fmt(len(payload["edges"]))}</span>
        </div>
      </div>
      <div class="flow-viewport">
        <div id="reactFlowRoot" class="flow-root">
          <div class="flow-fallback">ReactFlow module is loading.</div>
        </div>
      </div>
    </section>"""


def _render_relationship_paths(links: list[dict[str, Any]]) -> str:
    groups = [
        ("factor", "Factor -> Session"),
        ("tag", "Session -> Tag"),
        ("evidence", "Session -> Evidence"),
    ]
    counts = {kind: sum(1 for row in links if row.get("kind") == kind) for kind, _title in groups}
    summary = "".join(
        f"""<span class="summary-pill">{_esc(title)} · {_fmt(counts[kind])}</span>"""
        for kind, title in groups
    )
    body = "\n".join(_render_path_group(kind, title, [row for row in links if row.get("kind") == kind]) for kind, title in groups)
    return f"""<section class="panel relation-browser">
      <div class="relation-head">
        <h2>Relationship paths</h2>
        <div class="relation-summary">{summary}</div>
      </div>
      <div class="relation-groups">{body}</div>
    </section>"""


def _render_path_group(kind: str, title: str, rows: list[dict[str, Any]]) -> str:
    visible_rows = rows[:120]
    if visible_rows:
        body = "\n".join(_render_path_row(row) for row in visible_rows)
    else:
        body = """<div class="empty">No relationships</div>"""
    hidden = len(rows) - len(visible_rows)
    suffix = f" · {_fmt(hidden)} more" if hidden > 0 else ""
    return f"""<section class="relation-group">
        <h3>{_esc(title)}{_esc(suffix)}</h3>
        <div class="relation-list">{body}</div>
      </section>"""


def _render_path_row(row: dict[str, Any]) -> str:
    source_label = str(row.get("source_label") or row.get("source") or "")
    target_label = str(row.get("target_label") or row.get("target") or "")
    target_display_label = _tag_display_label(target_label) if row.get("kind") == "tag" else target_label
    source_kind = str(row.get("source_kind") or "source")
    target_kind = str(row.get("target_kind") or "target")
    kind = str(row.get("kind") or "relation")
    kind_class = kind if kind in {"factor", "tag", "evidence"} else "relation"
    return f"""<div class="path-row" data-search="{_search_with_extra(row, target_display_label)}">
          <span class="path-kind {kind_class}">{_esc(kind)}</span>
          <span class="path-chain">
            <span class="path-chain-line">
              <span class="path-node"><small>{_esc(source_kind)}</small><code title="{_esc(str(row.get("source") or ""))}">{_esc(source_label)}</code></span>
              <span class="path-arrow">-></span>
              <span class="path-node"><small>{_esc(target_kind)}</small><code title="{_esc(str(row.get("target") or ""))}">{_esc(target_display_label)}</code></span>
            </span>
          </span>
        </div>"""


def _flow_payload(links: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [row for row in links[:720] if row.get("source") and row.get("target")]
    tags_by_session: dict[str, list[str]] = {}
    tag_search_by_session: dict[str, list[str]] = {}
    node_rows: dict[str, dict[str, Any]] = {}
    degree: dict[str, int] = {}
    for row in rows:
        source = str(row.get("source") or "")
        target = str(row.get("target") or "")
        if row.get("kind") == "tag":
            raw_tag_label = str(row.get("target_label") or target)
            tag_label = _tag_display_label(raw_tag_label)
            tags_by_session.setdefault(source, [])
            if tag_label not in tags_by_session[source]:
                tags_by_session[source].append(tag_label)
            tag_search_by_session.setdefault(source, [])
            tag_search_by_session[source].extend([raw_tag_label, tag_label])
            node_rows.setdefault(
                source,
                {
                    "id": source,
                    "kind": str(row.get("source_kind") or "session"),
                    "label": str(row.get("source_label") or source),
                },
            )
            continue
        degree[source] = degree.get(source, 0) + 1
        degree[target] = degree.get(target, 0) + 1
        node_rows.setdefault(
            source,
            {
                "id": source,
                "kind": str(row.get("source_kind") or "session"),
                "label": str(row.get("source_label") or source),
            },
        )
        node_rows.setdefault(
            target,
            {
                "id": target,
                "kind": str(row.get("target_kind") or "tag"),
                "label": str(row.get("target_label") or target),
            },
        )

    lane_limits = {"factor": 24, "session": 84, "tag": 0, "event": 60}
    visible_ids: set[str] = set()
    flow_nodes: list[dict[str, Any]] = []
    sorted_nodes: dict[str, list[dict[str, Any]]] = {}
    for kind in ("factor", "session", "tag", "event"):
        candidates = [node for node in node_rows.values() if node["kind"] == kind]
        candidates.sort(key=lambda node: (-degree.get(node["id"], 0), str(node["label"])))
        sorted_nodes[kind] = candidates[: lane_limits[kind]]

    factor_rows = _append_flow_nodes(
        flow_nodes=flow_nodes,
        visible_ids=visible_ids,
        nodes=sorted_nodes["factor"],
        kind="factor",
        tags_by_node={},
        tag_search_by_node={},
        x0=0,
        y0=0,
        columns=6,
    )
    session_y = 150 + factor_rows * 94
    session_rows = _append_flow_nodes(
        flow_nodes=flow_nodes,
        visible_ids=visible_ids,
        nodes=sorted_nodes["session"],
        kind="session",
        tags_by_node=tags_by_session,
        tag_search_by_node=tag_search_by_session,
        x0=0,
        y0=session_y,
        columns=7,
    )
    lower_y = session_y + session_rows * 98 + 150
    _append_flow_nodes(
        flow_nodes=flow_nodes,
        visible_ids=visible_ids,
        nodes=sorted_nodes["tag"],
        kind="tag",
        tags_by_node={},
        tag_search_by_node={},
        x0=0,
        y0=lower_y,
        columns=4,
    )
    _append_flow_nodes(
        flow_nodes=flow_nodes,
        visible_ids=visible_ids,
        nodes=sorted_nodes["event"],
        kind="event",
        tags_by_node={},
        tag_search_by_node={},
        x0=900,
        y0=lower_y,
        columns=4,
    )

    flow_edges: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        source = str(row.get("source") or "")
        target = str(row.get("target") or "")
        if row.get("kind") == "tag":
            continue
        if source not in visible_ids or target not in visible_ids:
            continue
        kind = str(row.get("kind") or "relation")
        color = _flow_color(kind)
        edge_id = f"edge:{index}:{source}->{target}"
        flow_edges.append(
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "type": "smoothstep",
                "data": {"kind": kind, "search": _flow_search(row)},
                "style": {"stroke": color["accent"], "strokeWidth": 1.6},
            }
        )
    return {"nodes": flow_nodes, "edges": flow_edges}


def _append_flow_nodes(
    *,
    flow_nodes: list[dict[str, Any]],
    visible_ids: set[str],
    nodes: list[dict[str, Any]],
    kind: str,
    tags_by_node: dict[str, list[str]],
    tag_search_by_node: dict[str, list[str]],
    x0: int,
    y0: int,
    columns: int,
) -> int:
    x_gap = 215
    y_gap = 96
    for index, node in enumerate(nodes):
        visible_ids.add(str(node["id"]))
        color = _flow_color(kind)
        tags = tags_by_node.get(str(node["id"]), [])[:8]
        tag_search = " ".join(tag_search_by_node.get(str(node["id"]), []))
        flow_nodes.append(
            {
                "id": node["id"],
                "type": "ledger",
                "position": {"x": x0 + (index % columns) * x_gap, "y": y0 + (index // columns) * y_gap},
                "sourcePosition": "bottom" if kind in {"factor", "session"} else "right",
                "targetPosition": "top" if kind in {"session", "tag", "event"} else "left",
                "data": {
                    "label": _clip(str(node["label"]), 22),
                    "fullLabel": str(node["label"]),
                    "kind": kind,
                    "tags": tags[:3],
                    "tagOverflow": max(0, len(tags) - 3),
                    "color": color["accent"],
                    "background": color["background"],
                    "border": color["border"],
                    "text": color["text"],
                    "search": " ".join(filter(None, [_flow_search(node), " ".join(tags).lower(), tag_search.lower()])),
                },
                "style": {
                    "width": 196,
                },
            }
        )
    return max(1, (len(nodes) + columns - 1) // columns)


def _flow_color(kind: str) -> dict[str, str]:
    colors = {
        "factor": {"accent": "#7c3aed", "border": "#a78bfa", "background": "#f5f3ff", "text": "#312e81"},
        "session": {"accent": "#2563eb", "border": "#93c5fd", "background": "#eff6ff", "text": "#1e3a8a"},
        "tag": {"accent": "#0f766e", "border": "#5eead4", "background": "#ecfdf5", "text": "#134e4a"},
        "event": {"accent": "#b45309", "border": "#fdba74", "background": "#fff7ed", "text": "#7c2d12"},
        "evidence": {"accent": "#b45309", "border": "#fdba74", "background": "#fff7ed", "text": "#7c2d12"},
    }
    return colors.get(kind, {"accent": "#64748b", "border": "#cbd5e1", "background": "#f8fafc", "text": "#334155"})


def _flow_search(row: dict[str, Any]) -> str:
    return " ".join(str(value).lower() for value in row.values() if value is not None)


def _tag_display_label(raw_label: str) -> str:
    tag_type, sep, tag_value = raw_label.partition(":")
    if not sep:
        return _tag_value_label("", raw_label)
    return _tag_display_label_from_parts(tag_type, tag_value)


def _tag_display_label_from_parts(tag_type: str, tag_value: str) -> str:
    type_label = _tag_type_label(tag_type)
    value_label = _tag_value_label(tag_type, tag_value)
    return f"{type_label}：{value_label}" if type_label and value_label else value_label or type_label


def _tag_type_label(tag_type: str) -> str:
    labels = {
        "key_sentence": "关键句",
        "loop": "循环",
        "session_resource_usage": "会话资源使用",
        "signal": "信号",
        "task_completion": "任务完成",
        "tool_failure": "工具失败",
        "usage_sentence": "使用表达",
        "user_sentiment": "用户情绪",
    }
    return labels.get(tag_type, _humanize_token(tag_type))


def _tag_value_label(tag_type: str, tag_value: str) -> str:
    labels = {
        ("key_sentence", "trend"): "趋势",
        ("loop", "repeated-request"): "重复请求",
        ("session_resource_usage", "tools-skills-mcp"): "工具 / Skills / MCP",
        ("signal", "tool_failure"): "工具失败",
        ("signal", "user repeated a previously unresolved request"): "用户重复了未解决请求",
        ("task_completion", "blocked"): "阻塞",
        ("task_completion", "completed"): "已完成",
        ("task_completion", "incomplete"): "未完成",
        ("task_completion", "not_completed"): "未完成",
        ("tool_failure", "*"): "任意工具失败",
        ("usage_sentence", "high_frequency"): "高频",
        ("user_sentiment", "correction_request"): "要求纠正",
        ("user_sentiment", "dissatisfaction"): "不满意",
        ("user_sentiment", "negative"): "负面",
        ("user_sentiment", "neutral_request"): "中性请求",
        ("user_sentiment", "positive"): "正向",
        ("user_sentiment", "positive_feedback"): "正向反馈",
        ("user_sentiment", "problem_report"): "问题反馈",
    }
    return labels.get((tag_type, tag_value), _humanize_token(tag_value))


def _humanize_token(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").strip()


def _clip(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)] + "..."


def _search(row: dict[str, Any]) -> str:
    return _esc(" ".join(str(value).lower() for value in row.values() if value is not None))


def _search_with_extra(row: dict[str, Any], *extra: str) -> str:
    values = [str(value).lower() for value in row.values() if value is not None]
    values.extend(item.lower() for item in extra if item)
    return _esc(" ".join(values))


def _fmt(value: int) -> str:
    return f"{value:,}"


def _size(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _esc(value: str) -> str:
    return escape(value, quote=True)
