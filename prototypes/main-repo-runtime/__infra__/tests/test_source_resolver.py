import json
from pathlib import Path

from evozeus.scanners.base import ScanRequest
from evozeus.scanners.providers.codex import CodexScanner, CodexSourceResolver
from evozeus.scanners.resolver import EventLocator


def test_codex_source_resolver_reads_original_event_from_locator(tmp_path: Path):
    session_path = tmp_path / "session-a.jsonl"
    session_path.write_text(
        json.dumps({"id": "u1", "role": "user", "content": "请修复测试"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    scanner = CodexScanner()
    ref = scanner.discover(ScanRequest(provider="codex", source_dir=tmp_path))[0]
    envelope = scanner.load(ref)
    event = envelope.events[0]
    locator = EventLocator.model_validate(event.metadata["event_locator_json"])

    resolver = CodexSourceResolver()
    resolved = resolver.resolve_event(locator)

    assert resolved.scanner_id == "codex"
    assert resolved.scanner_version == "0.1.0"
    assert resolved.session_id == "session-a"
    assert resolved.event_id == "u1"
    assert resolved.source_ref == str(session_path)
    assert resolved.content == "请修复测试"
    assert resolver.verify_hash(resolved, event.metadata["content_hash"]) is True
