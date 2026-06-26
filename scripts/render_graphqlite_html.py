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
    parser = argparse.ArgumentParser(description="Render EvoZeus GraphQLite ledger as a static local browser.")
    parser.add_argument(
        "--workspace",
        default=Path.home(),
        type=Path,
        help="Workspace root for .evozeus state. Defaults to the user's home directory.",
    )
    parser.add_argument("--graph", type=Path, help="GraphQLite ledger path. Defaults to results.graph.sqlite3.")
    parser.add_argument("--legacy", type=Path, help="Legacy SQLite ledger path. Defaults to results.sqlite3.")
    parser.add_argument("--output", type=Path, help="HTML output path. Defaults to .evozeus/runtime/reports/evozeus-graph.html.")
    args = parser.parse_args()

    _add_src_to_path()
    from evozeus_runtime.use_cases.generate_graph_ledger_browser import generate_graph_ledger_browser

    result = generate_graph_ledger_browser(
        workspace_root=args.workspace,
        graph_path=args.graph,
        legacy_path=args.legacy,
        output_path=args.output,
    )
    print(f"html={result.html_path}")
    print(f"graph={result.graph_path}")
    print(f"legacy={result.legacy_path}")
    print(f"graph_size={result.graph_size_bytes}")
    print(f"legacy_size={result.legacy_size_bytes}")
    print(f"nodes={result.node_count}")
    print(f"edges={result.edge_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
