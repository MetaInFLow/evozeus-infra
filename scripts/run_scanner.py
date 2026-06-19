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
    parser = argparse.ArgumentParser(description="Run EvoZeus local session scanner.")
    parser.add_argument("--provider", default="codex", help="Session provider scanner to run.")
    parser.add_argument("--source", type=Path, help="Local session source directory. Defaults to provider local dirs.")
    parser.add_argument(
        "--workspace",
        default=Path("."),
        type=Path,
        help="Workspace root for .evozeus state. Defaults to the current working directory.",
    )
    args = parser.parse_args()

    _add_src_to_path()
    from evozeus_runtime.use_cases.scan_sessions import scan_sessions

    result = scan_sessions(
        workspace_root=args.workspace,
        provider=args.provider,
        source_dir=args.source,
    )
    print(f"scanned_sessions={result.session_count}")
    print(f"ledger={result.ledger_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
