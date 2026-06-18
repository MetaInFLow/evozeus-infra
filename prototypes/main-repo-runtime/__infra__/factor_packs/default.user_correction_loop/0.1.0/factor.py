from __future__ import annotations

from pathlib import Path

from evozeus.factors.base import Factor, FactorContext
from evozeus.factors.dashboard_signals import user_correction_loop_result
from evozeus.factors.manifest import load_manifest
from evozeus.factors.protocol import FactorResult


class UserCorrectionLoopFactor(Factor):
    def __init__(self) -> None:
        self.manifest = load_manifest(Path(__file__).with_name("factor.json"))

    def run(self, context: FactorContext) -> FactorResult:
        return user_correction_loop_result(
            context.session.session_id,
            context.session.events,
            version=self.manifest.version,
        )
