import inspect
from pathlib import Path
from unittest.mock import patch

from evozeus_runtime.scanners.base import ScanRequest, SessionScanner
from evozeus_runtime.scanners.providers.codex import CodexScanner


def test_codex_scanner_implements_scanner_abstract_class():
    assert inspect.isabstract(SessionScanner)
    assert issubclass(CodexScanner, SessionScanner)


def test_codex_scanner_discovers_and_loads_fixture_sessions():
    scanner = CodexScanner()
    source = Path("tests/fixtures/codex_sessions")

    refs = scanner.discover(ScanRequest(provider="codex", source_dir=source))

    assert [ref.session_id for ref in refs] == ["session-minimal"]
    envelope = scanner.load(refs[0])
    assert envelope.provider == "codex"
    assert envelope.session_id == "session-minimal"
    assert envelope.events
    assert envelope.metadata["scanner_id"] == "codex"
    assert envelope.metadata["scanner_version"] == "0.1.0"
    assert envelope.events[0].metadata["event_locator_json"]["kind"] == "source_event"


def test_codex_scanner_discovers_session_meta_after_large_initial_record(tmp_path):
    source = tmp_path / "codex_sessions"
    source.mkdir()
    session_file = source / "rollout-oversized-prefix.jsonl"
    large_prefix = "x" * 150_000
    session_file.write_text(
        "\n".join(
            [
                '{"payload":{"base_instructions":{"text":"' + large_prefix + '"}}}',
                '{"type":"session_meta","payload":{"id":"embedded-session","cwd":"/tmp/project"}}',
                '{"type":"response_item","payload":{"type":"message","role":"user","content":[{"text":"run it"}]}}',
            ]
        ),
        encoding="utf-8",
    )
    scanner = CodexScanner()

    refs = scanner.discover(ScanRequest(provider="codex", source_dir=source))
    envelope = scanner.load(refs[0])

    assert refs[0].session_id == "embedded-session"
    assert envelope.session_id == "embedded-session"
    assert refs[0].metadata["session_cwd"] == "/tmp/project"


def test_codex_scanner_keeps_first_session_meta_when_rollout_contains_parent_meta(tmp_path):
    source = tmp_path / "codex_sessions"
    source.mkdir()
    session_file = source / "rollout-subagent.jsonl"
    session_file.write_text(
        "\n".join(
            [
                '{"type":"session_meta","payload":{"id":"subagent-session","cwd":"/tmp/subagent"}}',
                '{"type":"session_meta","payload":{"id":"parent-session","cwd":"/tmp/parent"}}',
                '{"type":"response_item","payload":{"type":"message","role":"user","content":[{"text":"run it"}]}}',
            ]
        ),
        encoding="utf-8",
    )
    scanner = CodexScanner()

    ref = scanner.discover(ScanRequest(provider="codex", source_dir=source))[0]
    envelope = scanner.load(ref)
    message_refs = scanner.discover_message_refs(ref)

    assert ref.session_id == "subagent-session"
    assert envelope.session_id == "subagent-session"
    assert [message_ref.session_id for message_ref in message_refs] == ["subagent-session"]
    assert envelope.events[0].metadata["event_locator_json"]["payload"]["session_id"] == "subagent-session"


def test_codex_scanner_loads_events_progressively_without_read_text():
    scanner = CodexScanner()
    source = Path("tests/fixtures/codex_sessions")
    ref = scanner.discover(ScanRequest(provider="codex", source_dir=source))[0]

    with patch.object(Path, "read_text", side_effect=AssertionError("load must stream lines")):
        event_iterator = scanner.iter_events(ref)
        assert inspect.isgenerator(event_iterator)
        assert next(event_iterator).event_id == "event_0002"
        envelope = scanner.load(ref)

    assert [event.event_id for event in envelope.events] == ["event_0002", "event_0003", "event_0004"]


