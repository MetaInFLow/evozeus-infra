import sqlite3

from evozeus_runtime.factors.protocol import FactorResult, FactorStage
from evozeus_runtime.ledger.paths import RuntimePaths
from evozeus_runtime.ledger.repository import LedgerRepository
from evozeus_runtime.sessions.schema import SessionEnvelope, SessionEvent


def test_ledger_replaces_latest_factor_result_and_keeps_compact_datasets(tmp_path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    ledger = LedgerRepository(paths)
    session = SessionEnvelope(
        session_id="s1",
        provider="codex",
        source_ref="/tmp/s1.jsonl",
        events=[SessionEvent(event_id="u1", role="user", content="需要检查")],
        metadata={"source_fingerprint": "fp1"},
    )

    ledger.record_factor_run(
        session,
        [_result("old", tag_value="negative", count=1)],
        factor_ids=["official.user-input-sentiment"],
    )
    ledger.record_factor_run(
        session,
        [_result("new", tag_value="positive", count=2)],
        factor_ids=["official.user-input-sentiment"],
    )

    with sqlite3.connect(paths.result_index_db) as conn:
        factor_result_count = conn.execute("SELECT COUNT(*) FROM factor_results").fetchone()[0]
        dataset_count = conn.execute("SELECT COUNT(*) FROM factor_datasets").fetchone()[0]
        presentation_count = conn.execute("SELECT COUNT(*) FROM factor_presentations").fetchone()[0]
        event_tag_values = [
            row[0]
            for row in conn.execute(
                "SELECT tag_value FROM event_factor_tags ORDER BY tag_value"
            ).fetchall()
        ]

    assert factor_result_count == 1
    assert dataset_count == 1
    assert presentation_count == 1
    assert event_tag_values == ["positive"]

    latest = ledger.list_factor_results(session_id="s1")
    assert len(latest) == 1
    assert latest[0].run_id == "new"
    assert latest[0].statistics == {"overall_sentiment": "positive"}
    assert latest[0].datasets[0]["records"] == [{"event_id": "u1", "sentiment": "positive", "count": 2}]
    assert latest[0].presentations[0]["component_ref"] == "ui.native-static.table.v1"


def test_ledger_materializes_event_tags_from_dataset_records_without_cross_product(tmp_path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    ledger = LedgerRepository(paths)
    session = SessionEnvelope(
        session_id="s1",
        provider="codex",
        source_ref="/tmp/s1.jsonl",
        events=[
            SessionEvent(event_id=f"u{index}", role="user", content=f"message {index}")
            for index in range(1, 51)
        ],
        metadata={"source_fingerprint": "fp1"},
    )

    result = _result("large-evidence", tag_value="negative", count=1).model_copy(
        update={
            "datasets": [
                {
                    "id": "user_input_sentiment",
                    "semantic_type": "user_sentiment",
                    "shape": "record_set",
                    "primary_key": "event_id",
                    "records": [
                        {"event_id": "u1", "sentiment": "negative", "sentiment_score": -1.0},
                        {"event_id": "u2", "sentiment": "positive", "sentiment_score": 1.0},
                    ],
                    "schema": {"event_id": "string", "sentiment": "string"},
                }
            ],
            "evidence_refs": [{"ref_id": f"u{index}", "kind": "user_turn"} for index in range(1, 51)],
        }
    )

    ledger.record_factor_run(session, [result], factor_ids=["official.user-input-sentiment"])

    with sqlite3.connect(paths.result_index_db) as conn:
        event_tags = conn.execute(
            """
            SELECT event_id, tag_type, tag_value
            FROM event_factor_tags
            ORDER BY event_id, tag_type, tag_value
            """
        ).fetchall()

    assert event_tags == [
        ("u1", "user_sentiment", "negative"),
        ("u2", "user_sentiment", "positive"),
    ]


def _result(run_id: str, *, tag_value: str, count: int) -> FactorResult:
    return FactorResult(
        run_id=run_id,
        factor_id="official.user-input-sentiment",
        factor_version="v0.1.0",
        framework_id="evozeus.official",
        stage=FactorStage.SIGNAL_EXTRACTION,
        target_type="session",
        target_id="s1",
        session_id="s1",
        status="matched",
        tags=[{"type": "user_sentiment", "value": tag_value}],
        scores={"average_sentiment_score": 1.0},
        statistics={"overall_sentiment": tag_value},
        datasets=[
            {
                "id": "user_input_sentiment",
                "semantic_type": "user_sentiment",
                "shape": "record_set",
                "primary_key": "event_id",
                "records": [{"event_id": "u1", "sentiment": tag_value, "count": count}],
                "schema": {"event_id": "string", "sentiment": "string", "count": "number"},
            }
        ],
        presentations=[
            {
                "id": "sentiment_table",
                "title": "情绪明细",
                "component_ref": "ui.native-static.table.v1",
                "data_ref": "user_input_sentiment",
                "bindings": {"row_key": "event_id"},
                "routes": ["session.detail.factor_drawer"],
                "fallback": ["ui.native-static.json.v1"],
                "priority": 50,
            }
        ],
        evidence_refs=[{"ref_id": "u1", "kind": "user_turn"}],
        notes=["compact result"],
        confidence=0.9,
    )
