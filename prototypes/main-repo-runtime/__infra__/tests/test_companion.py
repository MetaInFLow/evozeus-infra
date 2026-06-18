import json
from pathlib import Path

from fastapi.testclient import TestClient

from evozeus.companion.app import create_app
from evozeus.companion.tokens import create_one_time_token
from evozeus.runtime.paths import RuntimePaths
from evozeus.scanners.base import SessionRef
from evozeus.storage.sqlite_result_store import SQLiteResultStore

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESTDATA = PROJECT_ROOT / "__infra__" / "testdata"
BRIDGED_CODEX_SOURCES = [
    (
        "rollout-2026-06-14T14-55-35-019ec4ea-0f23-77b1-a2e0-92b897167191",
        "019ec4ea-0f23-77b1-a2e0-92b897167191",
        243,
    ),
    (
        "rollout-2026-05-13T16-18-30-019e206a-7e07-7050-be2c-4e8a9465d30b",
        "019e206a-7e07-7050-be2c-4e8a9465d30b",
        4,
    ),
    (
        "rollout-2026-04-21T18-37-58-019daf9e-45db-77e1-8a1f-0b71ab9a3c7f",
        "019daf9e-45db-77e1-8a1f-0b71ab9a3c7f",
        4,
    ),
    (
        "rollout-2026-05-26T15-35-47-019e6336-0fdd-7062-9597-a7d1c12d92c2",
        "019e6336-0fdd-7062-9597-a7d1c12d92c2",
        4,
    ),
    (
        "rollout-2026-04-29T13-42-14-019dd7c2-649b-7521-8b66-61a0f3a747ff",
        "019dd7c2-649b-7521-8b66-61a0f3a747ff",
        4,
    ),
]
PRIMARY_CODEX_SESSION_ID = BRIDGED_CODEX_SOURCES[0][1]
PRIMARY_CODEX_EVENT_COUNT = BRIDGED_CODEX_SOURCES[0][2]


def _write_fake_codex_sources(home: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for source_index, (source_id, session_id, event_count) in enumerate(BRIDGED_CODEX_SOURCES):
        source_path = home / ".codex" / "sessions" / "2026" / "06" / f"{14 + source_index:02d}" / f"{source_id}.jsonl"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        records: list[dict[str, object]] = [{"type": "session_meta", "payload": {"id": session_id}}]
        for event_index in range(event_count):
            payload: dict[str, object] = {
                "id": f"bridge-event-{event_index:03d}",
                "role": "user" if event_index % 2 == 0 else "assistant",
                "content": f"桥接生成事件 {source_index:02d}-{event_index:03d}",
            }
            if source_index == 0 and event_index == 2:
                payload = {
                    "id": f"bridge-event-{event_index:03d}",
                    "type": "function_call_output",
                    "call_id": "call-bridge-timeout",
                    "output": "fatal: network timeout",
                }
            records.append({"type": "response_item", "payload": payload})
        source_path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")
        paths[session_id] = source_path
    return paths


def test_create_one_time_token_returns_non_empty_token():
    assert create_one_time_token()


def test_companion_rejects_missing_token():
    client = TestClient(create_app(token="secret"))

    response = client.get("/")

    assert response.status_code == 403


def test_companion_accepts_valid_token():
    client = TestClient(create_app(token="secret"))

    response = client.get("/?token=secret")

    assert response.status_code == 200
    assert "EvoZeus Companion" in response.text


def test_companion_bootstrap_status_and_factor_routes(tmp_path):
    client = TestClient(create_app(token="secret", workspace_root=tmp_path))

    status = client.get("/api/bootstrap/status?token=secret")
    assert status.status_code == 200
    assert status.json()["initialized"] is False

    bootstrap = client.post("/api/bootstrap?token=secret")
    assert bootstrap.status_code == 200
    assert bootstrap.json()["initialized"] is True

    factors = client.get("/api/factors?token=secret")
    routes = client.get("/api/routes?token=secret")
    assert factors.status_code == 200
    assert routes.status_code == 200
    assert len(factors.json()["factors"]) >= 8
    assert any(factor["factor_id"] == "default.tool_failure" for factor in factors.json()["factors"])
    assert any(route["route_area"] == "dashboard" for route in routes.json()["routes"])


def test_companion_lists_sessions_from_sqlite(tmp_path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    store = SQLiteResultStore(paths)
    store.record_session_refs(
        [
            SessionRef(
                provider="codex",
                session_id="session-alpha",
                source_path=tmp_path / "session-alpha.jsonl",
            )
        ]
    )
    client = TestClient(create_app(token="secret", workspace_root=tmp_path))

    response = client.get("/api/sessions?token=secret&factor_id=default.open_loop")

    assert response.status_code == 200
    sessions = response.json()["sessions"]
    assert sessions[0]["session_id"] == "session-alpha"
    assert sessions[0]["provider"] == "codex"
    assert sessions[0]["pending_factor_count"] == 1


def test_companion_scans_and_analyzes_session(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    source_paths = _write_fake_codex_sources(fake_home)
    monkeypatch.setenv("HOME", str(fake_home))
    client = TestClient(create_app(token="secret", workspace_root=tmp_path))
    client.post("/api/bootstrap?token=secret")

    scan = client.post(f"/api/scan?token=secret&source={TESTDATA / 'codex_sessions'}")
    assert scan.status_code == 200
    assert scan.json()["session_count"] == 5

    analyze = client.post(f"/api/analyze/{PRIMARY_CODEX_SESSION_ID}?token=secret&factor_id=default.open_loop")
    assert analyze.status_code == 200
    assert analyze.json()["session_id"] == PRIMARY_CODEX_SESSION_ID
    assert analyze.json()["result_count"] == 1
    assert analyze.json()["html_path"].endswith("factor-results.html")

    sessions = client.get("/api/sessions?token=secret&factor_id=default.open_loop").json()["sessions"]
    by_id = {session["session_id"]: session for session in sessions}
    assert by_id[PRIMARY_CODEX_SESSION_ID]["pending_factor_count"] == 0
    assert by_id[PRIMARY_CODEX_SESSION_ID]["analyzed_factor_count"] == 1
    assert by_id[PRIMARY_CODEX_SESSION_ID]["event_count"] == PRIMARY_CODEX_EVENT_COUNT
    assert by_id[PRIMARY_CODEX_SESSION_ID]["source_ref"] == str(source_paths[PRIMARY_CODEX_SESSION_ID])
    assert by_id[PRIMARY_CODEX_SESSION_ID]["first_user_preview"] == "桥接生成事件 00-000"
    assert by_id[PRIMARY_CODEX_SESSION_ID]["first_user_source_line"] == 2
