from pathlib import Path

from evozeus.core.session import SessionEnvelope
from evozeus.factors.base import FactorContext
from evozeus.factors.packs import FactorPackRepository
from evozeus.factors.runner import FactorRunner
from evozeus.models import SessionEvent


PACK_ROOT = Path(__file__).resolve().parents[2] / "__infra__" / "factor_packs"


def test_dashboard_signal_factor_packs_are_available():
    ids = {pack.manifest.id for pack in FactorPackRepository(PACK_ROOT).discover()}

    assert {
        "default.task_span_extraction",
        "default.open_loop",
        "default.user_correction_loop",
        "default.repeated_user_requests",
        "default.success_closure_quality",
    } <= ids


def test_task_span_extraction_factor_outputs_task_span_tags():
    result = _run_factor("default.task_span_extraction", _session_with_rework_and_open_loop())

    assert result.status == "matched"
    assert {"type": "task_span", "value": "debug"} in result.tags
    assert result.scores["task_span_count"] >= 1
    assert result.evidence_refs[0]["kind"] == "user_turn"


def test_open_loop_factor_detects_unclosed_follow_up():
    result = _run_factor("default.open_loop", _session_with_rework_and_open_loop())

    assert result.status == "matched"
    assert {"type": "open_loop", "value": "follow_up_required"} in result.tags
    assert result.scores["open_loop_count"] >= 1


def test_user_correction_loop_factor_detects_multiple_corrections():
    result = _run_factor("default.user_correction_loop", _session_with_rework_and_open_loop())

    assert result.status == "matched"
    assert {"type": "correction_loop", "value": "user_correction_loop"} in result.tags
    assert result.scores["correction_count"] >= 2


def test_repeated_user_requests_factor_detects_repeated_target():
    result = _run_factor("default.repeated_user_requests", _session_with_rework_and_open_loop())

    assert result.status == "matched"
    assert {"type": "repeated_request", "value": "same_target"} in result.tags
    assert result.scores["repeated_request_count"] >= 1


def test_success_closure_quality_factor_scores_unresolved_closure():
    result = _run_factor("default.success_closure_quality", _session_with_rework_and_open_loop())

    assert result.status == "matched"
    assert {"type": "success_factor", "value": "closure_quality:watch"} in result.tags
    assert 0 < result.scores["closure_quality"] < 0.7


def _run_factor(factor_id: str, session: SessionEnvelope):
    repository = FactorPackRepository(PACK_ROOT)
    factor = repository.load(factor_id)
    summary = FactorRunner([factor]).run(FactorContext(session=session))

    assert not summary.errors
    assert summary.results
    return summary.results[0]


def _session_with_rework_and_open_loop() -> SessionEnvelope:
    return SessionEnvelope(
        session_id="session-dashboard-factors",
        provider="codex",
        source_ref="memory",
        events=[
            SessionEvent(event_id="u1", role="user", content="请修复 dashboard 的数据加载 bug，必须保留现有结构"),
            SessionEvent(event_id="a1", role="assistant", content="我会先定位问题。"),
            SessionEvent(event_id="u2", role="user", content="不对，继续修复 dashboard 数据加载，刚才没改到根因"),
            SessionEvent(event_id="a2", role="assistant", content="我会继续调整。"),
            SessionEvent(event_id="u3", role="user", content="还是不行，后续还需要确认 dashboard 数据加载是否闭环"),
            SessionEvent(
                event_id="t1",
                role="tool",
                tool_name="exec_command",
                tool_result={"stderr": "failed with timeout"},
            ),
            SessionEvent(event_id="a3", role="assistant", content="当前仍 blocked，后续需要确认。"),
        ],
    )
