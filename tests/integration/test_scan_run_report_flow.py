from pathlib import Path

from evozeus_runtime.ledger.paths import RuntimePaths
from evozeus_runtime.ledger.repository import LedgerRepository
from evozeus_runtime.use_cases.generate_report import generate_report
from evozeus_runtime.use_cases.generate_ledger_browser import generate_ledger_browser
from evozeus_runtime.use_cases.run_factors import run_factors
from evozeus_runtime.use_cases.scan_sessions import scan_sessions


def test_scan_sessions_uses_default_codex_dirs_when_source_is_omitted(monkeypatch, tmp_path):
    home = tmp_path / "home"
    source = home / ".codex" / "sessions"
    source.mkdir(parents=True)
    fixture = Path("tests/fixtures/codex_sessions/session-minimal.jsonl")
    (source / "session-minimal.jsonl").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    scan_result = scan_sessions(
        workspace_root=tmp_path / "workspace",
        provider="codex",
        source_dir=None,
    )

    assert scan_result.session_count == 1


def test_scan_sessions_records_message_ids_without_content(tmp_path):
    scan_sessions(
        workspace_root=tmp_path,
        provider="codex",
        source_dir=Path("tests/fixtures/codex_sessions"),
    )

    ledger = LedgerRepository(RuntimePaths.for_workspace(tmp_path).ensure())
    events = ledger.list_session_events(session_id="session-minimal")

    assert [event.event_id for event in events] == ["event_0002", "event_0003", "event_0004"]
    assert [event.role for event in events] == ["user", "tool", "task_complete"]
    assert [event.tool_name for event in events] == ["", "exec_command", ""]
    assert all(event.content == "" for event in events)
    assert all(event.tool_result_preview == "" for event in events)


def test_scan_run_report_flow_writes_local_artifacts(tmp_path):
    scan_result = scan_sessions(
        workspace_root=tmp_path,
        provider="codex",
        source_dir=Path("tests/fixtures/codex_sessions"),
    )

    assert scan_result.session_count == 1
    assert scan_result.ledger_path.exists()

    run_result = run_factors(
        workspace_root=tmp_path,
        session_id="session-minimal",
        factor_ids=["default.tool_failure"],
        pack_root=Path("tests/fixtures/factor_packs"),
    )

    assert run_result.result_count == 1
    assert run_result.error_count == 0

    report_result = generate_report(
        workspace_root=tmp_path,
        session_id="session-minimal",
        formats=["markdown", "json", "html"],
    )

    assert report_result.markdown_path.exists()
    assert report_result.json_path.exists()
    assert report_result.html_path.exists()
    assert "default.tool_failure" in report_result.markdown_path.read_text(encoding="utf-8")


def test_generate_ledger_browser_writes_provider_project_session_chat_html(tmp_path):
    scan_sessions(
        workspace_root=tmp_path,
        provider="codex",
        source_dir=Path("tests/fixtures/codex_sessions"),
    )

    result = generate_ledger_browser(workspace_root=tmp_path)

    html = result.html_path.read_text(encoding="utf-8")
    assert result.html_path.exists()
    assert result.ledger_path == RuntimePaths.for_workspace(tmp_path).result_index_db
    assert "EvoZeus SQLite Visualizer" in html
    assert "codex" in html
    assert "session-minimal" in html
    assert "event_0002" in html
    assert "results.sqlite3" in html
