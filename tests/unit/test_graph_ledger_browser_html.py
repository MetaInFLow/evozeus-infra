from pathlib import Path

import pytest

from evozeus_runtime.ledger.graph_repository import GraphLedgerRepository
from evozeus_runtime.use_cases.generate_graph_ledger_browser import _build_snapshot
from evozeus_runtime.reports.graph_ledger_browser import GraphLedgerBrowserSnapshot, _flow_payload, render_graph_ledger_browser_html


def test_graph_ledger_browser_html_renders_core_views():
    snapshot = GraphLedgerBrowserSnapshot(
        graph_path=Path("/tmp/results.graph.sqlite3"),
        legacy_path=Path("/tmp/results.sqlite3"),
        graph_size_bytes=400,
        legacy_size_bytes=1000,
        node_counts=[
            {"label": "Session", "count": 3},
            {"label": "ChatEventRef", "count": 2},
        ],
        edge_counts=[{"type": "HAS_TAG_ROLLUP", "count": 2}],
        project_rows=[{"project": "EvoZeus", "sessions": 3, "factor_results": 8, "evidence_events": 2}],
        tag_rows=[{"type": "signal", "value": "tool_failure", "sessions": 2, "assertions": 4, "evidence": 2}],
        factor_rows=[{"factor_id": "default.tool_failure", "results": 3, "status": "matched"}],
        run_status_rows=[{"status": "completed", "count": 3}],
        evidence_rows=[
            {
                "session_id": "s1",
                "event_id": "e1",
                "role": "tool",
                "tool_name": "exec_command",
                "preview": "Traceback",
            }
        ],
        graph_links=[
            {
                "source": "factor:default.tool_failure:v1",
                "target": "session:codex:s1",
                "source_label": "default.tool_failure",
                "target_label": "s1",
                "source_kind": "factor",
                "target_kind": "session",
                "kind": "factor",
            },
            {
                "source": "session:codex:s1",
                "target": "tag:signal:tool_failure",
                "source_label": "s1",
                "target_label": "signal:tool_failure",
                "source_kind": "session",
                "target_kind": "tag",
                "kind": "tag",
            },
            {
                "source": "session:codex:s1",
                "target": "event:codex:s1:e1",
                "source_label": "s1",
                "target_label": "e1",
                "source_kind": "session",
                "target_kind": "event",
                "kind": "evidence",
            },
        ],
    )

    html = render_graph_ledger_browser_html(snapshot)

    assert "EvoZeus Graph Ledger Browser" in html
    assert "GraphQLite sparse evidence graph" in html
    assert 'data-tab-target="graph"' in html
    assert 'data-tab-target="relations"' in html
    assert 'data-tab-target="projects"' in html
    assert "@xyflow/react" in html
    assert "reactFlowRoot" in html
    assert "graphModel" in html
    assert "Relationship paths" in html
    assert "Factor -&gt; Session" in html
    assert "Session -&gt; Tag" in html
    assert "Session -&gt; Evidence" in html
    assert "60.0%" in html
    assert "EvoZeus" in html
    assert "信号：工具失败" in html
    assert "tool_failure" in html
    assert "exec_command" in html
    assert "graphData" not in html
    assert "<canvas" not in html
    assert "graphCanvas" not in html

    payload = _flow_payload(snapshot.graph_links)
    assert all(node["data"]["kind"] != "tag" for node in payload["nodes"])
    assert all(edge["data"]["kind"] != "tag" for edge in payload["edges"])
    session_node = next(node for node in payload["nodes"] if node["id"] == "session:codex:s1")
    assert session_node["data"]["tags"] == ["信号：工具失败"]
    assert "signal:tool_failure" in session_node["data"]["search"]
    assert "信号：工具失败" in session_node["data"]["search"]


def test_graph_ledger_browser_snapshot_uses_graph_relationships(tmp_path):
    pytest.importorskip("graphqlite")

    graph_path = tmp_path / "graph.sqlite3"
    graph = GraphLedgerRepository(graph_path)
    graph.upsert_node("project:codex:evozeus", ["Project"], {"project_label": "EvoZeus"})
    graph.upsert_node("project:codex:archive", ["Project"], {"project_label": "Archive"})
    graph.upsert_node("session:codex:s1", ["Session"], {"session_id": "s1", "project_label": "EvoZeus"})
    graph.upsert_node("session:codex:s2", ["Session"], {"session_id": "s2", "project_label": "Archive"})
    graph.upsert_node("session:codex:s3", ["Session"], {"session_id": "s3", "project_label": "Archive"})
    graph.upsert_node("event:codex:s1:e1", ["ChatEventRef"], {"event_id": "e1", "role": "tool", "tool_result_preview_redacted": "Traceback"})
    graph.upsert_node("factor:f:v1", ["Factor"], {"factor_id": "f", "version": "v1", "stub": False})
    graph.upsert_node("analysis_run:ar1", ["AnalysisRun"], {"status": "completed"})
    graph.upsert_node("factor_result:fr1", ["FactorResult"], {"factor_id": "f", "status": "matched"})
    graph.upsert_edge("project:codex:evozeus", "session:codex:s1", "HAS_SESSION", {})
    graph.upsert_edge("project:codex:archive", "session:codex:s2", "HAS_SESSION", {})
    graph.upsert_edge("project:codex:archive", "session:codex:s3", "HAS_SESSION", {})
    graph.upsert_edge("session:codex:s1", "event:codex:s1:e1", "HAS_EVIDENCE_EVENT", {})
    graph.upsert_edge("factor:f:v1", "analysis_run:ar1", "RAN_IN", {})
    graph.upsert_edge("analysis_run:ar1", "factor_result:fr1", "PRODUCED", {})
    graph.upsert_edge("factor_result:fr1", "session:codex:s1", "ABOUT", {})

    snapshot = _build_snapshot(graph=graph, graph_path=graph_path, legacy_path=None)

    assert snapshot.project_rows[:2] == [
        {"project": "EvoZeus", "sessions": 1, "factor_results": 1, "evidence_events": 1},
        {"project": "Archive", "sessions": 2, "factor_results": 0, "evidence_events": 0},
    ]
    assert snapshot.evidence_rows[0]["preview"] == "Traceback"
    assert {
        "source": "factor:f:v1",
        "target": "session:codex:s1",
        "source_label": "f",
        "target_label": "s1",
        "source_kind": "factor",
        "target_kind": "session",
        "kind": "factor",
    } in snapshot.graph_links
