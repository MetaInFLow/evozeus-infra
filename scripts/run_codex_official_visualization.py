#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _cluster_root() -> Path:
    return _repo_root().parents[1]


def _add_src_to_path() -> None:
    sys.path.insert(0, str(_repo_root() / "src"))


SLOW_FACTOR_RE = re.compile(r"\bfactor_done\b.*\belapsed=([0-9.]+)s")
SESSION_DONE_RE = re.compile(r"\bsession_done index=(\d+)/(\d+)\b.*\belapsed=([0-9.]+)s")


def _print_progress(message: str, *, verbose_factors: bool = False) -> None:
    if not _should_print_progress(message, verbose_factors=verbose_factors):
        return
    print(f"[codex-official] {message}", file=sys.stderr, flush=True)


def _should_print_progress(message: str, *, verbose_factors: bool) -> bool:
    if verbose_factors:
        return True
    if "factor_error" in message:
        return True
    if "session_start" in message:
        return False
    session_done = SESSION_DONE_RE.search(message)
    if session_done is not None:
        index = int(session_done.group(1))
        total = int(session_done.group(2))
        elapsed = float(session_done.group(3))
        return index == total or index % 100 == 0 or elapsed >= 2.0
    if "factor_start" in message:
        return False
    slow_factor = SLOW_FACTOR_RE.search(message)
    if slow_factor is not None:
        return float(slow_factor.group(1)) >= 2.0
    return "factor_done" not in message


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run official session-quality factors over local Codex sessions and render HTML."
    )
    parser.add_argument(
        "--workspace",
        default=Path.home(),
        type=Path,
        help="Workspace root for .evozeus state.",
    )
    parser.add_argument(
        "--official-repo-root",
        default=_cluster_root() / "10-repos" / "evozeus-session-signal-skill",
        type=Path,
        help="Path to evozeus-session-signal-skill.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="HTML output path. Defaults to workspace .evozeus/runtime/reports/codex-factor-visualization.html.",
    )
    parser.add_argument("--force", action="store_true", help="Run factors even when previous latest results are fresh.")
    parser.add_argument(
        "--no-skip-fresh",
        action="store_true",
        help="Disable skip-fresh decisions without forcing the final run status text.",
    )
    parser.add_argument(
        "--verbose-factors",
        action="store_true",
        help="Print every factor start/done progress event.",
    )
    args = parser.parse_args()

    _add_src_to_path()
    from evozeus_runtime.use_cases.run_codex_official_visualization import run_codex_official_visualization

    result = run_codex_official_visualization(
        workspace_root=args.workspace,
        official_repo_root=args.official_repo_root,
        force=args.force,
        skip_fresh=not args.no_skip_fresh,
        output_path=args.output,
        progress=lambda message: _print_progress(message, verbose_factors=args.verbose_factors),
    )
    print(f"sessions={result.session_count}")
    print(f"factors={result.factor_count}")
    print(f"ran={result.ran_count}")
    print(f"skipped={result.skipped_count}")
    print(f"errors={result.error_count}")
    print(f"db_size_bytes={result.db_size_bytes}")
    print(f"ledger={result.ledger_path}")
    print(f"html={result.html_path}")
    return 0 if result.error_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