def test_codex_scanner_discovers_message_ids_without_message_content():
    scanner = CodexScanner()
    source = Path("tests/fixtures/codex_sessions")
    session_ref = scanner.discover(ScanRequest(provider="codex", source_dir=source))[0]

    with patch.object(Path, "read_text", side_effect=AssertionError("message refs must stream lines")):
        message_refs = scanner.discover_message_refs(session_ref)

    assert [message_ref.message_id for message_ref in message_refs] == ["event_0002", "event_0004"]
    assert [message_ref.metadata["role"] for message_ref in message_refs] == ["user", "task_complete"]
    assert [message_ref.metadata["tool_name"] for message_ref in message_refs] == ["", ""]
    assert [message_ref.metadata["payload_type"] for message_ref in message_refs] == [
        "message",
        "task_complete",
    ]
    assert all("content_preview_redacted" not in message_ref.metadata for message_ref in message_refs)
    assert all("tool_result_preview_redacted" not in message_ref.metadata for message_ref in message_refs)


def test_codex_scanner_declares_default_local_session_dirs(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    scanner = CodexScanner()

    source_dirs = scanner.source_dirs(ScanRequest(provider="codex"))

    assert source_dirs == [
        tmp_path / ".codex" / "sessions",
        tmp_path / ".codex" / "archived_sessions",
    ]


def test_codex_scanner_skips_malformed_jsonl_lines(tmp_path):
    source = tmp_path / "codex_sessions"
    source.mkdir()
    session_file = source / "rollout-broken.jsonl"
    session_file.write_text(
        "\n".join(
            [
                '{"type":"session_meta","payload":{"id":"broken-session"}}',
                '{"type":"response_item","payload":{"type":"message","role":"user","content":[{"text":"truncated',
                '{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"text":"still readable"}]}}',
            ]
        ),
        encoding="utf-8",
    )
    scanner = CodexScanner()

    refs = scanner.discover(ScanRequest(provider="codex", source_dir=source))
    envelope = scanner.load(refs[0])

    assert envelope.session_id == "broken-session"
    assert [event.content for event in envelope.events] == ["still readable"]
    assert envelope.metadata["malformed_jsonl_line_count"] == "1"


def test_codex_scanner_normalizes_factor_channels_for_codex_noise(tmp_path):
    source = tmp_path / "codex_sessions"
    source.mkdir()
    session_file = source / "rollout-normalized.jsonl"
    session_file.write_text(
        "\n".join(
            [
                '{"type":"session_meta","payload":{"id":"normalized-session"}}',
                '{"type":"response_item","payload":{"type":"message","role":"user","content":[{"text":"# AGENTS.md instructions\\n<INSTRUCTIONS>中文输出</INSTRUCTIONS>"}]}}',
                '{"type":"response_item","payload":{"type":"message","role":"user","content":[{"text":"# Files mentioned by the user:\\n\\n## My request for Codex:\\n检查下为什么失败了"}]}}',
                '{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"text":"我会检查日志。"}]}}',
                '{"type":"response_item","payload":{"type":"function_call","name":"exec_command","arguments":"{\\"cmd\\":\\"pytest\\"}"}}',
                '{"type":"response_item","payload":{"type":"function_call_output","name":"exec_command","output":"{\\"exit_code\\":1,\\"stderr\\":\\"failed\\"}"}}',
                '{"type":"event_msg","payload":{"type":"task_complete","duration_ms":42}}',
            ]
        ),
        encoding="utf-8",
    )
    scanner = CodexScanner()

    ref = scanner.discover(ScanRequest(provider="codex", source_dir=source))[0]
    envelope = scanner.load(ref)

    channels = [(event.role, event.metadata["content_kind"], event.metadata["factor_channel"]) for event in envelope.events]
    assert channels == [
        ("user", "codex_context", "context"),
        ("user", "real_user_message", "user_input"),
        ("assistant", "assistant_message", "assistant_result"),
        ("tool", "tool_call", "tool_usage"),
        ("tool", "tool_output", "tool_result"),
        ("task_complete", "task_complete", "assistant_result"),
    ]
    assert envelope.events[0].metadata["chat_role"] == "context"
    assert envelope.events[1].metadata["raw_role"] == "user"
    assert envelope.events[1].metadata["chat_role"] == "user"
    assert envelope.events[1].metadata["factor_text_preview"] == "检查下为什么失败了"
