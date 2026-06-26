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
    parser = argparse.ArgumentParser(description="Migrate EvoZeus legacy SQLite ledger to GraphQLite graph ledger.")
    parser.add_argument(
        "--workspace",
        default=Path.home(),
        type=Path,
        help="Workspace root for .evozeus state. Defaults to the user's home directory.",
    )
    parser.add_argument("--legacy-db", type=Path, help="Legacy SQLite ledger path. Defaults to workspace results.sqlite3.")
    parser.add_argument("--output", type=Path, help="Graph ledger output path. Defaults to results.graph.sqlite3.")
    parser.add_argument("--no-backup", action="store_true", help="Do not copy results.sqlite3 to results.sqlite3.legacy.")
    parser.add_argument(
        "--sqlite-test-backend",
        action="store_true",
        help="Use the local SQLite graph test backend instead of GraphQLite. For tests only.",
    )
    args = parser.parse_args()

    _add_src_to_path()
    from evozeus_runtime.ledger.graph_repository import GraphQLiteNotInstalledError
    from evozeus_runtime.ledger.migrate_sqlite_to_graphqlite import migrate_workspace_sqlite_to_graphqlite

    backend = "sqlite" if args.sqlite_test_backend else "graphqlite"
    try:
        result = migrate_workspace_sqlite_to_graphqlite(
            workspace_root=args.workspace,
            legacy_db_path=args.legacy_db,
            output_db_path=args.output,
            backup=not args.no_backup,
            backend=backend,
        )
    except GraphQLiteNotInstalledError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"migration_id={result.migration_id}")
    print(f"legacy={result.legacy_db_path}")
    print(f"graph={result.output_db_path}")
    if result.backup_db_path is not None:
        print(f"backup={result.backup_db_path}")
    for check in result.checks:
        status = "ok" if check.ok else "failed"
        print(f"check={check.name} legacy={check.legacy_count} graph={check.graph_count} op={check.operator} status={status}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
