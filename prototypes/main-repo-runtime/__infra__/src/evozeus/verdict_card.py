from __future__ import annotations

from evozeus.models import SessionVerdictCard


def render_verdict_card(card: SessionVerdictCard) -> str:
    def bullets(items: list[str]) -> str:
        if not items:
            return "- None"
        return "\n".join(f"- {item}" for item in items)

    return "\n".join(
        [
            "## Session Verdict Card",
            "",
            "### Task context",
            card.task_context,
            "",
            "### Key evidence",
            bullets(card.key_evidence),
            "",
            "### Judgment signals",
            bullets(card.judgment_signals),
            "",
            "### Proposed verdict",
            card.proposed_verdict.value,
            "",
            "### Suggested next action",
            card.suggested_next_action,
            "",
            "### Privacy note",
            card.privacy_note,
            "",
            "### Optional next steps",
            bullets(card.optional_next_steps),
            "",
        ]
    )
