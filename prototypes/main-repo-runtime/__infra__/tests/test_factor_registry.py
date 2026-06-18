from evozeus.factors.base import Factor, FactorContext
from evozeus.factors.manifest import FactorManifest
from evozeus.factors.protocol import FactorResult, FactorStage, RuntimeProfile
from evozeus.factors.registry import FactorRegistry


class RegistryFactor(Factor):
    def __init__(self, factor_id: str, stage: FactorStage):
        self.manifest = FactorManifest(
            id=factor_id,
            name=factor_id,
            framework_id="agent_session_review.v0",
            stage=stage,
            runtime_profile=RuntimeProfile.DEFAULT,
            version="0.1.0",
            status="active",
            description="registry test factor",
            rollback="disable factor",
        )

    def run(self, context: FactorContext) -> FactorResult:
        raise AssertionError("registry test should not execute factors")


def test_factor_registry_selects_by_id_and_stage():
    signal_factor = RegistryFactor("test.signal", FactorStage.SIGNAL_EXTRACTION)
    verdict_factor = RegistryFactor("test.verdict", FactorStage.VERDICT_BUILDING)
    registry = FactorRegistry()
    registry.register(signal_factor)
    registry.register(verdict_factor)

    assert registry.get("test.signal") is signal_factor
    assert registry.by_stage(FactorStage.SIGNAL_EXTRACTION) == [signal_factor]
    assert registry.by_stage(FactorStage.VERDICT_BUILDING) == [verdict_factor]
