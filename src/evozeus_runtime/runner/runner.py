from __future__ import annotations

from collections.abc import Callable
from time import perf_counter

from pydantic import BaseModel, Field

from evozeus_runtime.factors.base import Factor, FactorContext
from evozeus_runtime.factors.packs import FactorPack
from evozeus_runtime.factors.protocol import FactorResult
from evozeus_runtime.runner.runtime import RuntimeResolver


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

    def run(self, context: FactorContext, *, progress: Callable[[str], None] | None = None) -> FactorRunSummary:
        summary = FactorRunSummary()
        total = len(self.factors)
        for index, factor in enumerate(self.factors, start=1):
            factor_id = factor.manifest.id
            if progress is not None:
                progress(f"factor_start index={index}/{total} factor_id={factor_id}")
            started_at = perf_counter()
            try:
                result = self._run_one(factor, context)
            except Exception as exc:
                elapsed = perf_counter() - started_at
                summary.errors.append(
                    FactorRunError(
                        factor_id=factor_id,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
                if progress is not None:
                    progress(
                        f"factor_error index={index}/{total} factor_id={factor_id} "
                        f"error_type={type(exc).__name__} elapsed={elapsed:.2f}s"
                    )
                continue
            summary.results.append(result)
            if progress is not None:
                elapsed = perf_counter() - started_at
                progress(
                    f"factor_done index={index}/{total} factor_id={factor_id} "
                    f"status={result.status} elapsed={elapsed:.2f}s"
                )
        return summary

    def _run_one(self, factor: Factor | FactorPack, context: FactorContext) -> FactorResult:
        if isinstance(factor, FactorPack):
            return self.runtime_resolver.run(factor, context)
        return factor.execute(context)
