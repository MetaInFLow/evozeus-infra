from __future__ import annotations

import argparse
from pathlib import Path

from evozeus.scanners.base import ScanRequest
from evozeus.scanners.providers.codex import CodexScanner


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="")
    parser.add_argument("--min-sessions", type=int, default=2)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    if args.source:
        _scan(Path(args.source), args.min_sessions, args.limit or None)
        return

    _scan(None, args.min_sessions, args.limit or None)


def _scan(source_dir: Path | None, min_sessions: int, limit: int | None) -> None:
    scanner = CodexScanner()
    refs = scanner.discover(ScanRequest(provider="codex", source_dir=source_dir, limit=limit))
    assert len(refs) >= min_sessions, f"expected at least {min_sessions} scanned sessions, got {len(refs)}"
    envelopes = [scanner.load(ref) for ref in refs]
    total_events = sum(len(envelope.events) for envelope in envelopes)
    has_tool_result = any(event.tool_result for envelope in envelopes for event in envelope.events)
    assert total_events >= len(refs)
    assert all(envelope.session_id and envelope.provider == "codex" and envelope.source_ref for envelope in envelopes)
    assert has_tool_result
    print(f"scan sessions ok: sessions={len(refs)} total_events={total_events} has_tool_result={has_tool_result}")


if __name__ == "__main__":
    main()
