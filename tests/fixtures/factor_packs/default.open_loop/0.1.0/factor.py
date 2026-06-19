from __future__ import annotations

from pathlib import Path

from evozeus_runtime.factors.base import Factor, FactorContext
from evozeus_runtime.factors.dashboard_signals import open_loop_result
from evozeus_runtime.factors.manifest import load_manifest
from evozeus_runtime.factors.protocol import FactorResult


class OpenLoopFactor(Factor):
    def __init__(self) -> None:
        self.manifest = load_manifest(Path(__file__).with_name("factor.json"))

    def run(self, context: FactorContext) -> FactorResult:
        return open_loop_result(
            context.session.session_id,
            context.session.events,
            version=self.manifest.version,
        )
