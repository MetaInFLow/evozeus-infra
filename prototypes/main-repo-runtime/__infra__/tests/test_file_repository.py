from pathlib import Path

from evozeus.core.session import SessionEnvelope
from evozeus.factors.protocol import FactorResult, FactorStage
from evozeus.factors.packs import FactorPackRepository
from evozeus.models import SessionEvent, Verdict
from evozeus.reports.html_report import render_factor_results_html
from evozeus.runtime.paths import RuntimePaths
from evozeus.storage.file_repository import FileSessionRepository
from evozeus.storage.sqlite_result_store import SessionAnalysisStatus, SessionEventRecord, SessionEventTag


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACK_ROOT = PROJECT_ROOT / "__infra__" / "factor_packs"


def test_file_repository_persists_session_and_factor_results(tmp_path: Path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    repository = FileSessionRepository(paths)
    envelope = SessionEnvelope(
        session_id="ezs_001",
        provider="codex",
        source_ref="session.jsonl",
        events=[SessionEvent(event_id="u1", role="user", content="hello")],
    )
    result = FactorResult(
        factor_id="default.test",
        factor_version="0.1.0",
        framework_id="agent_session_review.v0",
        stage=FactorStage.SIGNAL_EXTRACTION,
        target_type="session",
        target_id="ezs_001",
        session_id="ezs_001",
        verdict_signals=[Verdict.PRESERVE.value],
        confidence=0.7,
    )

    repository.write_session(envelope)
    repository.append_factor_results("ezs_001", [result])

    session_dir = paths.session_dir("ezs_001")
    report = (session_dir / "factor-results.md").read_text(encoding="utf-8")
    assert "## Factor Results" in report
    assert "default.test" in report
    assert "Preserve" in report
    assert not (session_dir / "factor-results.jsonl").exists()


def test_file_repository_writes_html_report_for_selected_factor_results(tmp_path: Path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    repository = FileSessionRepository(paths)
    packs = FactorPackRepository(PACK_ROOT).discover()
    results = [
        FactorResult(
            factor_id="default.tool_failure",
            factor_version="0.1.0",
            framework_id="agent_session_review.v0",
            stage=FactorStage.SIGNAL_EXTRACTION,
            target_type="session",
            target_id="ezs_001",
            session_id="ezs_001",
            tags=[{"type": "phrase", "value": "timeout"}, {"type": "tool", "value": "exec_command"}],
            evidence_refs=[{"event_id": "t1", "kind": "tool"}],
            verdict_signals=[Verdict.FIX_ENVIRONMENT.value],
            confidence=0.8,
        ),
        FactorResult(
            factor_id="default.open_loop",
            factor_version="0.1.0",
            framework_id="agent_session_review.v0",
            stage=FactorStage.SIGNAL_EXTRACTION,
            target_type="session",
            target_id="ezs_001",
            session_id="ezs_001",
            verdict_signals=[Verdict.OPEN_CASE.value],
            confidence=0.6,
        ),
    ]

    html_path = repository.write_factor_results_html(
        "ezs_001",
        results,
        packs,
        selected_factor_ids=["default.tool_failure"],
    )

    html = html_path.read_text(encoding="utf-8")
    assert html_path.name == "factor-results.html"
    assert "<!doctype html>" in html
    assert "cdn.jsdelivr.net/npm/antd@5/dist/reset.css" in html
    assert "cdn.jsdelivr.net/npm/dayjs@1/dayjs.min.js" in html
    assert "cdn.jsdelivr.net/npm/antd@5/dist/antd.min.js" in html
    assert 'id="evozeus-dashboard-root"' in html
    assert "window.__EVOZEUS_REPORT__" in html
    assert "const { App, Badge, Button, Card, Col, Drawer, Empty, Progress, Row, Space, Statistic, Table, Tabs, Tag, Tooltip, Typography } = antd;" in html
    assert 'data-workspace-tab="sessions"' in html
    assert 'data-workspace-tab="dashboards"' in html
    assert 'data-workspace-tab="factor_packs"' in html
    assert "Sessions" in html
    assert "Dashboards" in html
    assert "Factor Packs" in html
    assert 'data-component="workspace_coverage"' in html
    assert "session_conversation" in html
    assert "event_signal_rail" in html
    assert "event-signal-icon" in html
    assert "pending-event-result-hint" not in html
    assert "factor runs pending for this session" not in html
    assert "待分析" in html
    assert "待分析因子运行" in html
    assert "visibleEventsForSession" in html
    assert "dedupeVisibleEvents" in html
    assert "setDrawerResult" in html
    assert 'data-component="word_cloud"' in html
    assert 'data-result-card="factor_result"' in html
    assert "timeout" in html
    assert "default.tool_failure" in html
    assert "Fix Environment" in html
    assert '"result_count":1' in html
    assert 'data-component="evidence_list"' not in html


def test_html_report_renders_summary_statuses_and_formatted_scores():
    packs = FactorPackRepository(PACK_ROOT).discover()
    results = [
        FactorResult(
            factor_id="default.negative_feedback",
            factor_version="0.1.0",
            framework_id="agent_session_review.v0",
            stage=FactorStage.SIGNAL_EXTRACTION,
            target_type="session",
            target_id="ezs_001",
            session_id="ezs_001",
            scores={"negative_feedback": 0.3333333333333333},
            verdict_signals=[Verdict.PROMOTE_TO_SKILL.value],
            confidence=0.72,
        ),
        FactorResult(
            factor_id="default.repeated_user_requests",
            factor_version="0.1.0",
            framework_id="agent_session_review.v0",
            stage=FactorStage.SIGNAL_EXTRACTION,
            target_type="session",
            target_id="ezs_001",
            session_id="ezs_001",
            status="skipped",
            confidence=0.0,
        ),
    ]

    html = render_factor_results_html("ezs_001", results, packs)

    assert "Ant Design" in html
    assert 'data-component="result_summary"' in html
    assert 'data-status="matched"' in html
    assert 'data-status="skipped"' in html
    assert "Matched" in html
    assert "Skipped" in html
    assert "0.333" in html
    assert "0.3333333333333333" not in html


def test_html_report_exposes_sentence_level_factor_tags_as_event_signal_icons():
    packs = FactorPackRepository(PACK_ROOT).discover()
    status = SessionAnalysisStatus(
        session_id="session-tagged",
        provider="codex",
        source_ref="session-tagged.jsonl",
        event_count=1,
        discovered_at="2026-06-18T09:00:00Z",
        last_analyzed_at="2026-06-18T09:05:00Z",
        analyzed_factor_count=1,
        pending_factor_count=0,
    )
    event = SessionEventRecord(
        session_id="session-tagged",
        event_id="u1",
        event_index=1,
        role="user",
        content="这个具体句子需要被打上 open loop 标签",
        tool_name="",
        tool_result_preview="",
        source_ref="session-tagged.jsonl",
        source_line=7,
        tags=[
            SessionEventTag(
                factor_id="default.open_loop",
                tag_type="open_loop",
                tag_value="follow_up_required",
                reason="",
                result_run_id="frun_1",
                analysis_run_id="arun_1",
                last_run_at="2026-06-18T09:05:00Z",
            )
        ],
    )

    html = render_factor_results_html(
        "session-tagged",
        [],
        packs,
        session_statuses=[status],
        session_events=[event],
    )

    assert "EventSignalRail" in html
    assert '"factor_id":"default.open_loop"' in html
    assert '"value":"follow_up_required"' in html
    assert '"factor_name_zh":"未闭环"' in html
    assert '"factor_name_en":"Open Loop"' in html
    assert '"label_zh":"需要跟进"' in html
    assert '"label_en":"Follow-up required"' in html
    assert "未闭环 / Open Loop" in html
    assert "需要跟进 / Follow-up required" in html
    assert "event-signal-icon" in html
    assert "event-signal-count" in html


def test_html_report_exposes_session_folder_groups_for_sessions_tab():
    packs = FactorPackRepository(PACK_ROOT).discover()
    statuses = [
        SessionAnalysisStatus(
            session_id="session-new",
            provider="codex",
            source_ref="/Users/anthonyf/.codex/sessions/2026/06/18/rollout-new.jsonl",
            event_count=243,
            discovered_at="2026-06-18T09:00:00Z",
            last_analyzed_at="",
            analyzed_factor_count=0,
            pending_factor_count=8,
            session_title="最新 scanner 复盘",
            session_cwd="/Users/anthonyf/Documents/EvoZeus",
            session_group_key="/Users/anthonyf/Documents/EvoZeus",
            session_group_label="EvoZeus",
            session_updated_at="1781679600",
        ),
        SessionAnalysisStatus(
            session_id="session-old",
            provider="codex",
            source_ref="/Users/anthonyf/.codex/sessions/2026/06/17/rollout-old.jsonl",
            event_count=120,
            discovered_at="2026-06-17T08:00:00Z",
            last_analyzed_at="",
            analyzed_factor_count=0,
            pending_factor_count=8,
            session_title="较早 scanner 复盘",
            session_cwd="/Users/anthonyf/Documents/EvoZeus",
            session_group_key="/Users/anthonyf/Documents/EvoZeus",
            session_group_label="EvoZeus",
            session_updated_at="1781593200",
        ),
    ]

    html = render_factor_results_html("session-new", [], packs, session_statuses=statuses)

    assert "session_folder_groups" in html
    assert "buildSessionGroups" in html
    assert '"session_group_label":"EvoZeus"' in html
    assert '"session_title":"最新 scanner 复盘"' in html
    assert '"event_count":243' in html
    assert "待分析" in html
    assert "个因子待分析" in html
