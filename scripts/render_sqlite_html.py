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
    parser = argparse.ArgumentParser(description="Render EvoZeus SQLite ledger as a static HTML visualizer.")
    parser.add_argument(
        "--workspace",
        default=Path.home(),
        type=Path,
        help="Workspace root for .evozeus state. Defaults to the user's home directory.",
    )
    parser.add_argument("--output", type=Path, help="HTML output path. Defaults to .evozeus/runtime/reports/evozeus-sqlite.html.")
    args = parser.parse_args()

    _add_src_to_path()
    from evozeus_runtime.use_cases.generate_ledger_browser import generate_ledger_browser

    result = generate_ledger_browser(
        workspace_root=args.workspace,
        output_path=args.output,
    )
    print(f"html={result.html_path}")
    print(f"ledger={result.ledger_path}")
    print(f"providers={result.provider_count}")
    print(f"projects={result.project_count}")
    print(f"sessions={result.session_count}")
    print(f"messages={result.event_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
