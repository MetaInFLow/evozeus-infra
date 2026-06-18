from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from evozeus.scanners.providers.codex import CodexSourceResolver
from evozeus.scanners.resolver import EventLocator


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a Codex event locator to local source content.")
    parser.add_argument("--workspace", default=".", help="Repository or runtime workspace root.")
    parser.add_argument("--session-id", default="", help="Session id in SQLite.")
    parser.add_argument("--event-id", default="", help="Event id in SQLite.")
    parser.add_argument("--locator-json", default="", help="Raw event locator JSON.")
    args = parser.parse_args()

    locator_data, expected_hash = _load_locator(args)
    resolver = CodexSourceResolver()
    try:
        resolved = resolver.resolve_event(EventLocator.model_validate(locator_data))
    except FileNotFoundError:
        print("error: source_missing")
        return 2
    except PermissionError:
        print("error: permission_denied")
        return 2
    except ValueError as exc:
        print(f"error: unsupported_locator {exc}")
        return 2

    hash_verified = resolver.verify_hash(resolved, expected_hash) if expected_hash else True
    print(f"scanner_id: {resolved.scanner_id}")
    print(f"scanner_version: {resolved.scanner_version}")
    print(f"session_id: {resolved.session_id}")
    print(f"event_id: {resolved.event_id}")
    print(f"source_ref: {resolved.source_ref}")
    print(f"content_hash: {resolved.content_hash}")
    print(f"hash_verified: {str(hash_verified).lower()}")
    print(f"preview: {resolved.content[:160]}")
    return 0 if hash_verified else 3


def _load_locator(args: argparse.Namespace) -> tuple[dict, str]:
    if args.locator_json:
        return json.loads(args.locator_json), ""
    if not args.session_id or not args.event_id:
        raise SystemExit("--session-id and --event-id are required when --locator-json is absent")

    db_path = Path(args.workspace) / ".evozeus" / "runtime" / "index" / "results.sqlite3"
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT event_locator_json, content_hash
            FROM session_events
            WHERE session_id = ? AND event_id = ?
            """,
            (args.session_id, args.event_id),
        ).fetchone()
    if row is None:
        raise SystemExit("event locator not found")
    return json.loads(row[0]), str(row[1] or "")


if __name__ == "__main__":
    raise SystemExit(main())
