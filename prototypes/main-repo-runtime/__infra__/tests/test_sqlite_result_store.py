from pathlib import Path

from evozeus.core.session import SessionEnvelope
from evozeus.factors.protocol import FactorResult, FactorStage
from evozeus.factors.packs import FactorPackRepository
from evozeus.models import SessionEvent, Verdict
from evozeus.runtime.paths import RuntimePaths
from evozeus.scanners.base import SessionRef
from evozeus.storage.sqlite_result_store import SQLiteResultStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACK_ROOT = PROJECT_ROOT / "__infra__" / "factor_packs"


def test_sqlite_result_store_initializes_capability_and_route_tables(tmp_path: Path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    SQLiteResultStore(paths)

    with _connect(paths) as conn:
        table_names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }

    assert "source_refs" in table_names
    assert "installed_factors" in table_names
    assert "factor_capabilities" in table_names
    assert "factor_result_routes" in table_names


def test_sqlite_result_store_uses_lightweight_session_event_columns(tmp_path: Path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    SQLiteResultStore(paths)

    with _connect(paths) as conn:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(session_events)").fetchall()
        }

    assert "content" not in columns
    assert "tool_result_json" not in columns
    assert "content_hash" in columns
    assert "content_preview_redacted" in columns
    assert "event_locator_json" in columns
    assert "artifact_locator_json" in columns
    assert "scanner_id" in columns
    assert "scanner_version" in columns


