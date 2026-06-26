import pytest

from evozeus_runtime.ledger.graph_repository import GraphLedgerRepository


def test_graphqlite_backend_normalizes_nested_python_api_rows(tmp_path):
    pytest.importorskip("graphqlite")

    graph = GraphLedgerRepository(tmp_path / "real-graph.sqlite3")
    graph.upsert_node(
        "tag_assertion:r1:session:codex:s1:signal:x",
        ["TagAssertion"],
        {"target_type": "chat_event"},
    )
    graph.upsert_node("chat_event:codex:s1:e1", ["ChatEventRef"], {"event_id": "e1"})
    graph.upsert_edge(
        "tag_assertion:r1:session:codex:s1:signal:x",
        "chat_event:codex:s1:e1",
        "ON",
        {},
    )

    assert graph.count_nodes("TagAssertion", {"target_type": "chat_event"}) == 1
    assert graph.count_edges("ON") == 1


def test_graphqlite_bulk_insert_mode_dedupes_nodes_and_keeps_edges(tmp_path):
    pytest.importorskip("graphqlite")

    graph = GraphLedgerRepository(tmp_path / "bulk-graph.sqlite3", bulk_insert_mode=True)
    graph.upsert_node("s1", ["Session"], {"session_id": "s1"})
    graph.upsert_node("s1", ["Session"], {"project_label": "EvoZeus"})
    graph.upsert_node("t1", ["Tag"], {"type": "signal", "value": "tool_failure"})
    graph.upsert_edge("s1", "t1", "HAS_TAG_ROLLUP", {"count": 1})
    graph.upsert_edge("s1", "t1", "HAS_TAG_ROLLUP", {"count": 2})
    graph.upsert_edge("s1", "t1", "USES_EVIDENCE", {"kind": "sample"})
    graph.upsert_edge("s1", "t1", "USES_EVIDENCE", {"kind": "sample"})

    assert graph.count_nodes("Session") == 1
    assert graph.get_node("s1")["project_label"] == "EvoZeus"
    assert graph.count_edges("HAS_TAG_ROLLUP") == 1
    assert graph.count_edges("USES_EVIDENCE") == 2


def test_graph_ledger_upserts_nodes_and_edges(tmp_path):
    graph = GraphLedgerRepository.for_tests(tmp_path / "graph.sqlite3")

    graph.upsert_node("session:codex:s1", ["Session"], {"session_id": "s1", "provider": "codex"})
    graph.upsert_node("tag:signal:tool_failure", ["Tag"], {"type": "signal", "value": "tool_failure"})
    graph.upsert_edge(
        "session:codex:s1",
        "tag:signal:tool_failure",
        "HAS_TAG_ROLLUP",
        {"count": 1},
    )

    graph.upsert_node("session:codex:s1", ["Session"], {"event_count": 3})

    assert graph.count_nodes("Session") == 1
    assert graph.get_node("session:codex:s1")["event_count"] == 3
    assert graph.count_edges("HAS_TAG_ROLLUP") == 1
    assert graph.stats() == {"node_count": 2, "edge_count": 1}
