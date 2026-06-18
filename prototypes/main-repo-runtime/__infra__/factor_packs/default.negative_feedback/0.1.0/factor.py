from __future__ import annotations

from pathlib import Path

from evozeus.factors.base import Factor, FactorContext
from evozeus.factors.defaults import _negative_feedback_result
from evozeus.factors.manifest import load_manifest
from evozeus.factors.protocol import FactorResult


class NegativeFeedbackFactor(Factor):
    def __init__(self) -> None:
        self.manifest = load_manifest(Path(__file__).with_name("factor.json"))

    def run(self, context: FactorContext) -> FactorResult:
        result = _negative_feedback_result(context.session.session_id, context.session.events)
        if result is not None:
            return result.model_copy(update={"factor_version": self.manifest.version})
        return FactorResult(
            factor_id=self.manifest.id,
            factor_version=self.manifest.version,
            framework_id=self.manifest.framework_id,
            stage=self.manifest.stage,
            target_type="session",
            target_id=context.session.session_id,
            session_id=context.session.session_id,
            status="skipped",
            confidence=0.0,
        )
