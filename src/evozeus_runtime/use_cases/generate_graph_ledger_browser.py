from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evozeus_runtime.ledger.graph_repository import GraphLedgerRepository
from evozeus_runtime.ledger.paths import RuntimePaths
from evozeus_runtime.reports.graph_ledger_browser import GraphLedgerBrowserSnapshot, render_graph_ledger_browser_html


@dataclass(frozen=True)
class GenerateGraphLedgerBrowserResult:
    html_path: Path
    graph_path: Path
    legacy_path: Path
    graph_size_bytes: int
    legacy_size_bytes: int
    node_count: int
    edge_count: int


def generate_graph_ledger_browser(
    *,
    workspace_root: Path,
    graph_path: Path | None = None,
    legacy_path: Path | None = None,
    output_path: Path | None = None,
) -> GenerateGraphLedgerBrowserResult:
    paths = RuntimePaths.for_workspace(workspace_root).ensure()
    resolved_graph_path = graph_path or (paths.runtime_index_dir / "results.graph.sqlite3")
    resolved_legacy_path = legacy_path or paths.result_index_db
    graph = GraphLedgerRepository(resolved_graph_path)
    snapshot = _build_snapshot(
        graph=graph,
        graph_path=resolved_graph_path,
        legacy_path=resolved_legacy_path if resolved_legacy_path.exists() else None,
    )
    html_path = output_path or (paths.runtime_root / "reports" / "evozeus-graph.html")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_graph_ledger_browser_html(snapshot), encoding="utf-8")
    return GenerateGraphLedgerBrowserResult(
        html_path=html_path,
        graph_path=resolved_graph_path,
        legacy_path=resolved_legacy_path,
        graph_size_bytes=snapshot.graph_size_bytes,
        legacy_size_bytes=snapshot.legacy_size_bytes,
        node_count=sum(_int(row.get("count")) for row in snapshot.node_counts),
        edge_count=sum(_int(row.get("count")) for row in snapshot.edge_counts),
    )


def _build_snapshot(
    *,
    graph: GraphLedgerRepository,
    graph_path: Path,
    legacy_path: Path | None,
) -> GraphLedgerBrowserSnapshot:
    node_counts = _node_counts(graph)
    edge_counts = _edge_counts(graph)
    return GraphLedgerBrowserSnapshot(
        graph_path=graph_path,
        legacy_path=legacy_path,
        graph_size_bytes=graph_path.stat().st_size if graph_path.exists() else 0,
        legacy_size_bytes=legacy_path.stat().st_size if legacy_path and legacy_path.exists() else 0,
        node_counts=node_counts,
        edge_counts=edge_counts,
        project_rows=_project_rows(graph),
        tag_rows=_query(
            graph,
            """
            MATCH (s:Session)-[r:HAS_TAG_ROLLUP]->(t:Tag)
            RETURN t.type AS type, t.value AS value, count(DISTINCT s) AS sessions,
                   sum(r.count) AS assertions, sum(r.evidence_count) AS evidence
            ORDER BY sessions DESC
            LIMIT 80
            """,
        ),
        factor_rows=_query(
            graph,
            """
            MATCH (r:FactorResult)
            RETURN r.factor_id AS factor_id, count(r) AS results, r.status AS status
            ORDER BY results DESC
            LIMIT 80
            """,
        ),
        run_status_rows=_query(
            graph,
            """
            MATCH (r:AnalysisRun)
            RETURN r.status AS status, count(r) AS count
            ORDER BY count DESC
            """,
        ),
        evidence_rows=_evidence_rows(graph),
        graph_links=_graph_links(graph),
    )


def _node_counts(graph: GraphLedgerRepository) -> list[dict[str, Any]]:
    rows = _query(
        graph,
        """
        MATCH (n)
        RETURN labels(n) AS labels, count(n) AS count
        ORDER BY count DESC
        """,
    )
    normalized: list[dict[str, Any]] = []
    for row in rows:
        labels = row.get("labels")
        label = " / ".join(str(item) for item in labels) if isinstance(labels, list) else str(labels or "")
        normalized.append({"label": label, "count": row.get("count")})
    return normalized


