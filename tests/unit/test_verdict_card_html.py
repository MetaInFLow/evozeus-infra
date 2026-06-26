from evozeus_runtime.factors.protocol import FactorResult, FactorStage
from evozeus_runtime.reports.html import render_factor_results_html


def test_factor_results_html_renders_session_verdict_card_without_raw_private_context():
    html = render_factor_results_html(
        "session-feishu-cli",
        [
            FactorResult(
                factor_id="default.tool_failure",
                framework_id="agent_session_review.v0",
                stage=FactorStage.SIGNAL_EXTRACTION,
                target_type="session",
                target_id="session-feishu-cli",
                session_id="session-feishu-cli",
                tags=[{"type": "tool_failure", "value": "exec_command"}],
                evidence_refs=[{"ref_id": "event-001", "kind": "tool_event"}],
                verdict_signals=["Fix Environment"],
                notes=["raw_source=/Users/anthonyf/private/session.jsonl"],
                confidence=0.8,
            )
        ],
    )

    assert "Session Verdict Card" in html
    assert "Proposed Verdict" in html
    assert "Fix Environment" in html
    assert "Evidence" in html
    assert "event-001" in html
    assert "Judgment Signals" in html
    assert "tool_failure" in html
    assert "exec_command" in html
    assert "Artifact Route" in html
    assert "Environment Rule" in html
    assert "Privacy" in html
    assert "raw session stays local" in html
    assert "Next Action" in html
    assert "/Users/anthonyf/private/session.jsonl" not in html


def test_factor_results_html_defaults_to_open_case_when_evidence_is_missing():
    html = render_factor_results_html("session-empty", [])

    assert "Session Verdict Card" in html
    assert "Open Case" in html
    assert "No evidence refs found" in html
    assert "collect more evidence" in html
