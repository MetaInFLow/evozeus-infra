from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from evozeus.core.session import SessionEnvelope
from evozeus.factors.manifest import FactorManifest
from evozeus.factors.protocol import FactorResult


class FactorContext(BaseModel):
    session: SessionEnvelope
    config: dict[str, str] = Field(default_factory=dict)


class Factor(ABC):
    manifest: FactorManifest

    def execute(self, context: FactorContext) -> FactorResult:
        result = self.run(context)
        return result.model_copy(
            update={
                "factor_id": result.factor_id or self.manifest.id,
                "factor_version": result.factor_version or self.manifest.version,
                "session_id": result.session_id or context.session.session_id,
            }
        )

    @abstractmethod
    def run(self, context: FactorContext) -> FactorResult:
        raise NotImplementedError
