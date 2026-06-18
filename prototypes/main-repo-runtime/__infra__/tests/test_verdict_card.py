from evozeus.models import SessionVerdictCard, Verdict
from evozeus.verdict_card import render_verdict_card


def test_render_verdict_card_contains_required_sections():
    card = SessionVerdictCard(
        task_context="Agent debugged a failing git push.",
        key_evidence=["gh auth succeeded", "push timed out"],
        judgment_signals=["network failure"],
        proposed_verdict=Verdict.FIX_ENVIRONMENT,
        suggested_next_action="Check network and retry later.",
        privacy_note="No raw private session included.",
        optional_next_steps=["Save local draft", "Ignore"],
    )

    rendered = render_verdict_card(card)

    assert "## Session Verdict Card" in rendered
    assert "### Proposed verdict" in rendered
    assert "Fix Environment" in rendered
    assert "Save local draft" in rendered
