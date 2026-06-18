from __future__ import annotations

from evozeus.factors.base import Factor, FactorContext
from evozeus.factors.defaults import (
    FRAMEWORK_ID,
    _negative_feedback_result,
    _same_target_rework_result,
    _tool_failure_result,
)
from evozeus.factors.manifest import FactorManifest
from evozeus.factors.protocol import FactorResult, FactorStage, RuntimeProfile


class BuiltinDefaultFactor(Factor):
    factor_id: str
    factor_name: str

    def __init__(self) -> None:
        self.manifest = FactorManifest(
            id=self.factor_id,
            name=self.factor_name,
            framework_id=FRAMEWORK_ID,
            stage=FactorStage.SIGNAL_EXTRACTION,
            runtime_profile=RuntimeProfile.DEFAULT,
            default_enabled=True,
            version="0.1.0",
            status="active",
            description=f"Built-in factor: {self.factor_name}",
            permissions=["read_session_events"],
            rollback="disable built-in factor in local config",
        )

    def skipped_result(self, context: FactorContext) -> FactorResult:
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


class NegativeFeedbackFactor(BuiltinDefaultFactor):
    factor_id = "default.negative_feedback"
    factor_name = "negative-feedback"

    def run(self, context: FactorContext) -> FactorResult:
        return _negative_feedback_result(context.session.session_id, context.session.events) or self.skipped_result(context)


class SameTargetReworkFactor(BuiltinDefaultFactor):
    factor_id = "default.same_target_rework"
    factor_name = "same-target-rework"

    def run(self, context: FactorContext) -> FactorResult:
        return _same_target_rework_result(context.session.session_id, context.session.events) or self.skipped_result(context)


class ToolFailureFactor(BuiltinDefaultFactor):
    factor_id = "default.tool_failure"
    factor_name = "tool-failure"

    def run(self, context: FactorContext) -> FactorResult:
        return _tool_failure_result(context.session.session_id, context.session.events) or self.skipped_result(context)


def builtin_factors() -> list[Factor]:
    return [
        NegativeFeedbackFactor(),
        SameTargetReworkFactor(),
        ToolFailureFactor(),
    ]
