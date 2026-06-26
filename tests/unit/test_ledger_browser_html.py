from pathlib import Path

from evozeus_runtime.factors.protocol import FactorResult, FactorStage
from evozeus_runtime.ledger.repository import (
    SessionAnalysisStatus,
    SessionEventTag,
    SessionEventRecord,
)
from evozeus_runtime.reports.ledger_browser import render_ledger_browser_html


def test_ledger_browser_html_renders_provider_project_session_and_chat():
    status = SessionAnalysisStatus(
        session_id="session-1",
        provider="codex",
        project_key="/Users/anthonyf/Documents/evozeus-web",
        project_label="evozeus-web",
        source_ref="/tmp/session-1.jsonl",
        event_count=1,
        discovered_at="2026-06-19T00:00:00+00:00",
        last_analyzed_at="",
        analyzed_factor_count=0,
        pending_factor_count=0,
        session_title="分析 scanner runner",
        session_cwd="/Users/anthonyf/Documents/evozeus-web",
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
        tags=[
            SessionEventTag(
                factor_id="official.user-input-sentiment",
                tag_type="user_sentiment",
                tag_value="dissatisfaction",
                reason="classified",
                result_run_id="frun-1",
                analysis_run_id="arun-1",
                last_run_at="2026-06-19T00:00:00+00:00",
            )
        ],
    )

    html = render_ledger_browser_html(
        statuses=[status],
        events=[event],
        factor_results=[
            FactorResult(
                run_id="frun-1",
                factor_id="official.user-input-sentiment",
                factor_version="v0.1.0",
                framework_id="evozeus.official",
                stage=FactorStage.SIGNAL_EXTRACTION,
                target_type="session",
                target_id="session-1",
                session_id="session-1",
                status="matched",
                tags=[{"type": "user_sentiment", "value": "dissatisfaction"}],
                scores={"average_sentiment_score": -0.8},
                statistics={"dominant_sentiment_kind": "dissatisfaction"},
                datasets=[
                    {
                        "id": "sentiment_distribution",
                        "semantic_type": "frequency_distribution",
                        "shape": "record_set",
                        "primary_key": "sentiment_kind",
                        "records": [{"sentiment_kind": "dissatisfaction", "count": 1}],
                        "schema": {"sentiment_kind": "string", "count": "number"},
                    }
                ],
                presentations=[
                    {
                        "id": "sentiment_chart",
                        "title": "用户情绪分布",
                        "component_ref": "ui.native-static.bar-chart.v1",
                        "data_ref": "sentiment_distribution",
                        "bindings": {"x": "sentiment_kind", "y": "count"},
                        "routes": ["canvas.global.insights", "session.detail.factor_drawer"],
                        "fallback": ["ui.native-static.table.v1"],
                        "priority": 75,
                    }
                ],
                evidence_refs=[{"ref_id": "msg-1", "kind": "user_turn"}],
                confidence=0.8,
            )
        ],
        ledger_path=Path("/tmp/evozeus/results.sqlite3"),
    )

    assert "Codex SKILL Candidate Finder" in html
    assert "找到需要被总结成 SKILL 的 sessions" in html
    assert "SKILL.md 方法层" in html
    assert 'data-tab-target="skill-candidates"' in html
    assert 'data-tab-target="sessions"' in html
    assert 'data-tab-target="global-canvas"' in html
    assert 'data-tab-target="run-health"' in html
    assert "SKILL 候选识别结果" in html
    assert "SKILL Candidates" in html
    assert "problem_skill_candidate" in html
    assert "建议沉淀成" in html
    assert "quality-row" in html
    assert "Global Canvas" in html
    assert "Run Health" in html
    assert "ui.native-static.bar-chart.v1" in html
    assert "用户情绪分布" in html
    assert "dissatisfaction" in html
    assert "sentiment:negative" in html
    assert "不满意 chat" in html
    assert 'data-filter-value="dissatisfaction"' in html
    assert 'data-filter-value="sentiment:negative"' in html
    assert "function normalizedTerms()" in html
    assert 'project.querySelector(".session:not(.hidden)")' in html
    assert 'data-provider="codex"' in html
    assert "evozeus-web" in html
    assert "session-1" in html
    assert "msg-1" in html
    assert "看看 provider、project、session、chat" in html
    assert "/tmp/evozeus/results.sqlite3" in html


def test_ledger_browser_html_bounds_rendered_events_for_large_sessions():
    status = SessionAnalysisStatus(
        session_id="session-large",
        provider="codex",
        project_key="p1",
        project_label="P1",
        source_ref="/tmp/session-large.jsonl",
        event_count=120,
        discovered_at="2026-06-19T00:00:00+00:00",
        last_analyzed_at="",
        analyzed_factor_count=0,
        pending_factor_count=0,
    )
    events = [
        SessionEventRecord(
            session_id="session-large",
            event_id=f"msg-{index}",
            event_index=index,
            role="tool",
            content=f"tool event {index}",
            tool_name="exec_command",
            tool_result_preview="",
            source_ref="/tmp/session-large.jsonl",
            source_line=index,
            tags=[],
        )
        for index in range(1, 121)
    ]

    html = render_ledger_browser_html(statuses=[status], events=events, ledger_path=Path("/tmp/evozeus/results.sqlite3"))

    assert "已省略" in html
    assert "完整索引保留在 SQLite ledger" in html
    assert "tool event 60" not in html
