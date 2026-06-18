from evozeus.factors.protocol import FactorResult, FactorStage
from evozeus.models import Verdict
from evozeus.reports.visualizations import build_result_visualizations


def test_word_cloud_visualization_uses_factor_result_outputs_as_input():
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
            tags=[{"type": "phrase", "value": "timeout"}],
            verdict_signals=[Verdict.OPEN_CASE.value],
            confidence=0.6,
        ),
    ]

    visualizations = build_result_visualizations(results)
    word_cloud = visualizations[0]

    assert word_cloud.component == "word_cloud"
    assert word_cloud.input_fields == ["tags.type", "tags.value", "verdict_signals", "factor_id"]
    timeout = next(term for term in word_cloud.terms if term.text == "timeout")
    assert timeout.weight == 2
    assert timeout.source_factor_ids == ["default.open_loop", "default.tool_failure"]
    assert any(term.text == "Fix Environment" for term in word_cloud.terms)
    assert not any(term.text.startswith("default.") for term in word_cloud.terms)
