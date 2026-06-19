from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from evozeus_runtime.factors.base import FactorContext
from evozeus_runtime.factors.packs import FactorPackRepository
from evozeus_runtime.ledger.paths import RuntimePaths
from evozeus_runtime.ledger.repository import LedgerRepository
from evozeus_runtime.policy.permissions import PermissionDeclaration, PermissionGate
from evozeus_runtime.runner.runner import FactorRunner
from evozeus_runtime.scanners.builtins import create_default_scanner_registry


@dataclass(frozen=True)
class RunFactorsResult:
    result_count: int
    error_count: int
    analysis_run_id: str
    ledger_path: Path


def run_factors(
    *,
    workspace_root: Path,
    session_id: str,
    factor_ids: list[str],
    pack_root: Path,
) -> RunFactorsResult:
    decision = PermissionGate().approve(PermissionDeclaration(files_read=[pack_root]))
    if not decision.ok:
        raise PermissionError(decision.reason)

    paths = RuntimePaths.for_workspace(workspace_root).ensure()
    ledger = LedgerRepository(paths)
    ref = ledger.get_session_ref(session_id)
    session = create_default_scanner_registry().load(ref)

    repository = FactorPackRepository(pack_root)
    packs = [repository.get(factor_id) for factor_id in factor_ids]
    ledger.record_installed_factors(packs, source="local-fixture")
    ledger.record_default_routes(packs)
    summary = FactorRunner(packs).run(FactorContext(session=session))
    analysis_run_id = ledger.record_factor_run(
        session,
        summary.results,
        factor_ids=factor_ids,
        errors=summary.errors,
    )
    return RunFactorsResult(
        result_count=len(summary.results),
        error_count=len(summary.errors),
        analysis_run_id=analysis_run_id,
        ledger_path=paths.result_index_db,
    )
