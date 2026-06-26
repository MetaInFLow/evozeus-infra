import json
import sqlite3

from evozeus_runtime.ledger.paths import RuntimePaths
from evozeus_runtime.ledger.repository import LedgerRepository
from evozeus_runtime.scanners.base import SessionMessageRef, SessionRef
from evozeus_runtime.sessions.schema import SessionEnvelope, SessionEvent


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
                    "session_group_key": "/Users/anthonyf/Documents/evozeus-web",
                    "session_group_label": "evozeus-web",
                },
            )
        ]
    )

    with sqlite3.connect(paths.result_index_db) as conn:
        row = conn.execute("SELECT project_key, project_label FROM sessions WHERE session_id = 's1'").fetchone()

    assert row == ("/Users/anthonyf/Documents/evozeus-web", "evozeus-web")
    status = ledger.list_session_statuses()[0]
    assert status.project_key == "/Users/anthonyf/Documents/evozeus-web"
    assert status.project_label == "evozeus-web"


def test_ledger_replaces_source_ref_alias_when_loaded_session_id_differs(tmp_path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    ledger = LedgerRepository(paths)
    source_path = tmp_path / "rollout-file-id.jsonl"
    source_path.write_text("{}", encoding="utf-8")

    ledger.record_session_refs([SessionRef(provider="codex", session_id="file-id", source_path=source_path)])
    ledger.record_session_envelope(
        SessionEnvelope(
            session_id="embedded-id",
            provider="codex",
            source_ref=str(source_path),
            events=[
                SessionEvent(
                    event_id="m1",
                    role="user",
                    content="run it",
                    metadata={"factor_channel": "user_input"},
                )
            ],
        )
    )

    statuses = ledger.list_session_statuses()

    assert [status.session_id for status in statuses] == ["embedded-id"]
    assert statuses[0].source_ref == str(source_path)


def test_ledger_stores_compact_event_metadata_without_duplicate_locator_payloads(tmp_path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    ledger = LedgerRepository(paths)
    source_path = tmp_path / "s1.jsonl"
    source_path.write_text("{}", encoding="utf-8")

    ledger.record_session_refs([SessionRef(provider="codex", session_id="s1", source_path=source_path)])
    ledger.record_session_message_refs(
        [
            SessionMessageRef(
                provider="codex",
                session_id="s1",
                message_id="m1",
                source_path=source_path,
                message_index=1,
                metadata={
                    "scanner_id": "codex.local",
                    "scanner_version": "0.1.0",
                    "role": "user",
                    "source_ref": str(source_path),
                    "source_fingerprint": "fingerprint",
                    "event_locator_json": "{\"large\":\"locator\"}",
                    "artifact_locator_json": "{\"large\":\"artifact\"}",
                    "content_hash": "content-hash",
                    "content_preview_redacted": "preview",
                    "tool_result_hash": "tool-hash",
                    "tool_result_preview_redacted": "tool preview",
                    "codex_record_type": "response_item",
                    "codex_event_type": "message",
                },
            )
        ]
    )

    with sqlite3.connect(paths.result_index_db) as conn:
        row = conn.execute(
            """
            SELECT event_locator_json, artifact_locator_json, metadata_json
            FROM session_events
            WHERE session_id = 's1' AND event_id = 'm1'
            """
        ).fetchone()

    assert row[0] == "{\"large\":\"locator\"}"
    assert row[1] == "{}"
    assert json.loads(row[2]) == {
        "codex_record_type": "response_item",
        "codex_event_type": "message",
    }
