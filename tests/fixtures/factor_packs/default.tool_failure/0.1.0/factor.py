from __future__ import annotations

from pathlib import Path

from evozeus_runtime.factors.base import Factor, FactorContext
from evozeus_runtime.factors.defaults import _tool_failure_result
from evozeus_runtime.factors.manifest import load_manifest
from evozeus_runtime.factors.protocol import FactorResult


class ToolFailureFactor(Factor):
    def __init__(self) -> None:
        self.manifest = load_manifest(Path(__file__).with_name("factor.json"))

    def run(self, context: FactorContext) -> FactorResult:
        result = _tool_failure_result(context.session.session_id, context.session.events)
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