def _project_rows(graph: GraphLedgerRepository) -> list[dict[str, Any]]:
    rows = _query(
        graph,
        """
        MATCH (p:Project)-[:HAS_SESSION]->(s:Session)
        OPTIONAL MATCH (r:FactorResult)-[:ABOUT]->(s)
        OPTIONAL MATCH (s)-[:HAS_EVIDENCE_EVENT]->(e:ChatEventRef)
        RETURN p.project_label AS project, count(DISTINCT s) AS sessions,
               count(DISTINCT r) AS factor_results, count(DISTINCT e) AS evidence_events
        ORDER BY factor_results DESC, evidence_events DESC, sessions DESC
        LIMIT 50
        """,
    )
    return [
        {
            "project": row.get("project") or "",
            "sessions": row.get("sessions") or 0,
            "factor_results": row.get("factor_results") or 0,
            "evidence_events": row.get("evidence_events") or 0,
        }
        for row in rows
    ]


def _evidence_rows(graph: GraphLedgerRepository) -> list[dict[str, Any]]:
    rows = _query(
        graph,
        """
        MATCH (s:Session)-[:HAS_EVIDENCE_EVENT]->(e:ChatEventRef)
        RETURN s.session_id AS session_id, e.event_id AS event_id, e.role AS role,
               e.tool_name AS tool_name, e.content_preview_redacted AS content_preview,
               e.tool_result_preview_redacted AS tool_preview
        LIMIT 120
        """,
    )
    return [
        {
            "session_id": row.get("session_id") or "",
            "event_id": row.get("event_id") or "",
            "role": row.get("role") or "",
            "tool_name": row.get("tool_name") or "",
            "preview": row.get("content_preview") or row.get("tool_preview") or "",
        }
        for row in rows
    ]


def _edge_counts(graph: GraphLedgerRepository) -> list[dict[str, Any]]:
    return _query(
        graph,
        """
        MATCH ()-[r]->()
        RETURN type(r) AS type, count(r) AS count
        ORDER BY count DESC
        """,
    )


def _graph_links(graph: GraphLedgerRepository) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(
        {
            "source": str(row.get("session_node_id") or ""),
            "target": str(row.get("tag_node_id") or ""),
            "source_label": str(row.get("session_id") or ""),
            "target_label": f"{row.get('type')}:{row.get('value')}",
            "source_kind": "session",
            "target_kind": "tag",
            "kind": "tag",
        }
        for row in _query(
            graph,
            """
            MATCH (s:Session)-[:HAS_TAG_ROLLUP]->(t:Tag)
            RETURN s.id AS session_node_id, s.session_id AS session_id,
                   t.id AS tag_node_id, t.type AS type, t.value AS value
            LIMIT 160
            """,
        )
    )
    rows.extend(
        {
            "source": str(row.get("factor_node_id") or ""),
            "target": str(row.get("session_node_id") or ""),
            "source_label": str(row.get("factor_id") or ""),
            "target_label": str(row.get("session_id") or ""),
            "source_kind": "factor",
            "target_kind": "session",
            "kind": "factor",
        }
        for row in _query(
            graph,
            """
            MATCH (f:Factor)-[:RAN_IN]->(:AnalysisRun)-[:PRODUCED]->(:FactorResult)-[:ABOUT]->(s:Session)
            WHERE f.stub = false
            RETURN DISTINCT f.id AS factor_node_id, f.factor_id AS factor_id,
                   s.id AS session_node_id, s.session_id AS session_id
            LIMIT 80
            """,
        )
    )
    rows.extend(
        {
            "source": str(row.get("session_node_id") or ""),
            "target": str(row.get("event_node_id") or ""),
            "source_label": str(row.get("session_id") or ""),
            "target_label": str(row.get("event_id") or ""),
            "source_kind": "session",
            "target_kind": "event",
            "kind": "evidence",
        }
        for row in _query(
            graph,
            """
            MATCH (s:Session)-[:HAS_EVIDENCE_EVENT]->(e:ChatEventRef)
            RETURN s.id AS session_node_id, s.session_id AS session_id,
                   e.id AS event_node_id, e.event_id AS event_id
            LIMIT 80
            """,
        )
    )
    return [row for row in rows if row.get("source") and row.get("target")]


def _query(graph: GraphLedgerRepository, cypher: str) -> list[dict[str, Any]]:
    return graph.query(" ".join(line.strip() for line in cypher.strip().splitlines() if line.strip()))


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
