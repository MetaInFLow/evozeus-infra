from evozeus.core.session import SessionEnvelope
from evozeus.factors.base import Factor, FactorContext
from evozeus.factors.manifest import FactorManifest
from evozeus.factors.protocol import FactorResult, FactorStage, RuntimeProfile
from evozeus.factors.runner import FactorRunner
from evozeus.models import SessionEvent, Verdict


class OrderedFactor(Factor):
    def __init__(self, factor_id: str, calls: list[str]):
        self.manifest = FactorManifest(
            id=factor_id,
            name=factor_id,
            framework_id="agent_session_review.v0",
            stage=FactorStage.SIGNAL_EXTRACTION,
            runtime_profile=RuntimeProfile.DEFAULT,
            version="0.1.0",
            status="active",
            description="records execution order",
            rollback="disable factor",
        )
        self.calls = calls

    def run(self, context: FactorContext) -> FactorResult:
        self.calls.append(self.manifest.id)
        return FactorResult(
            factor_id=self.manifest.id,
            factor_version=self.manifest.version,
            framework_id=self.manifest.framework_id,
            stage=self.manifest.stage,
            target_type="session",
            target_id=context.session.session_id,
            session_id=context.session.session_id,
            verdict_signals=[Verdict.PRESERVE.value],
            confidence=0.5,
        )


class BrokenFactor(OrderedFactor):
    def run(self, context: FactorContext) -> FactorResult:
        raise RuntimeError("boom")


def test_factor_runner_runs_serially_and_isolates_errors():
    calls: list[str] = []
    context = FactorContext(
        session=SessionEnvelope(
            session_id="ezs_001",
            provider="codex",
            source_ref="memory",
            events=[SessionEvent(event_id="u1", role="user", content="hello")],
        )
    )

    summary = FactorRunner(
        [
            OrderedFactor("test.first", calls),
            BrokenFactor("test.broken", calls),
            OrderedFactor("test.second", calls),
        ]
    ).run(context)

    assert calls == ["test.first", "test.second"]
    assert [result.factor_id for result in summary.results] == ["test.first", "test.second"]
    assert summary.errors[0].factor_id == "test.broken"
    assert summary.errors[0].error_type == "RuntimeError"
