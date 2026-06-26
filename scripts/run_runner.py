#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _add_src_to_path() -> None:
    sys.path.insert(0, str(_repo_root() / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EvoZeus selected factors for one scanned session.")
    parser.add_argument("--session-id", required=True, help="Session id already recorded in the local ledger.")
    parser.add_argument(
        "--factor",
        action="append",
        required=True,
        dest="factors",
        help="Factor id to run. Can be provided more than once.",
    )
    parser.add_argument("--pack-root", required=True, type=Path, help="Local FactorPack root.")
    parser.add_argument(
        "--workspace",
        default=Path.home(),
        type=Path,
        help="Workspace root for .evozeus state. Defaults to the user's home directory.",
    )
    args = parser.parse_args()

    _add_src_to_path()
    from evozeus_runtime.use_cases.run_factors import run_factors

    result = run_factors(
        workspace_root=args.workspace,
        session_id=args.session_id,
        factor_ids=args.factors,
        pack_root=args.pack_root,
    )
    print(f"results={result.result_count}")
    print(f"errors={result.error_count}")
    print(f"analysis_run_id={result.analysis_run_id}")
    print(f"ledger={result.ledger_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
