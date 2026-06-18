from __future__ import annotations

from pydantic import BaseModel, Field

from evozeus.factors.base import Factor, FactorContext
from evozeus.factors.packs import FactorPack
from evozeus.factors.protocol import FactorResult
from evozeus.factors.runtime import RuntimeResolver


class FactorRunError(BaseModel):
    factor_id: str
    error_type: str
    message: str


class FactorRunSummary(BaseModel):
    results: list[FactorResult] = Field(default_factory=list)
    errors: list[FactorRunError] = Field(default_factory=list)


class FactorRunner:
    def __init__(self, factors: list[Factor | FactorPack], runtime_resolver: RuntimeResolver | None = None):
        self.factors = factors
        self.runtime_resolver = runtime_resolver or RuntimeResolver()

    def run(self, context: FactorContext) -> FactorRunSummary:
        summary = FactorRunSummary()
        for factor in self.factors:
            try:
                result = self._run_one(factor, context)
            except Exception as exc:
                summary.errors.append(
                    FactorRunError(
                        factor_id=factor.manifest.id,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
                continue
            summary.results.append(result)
        return summary

    def _run_one(self, factor: Factor | FactorPack, context: FactorContext) -> FactorResult:
        if isinstance(factor, FactorPack):
            return self.runtime_resolver.run(factor, context)
        return factor.execute(context)
