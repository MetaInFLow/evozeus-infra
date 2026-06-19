from __future__ import annotations

from evozeus_runtime.factors.protocol import FactorResult


def render_factor_results_json(session_id: str, results: list[FactorResult]) -> dict[str, object]:
    return {
        "session_id": session_id,
        "results": [result.model_dump(mode="json") for result in results],
    }

