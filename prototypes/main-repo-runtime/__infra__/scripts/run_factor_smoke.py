from __future__ import annotations

import argparse
from pathlib import Path

from evozeus.factors.base import FactorContext
from evozeus.factors.packs import FactorPackRepository
from evozeus.factors.runner import FactorRunner
from evozeus.scanners.base import ScanRequest
from evozeus.scanners.providers.codex import CodexScanner
from smoke_support import sample_session


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("factor_id", nargs="?", default="default.tool_failure")
    parser.add_argument("--pack-root", default=str(PROJECT_ROOT / "__infra__" / "factor_packs"))
    parser.add_argument("--source", default="")
    args = parser.parse_args()

    factor = FactorPackRepository(Path(args.pack_root)).load(args.factor_id)
    session = _load_session(Path(args.source)) if args.source else sample_session()
    summary = FactorRunner([factor]).run(FactorContext(session=session))
    assert not summary.errors, summary.errors
    assert summary.results, "expected a factor result"
    result = summary.results[0]
    assert result.status == "matched"
    verdict = result.verdict_signals[0] if result.verdict_signals else "None"
    print(f"run factor ok: factor_id={result.factor_id} status={result.status} verdict={verdict}")


def _load_session(source_dir: Path):
    scanner = CodexScanner()
    refs = scanner.discover(ScanRequest(provider="codex", source_dir=source_dir))
    assert refs, f"no sessions found in {source_dir}"
    return scanner.load(refs[0])


if __name__ == "__main__":
    main()
