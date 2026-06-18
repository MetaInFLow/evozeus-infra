from __future__ import annotations

from evozeus.factors.base import Factor
from evozeus.factors.protocol import FactorStage


class FactorRegistry:
    def __init__(self) -> None:
        self._factors: dict[str, Factor] = {}

    def register(self, factor: Factor) -> None:
        self._factors[factor.manifest.id] = factor

    def get(self, factor_id: str) -> Factor:
        try:
            return self._factors[factor_id]
        except KeyError as exc:
            raise KeyError(f"unknown factor: {factor_id}") from exc

    def by_stage(self, stage: FactorStage) -> list[Factor]:
        return [factor for factor in self._factors.values() if factor.manifest.stage == stage]
