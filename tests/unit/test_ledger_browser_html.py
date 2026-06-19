from pathlib import Path

from evozeus_runtime.ledger.repository import (
    SessionAnalysisStatus,
    SessionEventRecord,
)
from evozeus_runtime.reports.ledger_browser import render_ledger_browser_html


def test_ledger_browser_html_renders_provider_project_session_and_chat():
    status = SessionAnalysisStatus(
        session_id="session-1",
        provider="codex",
        project_key="/Users/anthonyf/Documents/EvoZeus-community",
        project_label="EvoZeus-community",
        source_ref="/tmp/session-1.jsonl",
        event_count=1,
        discovered_at="2026-06-19T00:00:00+00:00",
        last_analyzed_at="",
        analyzed_factor_count=0,
        pending_factor_count=0,
        session_title="分析 scanner runner",
        session_cwd="/Users/anthonyf/Documents/EvoZeus-community",
        session_updated_at="2026-06-19T00:00:00+00:00",
    )
    event = SessionEventRecord(
        session_id="session-1",
        event_id="msg-1",
        event_index=1,
        role="user",
        content="看看 provider、project、session、chat",
        tool_name="",
        tool_result_preview="",
        source_ref="/tmp/session-1.jsonl",
        source_line=12,
        tags=[],
    )

    html = render_ledger_browser_html(
        statuses=[status],
        events=[event],
        ledger_path=Path("/tmp/evozeus/results.sqlite3"),
    )

    assert "EvoZeus SQLite Visualizer" in html
    assert 'data-provider="codex"' in html
    assert "EvoZeus-community" in html
    assert "session-1" in html
    assert "msg-1" in html
    assert "看看 provider、project、session、chat" in html
    assert "/tmp/evozeus/results.sqlite3" in html
