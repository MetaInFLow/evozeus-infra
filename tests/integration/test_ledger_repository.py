import sqlite3

from evozeus_runtime.ledger.paths import RuntimePaths
from evozeus_runtime.ledger.repository import LedgerRepository
from evozeus_runtime.scanners.base import SessionRef


def test_ledger_records_session_refs(tmp_path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    ledger = LedgerRepository(paths)

    ledger.record_session_refs([
        SessionRef(provider="codex", session_id="s1", source_path=tmp_path / "s1.jsonl")
    ])

    statuses = ledger.list_session_statuses()
    assert len(statuses) == 1
    assert statuses[0].session_id == "s1"
    assert statuses[0].provider == "codex"


def test_ledger_records_project_fields_on_sessions(tmp_path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    ledger = LedgerRepository(paths)

    ledger.record_session_refs(
        [
            SessionRef(
                provider="codex",
                session_id="s1",
                source_path=tmp_path / "s1.jsonl",
                metadata={
                    "session_group_key": "/Users/anthonyf/Documents/EvoZeus-community",
                    "session_group_label": "EvoZeus-community",
                },
            )
        ]
    )

    with sqlite3.connect(paths.result_index_db) as conn:
        row = conn.execute("SELECT project_key, project_label FROM sessions WHERE session_id = 's1'").fetchone()

    assert row == ("/Users/anthonyf/Documents/EvoZeus-community", "EvoZeus-community")
    status = ledger.list_session_statuses()[0]
    assert status.project_key == "/Users/anthonyf/Documents/EvoZeus-community"
    assert status.project_label == "EvoZeus-community"