def test_sqlite_result_store_records_installed_factor_capabilities_and_routes(tmp_path: Path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    store = SQLiteResultStore(paths)
    packs = FactorPackRepository(PACK_ROOT).discover()

    store.record_installed_factors(packs, source="bundled")
    store.record_default_routes(packs)

    factors = store.list_installed_factors()
    routes = store.list_factor_result_routes()
    tool_failure = next(factor for factor in factors if factor.factor_id == "default.tool_failure")
    tool_failure_routes = [route for route in routes if route.factor_id == "default.tool_failure"]

    assert len(factors) == 8
    assert tool_failure.version == "0.1.0"
    assert tool_failure.source == "bundled"
    assert tool_failure.enabled is True
    assert tool_failure.runtime_mode == "in_process"
    assert tool_failure.status == "available"
    assert tool_failure.supported_providers == ["codex"]
    assert tool_failure.supported_target_types == ["session"]
    assert any(route.route_area == "dashboard" for route in tool_failure_routes)
    assert any(route.route_area == "sessions_table" for route in tool_failure_routes)
    assert any(route.route_area == "drawer" for route in tool_failure_routes)


def test_sqlite_result_store_records_sessions_results_tags_and_event_content(tmp_path: Path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    store = SQLiteResultStore(paths)
    session = _session("session-alpha")
    result = FactorResult(
        factor_id="default.tool_failure",
        factor_version="0.1.0",
        framework_id="agent_session_review.v0",
        stage=FactorStage.SIGNAL_EXTRACTION,
        target_type="session",
        target_id=session.session_id,
        session_id=session.session_id,
        status="matched",
        tags=[{"type": "tool_failure", "value": "exec_command"}],
        scores={"tool_failure": 1.0},
        evidence_refs=[{"ref_id": "t1", "kind": "tool_event"}],
        verdict_signals=[Verdict.FIX_ENVIRONMENT.value],
        confidence=0.82,
    )

    analysis_run_id = store.record_factor_run(
        session,
        [result],
        factor_ids=["default.tool_failure"],
    )

    assert analysis_run_id.startswith("arun_")
    assert paths.result_index_db.exists()

    statuses = store.list_session_statuses(factor_ids=["default.tool_failure"])
    assert [(row.session_id, row.event_count, row.analyzed_factor_count, row.pending_factor_count) for row in statuses] == [
        ("session-alpha", 2, 1, 0)
    ]
    assert statuses[0].last_analyzed_at

    event_tags = store.list_event_factor_tags(session_id="session-alpha")
    assert len(event_tags) == 1
    event_tag = event_tags[0]
    assert event_tag.event_id == "t1"
    assert event_tag.role == "tool"
    assert event_tag.content == "fatal: network timeout"
    assert event_tag.factor_id == "default.tool_failure"
    assert event_tag.tag_type == "tool_failure"
    assert event_tag.tag_value == "exec_command"
    assert event_tag.analysis_run_id == analysis_run_id


def test_sqlite_result_store_records_loaded_session_preview_and_source_locator(tmp_path: Path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    store = SQLiteResultStore(paths)
    session = SessionEnvelope(
        session_id="session-preview",
        provider="codex",
        source_ref="session-preview.jsonl",
        events=[
            SessionEvent(
                event_id="u1",
                role="user",
                content="这个 factor 结果不对，没改到默认输出",
                metadata={
                    "content_preview_redacted": "这个 factor 结果不对，没改到默认输出",
                    "event_locator_json": {
                        "payload": {
                            "source_path": "session-preview.jsonl",
                            "line_start": 1,
                        }
                    },
                },
            ),
            SessionEvent(
                event_id="a1",
                role="assistant",
                content="我会运行指定 factor。",
                metadata={
                    "content_preview_redacted": "我会运行指定 factor。",
                    "event_locator_json": {
                        "payload": {
                            "source_path": "session-preview.jsonl",
                            "line_start": 2,
                        }
                    },
                },
            ),
        ],
    )

    store.record_session_envelope(session)

    statuses = store.list_session_statuses(factor_ids=["default.tool_failure"])
    status = statuses[0]
    assert status.event_count == 2
    assert status.first_user_preview == "这个 factor 结果不对，没改到默认输出"
    assert status.first_user_source_ref == "session-preview.jsonl"
    assert status.first_user_source_line == 1
    assert status.last_assistant_preview == "我会运行指定 factor。"
    assert status.last_assistant_source_ref == "session-preview.jsonl"
    assert status.last_assistant_source_line == 2


def test_sqlite_result_store_lists_full_session_events_with_factor_tags(tmp_path: Path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    store = SQLiteResultStore(paths)
    session = SessionEnvelope(
        session_id="session-alpha",
        provider="codex",
        source_ref="session-alpha.jsonl",
        events=[
            SessionEvent(
                event_id="u1",
                role="user",
                content="请修复 runtime scanner",
                metadata={
                    "content_preview_redacted": "请修复 runtime scanner",
                    "event_locator_json": {
                        "payload": {
                            "source_path": "session-alpha.jsonl",
                            "line_start": 1,
                        }
                    },
                },
            ),
            SessionEvent(
                event_id="t1",
                role="tool",
                content="fatal: network timeout",
                tool_name="exec_command",
                tool_result={"stderr": "fatal: network timeout"},
                metadata={
                    "content_preview_redacted": "fatal: network timeout",
                    "tool_result_preview_redacted": '{"stderr": "fatal: network timeout"}',
                    "event_locator_json": {
                        "payload": {
                            "source_path": "session-alpha.jsonl",
                            "line_start": 2,
                        }
                    },
                },
            ),
        ],
    )
    result = FactorResult(
        factor_id="default.tool_failure",
        factor_version="0.1.0",
        framework_id="agent_session_review.v0",
        stage=FactorStage.SIGNAL_EXTRACTION,
        target_type="session",
        target_id=session.session_id,
        session_id=session.session_id,
        status="matched",
        tags=[{"type": "tool_failure", "value": "exec_command"}],
        scores={"tool_failure": 1.0},
        evidence_refs=[{"ref_id": "t1", "kind": "tool_event"}],
        verdict_signals=[Verdict.FIX_ENVIRONMENT.value],
        confidence=0.82,
    )

    store.record_factor_run(session, [result], factor_ids=["default.tool_failure"])

    events = store.list_session_events(session_id="session-alpha")
    assert [event.event_id for event in events] == ["u1", "t1"]
    assert events[0].content == "请修复 runtime scanner"
    assert events[0].source_ref == "session-alpha.jsonl"
    assert events[0].source_line == 1
    assert events[0].tags == []
    assert events[1].role == "tool"
    assert events[1].tool_name == "exec_command"
    assert events[1].tool_result_preview == '{"stderr": "fatal: network timeout"}'
    assert events[1].source_line == 2
    assert [(tag.factor_id, tag.tag_type, tag.tag_value, tag.reason) for tag in events[1].tags] == [
        ("default.tool_failure", "tool_failure", "exec_command", "")
    ]


def test_sqlite_result_store_marks_discovered_sessions_pending_until_factor_run(tmp_path: Path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    store = SQLiteResultStore(paths)
    store.record_session_refs(
        [
            SessionRef(provider="codex", session_id="session-alpha", source_path=Path("session-alpha.jsonl")),
            SessionRef(provider="codex", session_id="session-beta", source_path=Path("session-beta.jsonl")),
        ]
    )

    store.record_factor_run(
        _session("session-alpha"),
        [
            FactorResult(
                factor_id="default.open_loop",
                factor_version="0.1.0",
                framework_id="agent_session_review.v0",
                stage=FactorStage.SIGNAL_EXTRACTION,
                target_type="session",
                target_id="session-alpha",
                session_id="session-alpha",
                status="skipped",
                confidence=0.0,
            )
        ],
        factor_ids=["default.open_loop"],
    )

    statuses = store.list_session_statuses(factor_ids=["default.open_loop"])
    by_id = {row.session_id: row for row in statuses}

    assert by_id["session-alpha"].pending_factor_count == 0
    assert by_id["session-alpha"].last_analyzed_at
    assert by_id["session-beta"].event_count == 0
    assert by_id["session-beta"].analyzed_factor_count == 0
    assert by_id["session-beta"].pending_factor_count == 1
    assert by_id["session-beta"].last_analyzed_at == ""


def test_sqlite_result_store_persists_scanner_session_group_metadata(tmp_path: Path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    store = SQLiteResultStore(paths)
    source_path = Path("/Users/anthonyf/.codex/sessions/2026/06/17/rollout-example.jsonl")

    store.record_session_refs(
        [
            SessionRef(
                provider="codex",
                session_id="session-grouped",
                source_path=source_path,
                metadata={
                    "session_title": "修复 Codex scanner 聚合",
                    "session_cwd": "/Users/anthonyf/Documents/EvoZeus",
                    "session_group_key": "/Users/anthonyf/Documents/EvoZeus",
                    "session_group_label": "EvoZeus",
                    "session_updated_at": "1781679600",
                    "codex_source_root": "/Users/anthonyf/.codex",
                },
            )
        ]
    )

    status = store.list_session_statuses(factor_ids=["default.open_loop"])[0]
    ref = store.get_session_ref("session-grouped")

    assert status.session_id == "session-grouped"
    assert status.session_title == "修复 Codex scanner 聚合"
    assert status.session_cwd == "/Users/anthonyf/Documents/EvoZeus"
    assert status.session_group_key == "/Users/anthonyf/Documents/EvoZeus"
    assert status.session_group_label == "EvoZeus"
    assert status.session_updated_at == "1781679600"
    assert status.pending_factor_count == 1
    assert ref.metadata["session_group_label"] == "EvoZeus"
    assert ref.metadata["source_ref"] == str(source_path)


def test_sqlite_result_store_replaces_stale_discovered_session_id_for_same_source(tmp_path: Path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    store = SQLiteResultStore(paths)
    source_path = Path("session-archive-shape.jsonl")

    store.record_session_refs([SessionRef(provider="codex", session_id="session-archive-shape", source_path=source_path)])
    store.record_session_refs([SessionRef(provider="codex", session_id="archive-session", source_path=source_path)])

    statuses = store.list_session_statuses(factor_ids=["default.open_loop"])

    assert [row.session_id for row in statuses] == ["archive-session"]
    assert statuses[0].pending_factor_count == 1


def test_sqlite_result_store_marks_factor_run_stale_when_source_fingerprint_changes(tmp_path: Path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    store = SQLiteResultStore(paths)
    source_path = Path("session-alpha.jsonl")
    store.record_session_refs(
        [
            SessionRef(
                provider="codex",
                session_id="session-alpha",
                source_path=source_path,
                metadata={
                    "source_size": "10",
                    "source_mtime": "100",
                    "source_fingerprint": "sha256:old",
                },
            )
        ]
    )
    session = _session("session-alpha", metadata={"source_fingerprint": "sha256:old"})
    store.record_factor_run(
        session,
        [
            FactorResult(
                factor_id="default.open_loop",
                factor_version="0.1.0",
                framework_id="agent_session_review.v0",
                stage=FactorStage.SIGNAL_EXTRACTION,
                target_type="session",
                target_id="session-alpha",
                session_id="session-alpha",
                status="skipped",
                confidence=0.0,
            )
        ],
        factor_ids=["default.open_loop"],
    )
    store.record_session_refs(
        [
            SessionRef(
                provider="codex",
                session_id="session-alpha",
                source_path=source_path,
                metadata={
                    "source_size": "11",
                    "source_mtime": "101",
                    "source_fingerprint": "sha256:new",
                },
            )
        ]
    )

    statuses = store.list_session_statuses(factor_ids=["default.open_loop"])

    assert statuses[0].analyzed_factor_count == 1
    assert statuses[0].pending_factor_count == 1
    assert statuses[0].stale_reason == "source_changed"


def _connect(paths: RuntimePaths):
    import sqlite3

    return sqlite3.connect(paths.result_index_db)


def _session(session_id: str, *, metadata: dict[str, str] | None = None) -> SessionEnvelope:
    return SessionEnvelope(
        session_id=session_id,
        provider="codex",
        source_ref=f"{session_id}.jsonl",
        events=[
            SessionEvent(event_id="u1", role="user", content="请修复 runtime scanner"),
            SessionEvent(
                event_id="t1",
                role="tool",
                content="fatal: network timeout",
                tool_name="exec_command",
                tool_result={"stderr": "fatal: network timeout"},
            ),
        ],
        metadata=metadata or {},
    )
