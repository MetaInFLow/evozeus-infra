import subprocess
import sys

from evozeus_runtime.factors.protocol import FactorResult, FactorStage
from evozeus_runtime.ledger.graph_repository import GraphLedgerRepository
from evozeus_runtime.ledger.migrate_sqlite_to_graphqlite import migrate_workspace_sqlite_to_graphqlite
from evozeus_runtime.ledger.paths import RuntimePaths
from evozeus_runtime.ledger.repository import LedgerRepository
from evozeus_runtime.scanners.base import SessionRef
from evozeus_runtime.sessions.schema import SessionEnvelope, SessionEvent


def test_migrate_legacy_sqlite_to_sparse_graph(tmp_path):
    legacy_path = _write_legacy_ledger(tmp_path)
    output_path = tmp_path / ".evozeus" / "runtime" / "index" / "results.graph.sqlite3"

    result = migrate_workspace_sqlite_to_graphqlite(
        workspace_root=tmp_path,
        legacy_db_path=legacy_path,
        output_db_path=output_path,
        backend="sqlite",
    )

    assert result.ok
    assert output_path.exists()
    assert all(check.ok for check in result.checks)

    graph = GraphLedgerRepository.for_tests(output_path)
    assert graph.count_nodes("Session") == 1
    assert graph.count_nodes("SourceRef") == 1
    assert graph.count_nodes("FactorResult") == 1
    assert graph.count_nodes("AnalysisRun") == 1
    assert graph.count_nodes("ChatEventRef") == 1
    assert graph.count_nodes("TagAssertion") == 2
    assert graph.count_nodes("TagAssertion", {"target_type": "chat_event"}) == 1
    assert graph.count_edges("USES_EVIDENCE") == 1
    assert graph.count_edges("HAS_TAG_ROLLUP") == 1


def test_migration_script_writes_count_checks(tmp_path):
    _write_legacy_ledger(tmp_path)

    run = subprocess.run(
        [
            sys.executable,
            "scripts/migrate_sqlite_to_graphqlite.py",
            "--workspace",
            str(tmp_path),
            "--sqlite-test-backend",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    assert "migration_id=" in run.stdout
    assert "check=sessions legacy=1 graph=1 op=== status=ok" in run.stdout
    assert "check=session_events_sparse legacy=2 graph=1 op=>= status=ok" in run.stdout


def _write_legacy_ledger(tmp_path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    ledger = LedgerRepository(paths)
    source_path = tmp_path / "s1.jsonl"
    source_path.write_text("{}", encoding="utf-8")
    ledger.record_session_refs(
        [
            SessionRef(
                provider="codex",
                session_id="s1",
                source_path=source_path,
                metadata={"session_group_key": "/tmp/evozeus", "session_group_label": "EvoZeus"},
            )
        ]
    )
    session = SessionEnvelope(
        session_id="s1",
        provider="codex",
        source_ref=str(source_path),
        events=[
            SessionEvent(
                event_id="u1",
                role="user",
                content="工具失败了",
                metadata={"factor_channel": "user_input", "source_ref": str(source_path)},
            ),
            SessionEvent(
                event_id="a1",
                role="assistant",
                content="收到",
                metadata={"factor_channel": "assistant_result", "source_ref": str(source_path)},
            ),
        ],
        metadata={"session_group_key": "/tmp/evozeus", "session_group_label": "EvoZeus"},
    )
    result = FactorResult(
        run_id="frun_1",
        factor_id="default.tool_failure",
        factor_version="0.1.0",
        framework_id="default",
        stage=FactorStage.SIGNAL_EXTRACTION,
        target_type="session",
        target_id="s1",
        session_id="s1",
        status="matched",
        tags=[{"type": "signal", "value": "tool_failure"}],
        scores={"severity": 1.0},
        statistics={"count": 1},
        datasets=[
            {
                "id": "tool_failures",
                "semantic_type": "tool_failure",
                "shape": "record_set",
                "primary_key": "event_id",
                "records": [{"event_id": "u1", "signal": "tool_failure"}],
                "schema": {"event_id": "string", "signal": "string"},
            }
        ],
        presentations=[],
        evidence_refs=[{"ref_id": "u1", "kind": "user_turn"}],
        confidence=0.9,
    )
    ledger.record_factor_run(session, [result], factor_ids=["default.tool_failure"])
    return paths.result_index_db
