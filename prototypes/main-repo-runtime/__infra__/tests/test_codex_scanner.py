import json
from pathlib import Path

from evozeus.scanners.base import ScanRequest
from evozeus.scanners.providers.codex import CodexScanner


def test_codex_scanner_loads_jsonl_session_events(tmp_path: Path):
    session_path = tmp_path / "session-a.jsonl"
    session_path.write_text(
        "\n".join(
            [
                json.dumps({"id": "u1", "role": "user", "content": "请修复测试"}),
                json.dumps(
                    {
                        "id": "t1",
                        "role": "tool",
                        "tool_name": "exec_command",
                        "tool_result": {"stderr": "timeout"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scanner = CodexScanner()
    refs = scanner.discover(ScanRequest(provider="codex", source_dir=tmp_path))
    envelope = scanner.load(refs[0])

    assert refs[0].session_id == "session-a"
    assert refs[0].metadata["source_size"]
    assert refs[0].metadata["source_mtime"]
    assert refs[0].metadata["source_fingerprint"].startswith("sha256:")
    assert envelope.provider == "codex"
    assert [event.event_id for event in envelope.events] == ["u1", "t1"]
    assert envelope.events[1].tool_name == "exec_command"
    locator = envelope.events[0].metadata["event_locator_json"]
    artifact_locator = envelope.events[0].metadata["artifact_locator_json"]

    assert envelope.events[0].metadata["scanner_id"] == "codex"
    assert envelope.events[0].metadata["scanner_version"] == "0.1.0"
    assert locator["schema_version"] == "locator.v0"
    assert locator["scanner_id"] == "codex"
    assert locator["scanner_version"] == "0.1.0"
    assert locator["locator_schema"] == "locator.codex_jsonl.v0"
    assert locator["kind"] == "source_event"
    assert locator["payload"]["source_path"] == str(session_path)
    assert locator["payload"]["line_start"] == 1
    assert locator["payload"]["line_end"] == 1
    assert artifact_locator["locator_schema"] == "locator.evozeus_artifact_jsonl.v0"
    assert envelope.events[0].metadata["content_hash"].startswith("sha256:")
    assert envelope.events[0].metadata["content_preview_redacted"] == "请修复测试"


def test_codex_scanner_loads_archived_payload_shape(tmp_path: Path):
    session_path = tmp_path / "session-archive.jsonl"
    session_path.write_text(
        "\n".join(
            [
                json.dumps({"type": "session_meta", "payload": {"id": "archive-session", "cwd": "/redacted"}}),
                json.dumps({"type": "response_item", "payload": {"role": "user", "content": "这个扫描结果不对"}}),
                json.dumps({"type": "event_msg", "payload": {"type": "exec_command", "message": "command failed"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scanner = CodexScanner()
    refs = scanner.discover(ScanRequest(provider="codex", source_dir=tmp_path))
    envelope = scanner.load(refs[0])

    assert refs[0].session_id == "archive-session"
    assert envelope.session_id == "archive-session"
    assert [event.role for event in envelope.events] == ["user", "tool"]
    assert envelope.events[1].tool_name == "exec_command"
    assert envelope.events[1].tool_result == {"message": "command failed"}


def test_codex_scanner_redacts_secret_like_values_from_preview(tmp_path: Path):
    session_path = tmp_path / "session-secret.jsonl"
    session_path.write_text(
        json.dumps({"id": "u1", "role": "user", "content": "token=abc123 请调试"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    scanner = CodexScanner()
    ref = scanner.discover(ScanRequest(provider="codex", source_dir=tmp_path))[0]
    envelope = scanner.load(ref)

    assert envelope.events[0].content == "token=abc123 请调试"
    assert envelope.events[0].metadata["content_preview_redacted"] == "token=[REDACTED] 请调试"


def test_codex_scanner_normalizes_archived_response_item_tools(tmp_path: Path):
    session_path = tmp_path / "session-tools.jsonl"
    session_path.write_text(
        "\n".join(
            [
                json.dumps({"type": "session_meta", "payload": {"id": "tool-session"}}),
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "exec_command",
                            "call_id": "call-1",
                            "arguments": "{\"cmd\":\"pytest\"}",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "function_call_output",
                            "call_id": "call-1",
                            "output": "pytest failed with timeout",
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scanner = CodexScanner()
    refs = scanner.discover(ScanRequest(provider="codex", source_dir=tmp_path))
    envelope = scanner.load(refs[0])

    assert [event.role for event in envelope.events] == ["tool", "tool"]
    assert envelope.events[0].tool_name == "exec_command"
    assert envelope.events[0].tool_result == {"arguments": "{\"cmd\":\"pytest\"}", "call_id": "call-1"}
    assert envelope.events[1].tool_name == "function_call_output"
    assert envelope.events[1].tool_result == {"output": "pytest failed with timeout", "call_id": "call-1"}


def test_codex_scanner_marks_task_complete_without_repeating_final_answer(tmp_path: Path):
    session_path = tmp_path / "session-complete.jsonl"
    final_answer = "已经传上去了。"
    session_path.write_text(
        "\n".join(
            [
                json.dumps({"type": "session_meta", "payload": {"id": "complete-session"}}),
                json.dumps(
                    {
                        "timestamp": "2026-04-21T10:49:28.472Z",
                        "type": "event_msg",
                        "payload": {"type": "agent_message", "message": final_answer, "phase": "final_answer"},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-04-21T10:49:28.556Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "task_complete",
                            "last_agent_message": final_answer,
                            "completed_at": 1776768568,
                            "duration_ms": 266612,
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scanner = CodexScanner()
    ref = scanner.discover(ScanRequest(provider="codex", source_dir=tmp_path))[0]
    envelope = scanner.load(ref)

    assert [(event.role, event.content) for event in envelope.events] == [
        ("assistant", final_answer),
        ("task_complete", "Task complete"),
    ]
    assert envelope.events[1].metadata["codex_event_type"] == "task_complete"
    assert envelope.events[1].metadata["task_duration_ms"] == "266612"


def test_codex_scanner_keeps_wrapped_records_that_share_timestamp(tmp_path: Path):
    session_path = tmp_path / "session-same-timestamp.jsonl"
    timestamp = "2026-04-21T10:49:28.472Z"
    session_path.write_text(
        "\n".join(
            [
                json.dumps({"type": "session_meta", "payload": {"id": "same-timestamp-session"}}),
                json.dumps({"timestamp": timestamp, "type": "response_item", "payload": {"role": "user", "content": "第一条指令"}}),
                json.dumps({"timestamp": timestamp, "type": "response_item", "payload": {"role": "assistant", "content": "第一条回复"}}),
                json.dumps({"timestamp": timestamp, "type": "event_msg", "payload": {"type": "agent_message", "message": "第二条回复"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scanner = CodexScanner()
    envelope = scanner.load(scanner.discover(ScanRequest(provider="codex", source_dir=tmp_path))[0])

    assert [event.content for event in envelope.events] == ["第一条指令", "第一条回复", "第二条回复"]
    assert len({event.event_id for event in envelope.events}) == 3
    assert all(timestamp in event.event_id for event in envelope.events)


def test_codex_scanner_dedupes_mirrored_user_message_records(tmp_path: Path):
    session_path = tmp_path / "session-mirrored-user.jsonl"
    timestamp = "2026-05-26T07:36:06.499Z"
    user_text = "结合当前的workspace，里面有一个S4 skill，执行S4 skill，生成公司报告出来\n"
    session_path.write_text(
        "\n".join(
            [
                json.dumps({"type": "session_meta", "payload": {"id": "mirrored-user-session"}}),
                json.dumps({"timestamp": timestamp, "type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": user_text}]}}),
                json.dumps({"timestamp": timestamp, "type": "event_msg", "payload": {"type": "user_message", "message": user_text}}),
                json.dumps({"timestamp": "2026-05-26T07:36:18.545Z", "type": "event_msg", "payload": {"type": "agent_message", "message": "我会执行。"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scanner = CodexScanner()
    envelope = scanner.load(scanner.discover(ScanRequest(provider="codex", source_dir=tmp_path))[0])

    assert [(event.role, event.content) for event in envelope.events] == [
        ("user", user_text),
        ("assistant", "我会执行。"),
    ]
    assert envelope.events[0].metadata["event_locator_json"]["payload"]["line_start"] == 2


def test_codex_scanner_bridges_source_id_manifest_to_local_codex_source(tmp_path: Path, monkeypatch):
    source_id = "rollout-test-bridge"
    session_id = "bridge-session"
    fake_home = tmp_path / "home"
    codex_source = fake_home / ".codex" / "sessions" / "2026" / "06" / "17" / f"{source_id}.jsonl"
    codex_source.parent.mkdir(parents=True)
    codex_source.write_text(
        "\n".join(
            [
                json.dumps({"type": "session_meta", "payload": {"id": session_id}}),
                json.dumps({"type": "response_item", "payload": {"id": "u1", "role": "user", "content": "桥接扫描"}}),
                json.dumps({"type": "response_item", "payload": {"id": "a1", "role": "assistant", "content": "已读取原始 source"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    source_dir = tmp_path / "testdata"
    source_dir.mkdir()
    (source_dir / "codex-source-ids.jsonl").write_text(json.dumps({"source_id": source_id}) + "\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(fake_home))

    scanner = CodexScanner()
    refs = scanner.discover(ScanRequest(provider="codex", source_dir=source_dir))
    envelope = scanner.load(refs[0])

    assert len(refs) == 1
    assert refs[0].session_id == session_id
    assert refs[0].source_path == codex_source
    assert refs[0].metadata["bridge_source_id"] == source_id
    assert refs[0].metadata["bridge_manifest"] == str(source_dir / "codex-source-ids.jsonl")
    assert envelope.session_id == session_id
    assert [event.content for event in envelope.events] == ["桥接扫描", "已读取原始 source"]
    assert envelope.events[0].metadata["event_locator_json"]["payload"]["source_path"] == str(codex_source)


def test_codex_scanner_groups_sessions_by_codex_workspace_cwd(tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    codex_root = fake_home / ".codex"
    sessions_root = codex_root / "sessions"
    project_a = "/Users/anthonyf/projects/evozeus"
    project_b = "/Users/anthonyf/projects/openlifeos"

    first_source = sessions_root / "2026" / "06" / "17" / "rollout-first.jsonl"
    second_source = sessions_root / "2026" / "06" / "18" / "rollout-second.jsonl"
    third_source = sessions_root / "2026" / "06" / "18" / "rollout-third.jsonl"
    first_source.parent.mkdir(parents=True)
    second_source.parent.mkdir(parents=True)
    first_source.write_text(
        "\n".join(
            [
                json.dumps({"type": "session_meta", "payload": {"id": "session-first", "cwd": project_a}}),
                json.dumps({"type": "response_item", "payload": {"id": "u1", "role": "user", "content": "first"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    second_source.write_text(
        "\n".join(
            [
                json.dumps({"type": "session_meta", "payload": {"id": "session-second", "cwd": project_a}}),
                json.dumps({"type": "response_item", "payload": {"id": "u1", "role": "user", "content": "second"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    third_source.write_text(
        "\n".join(
            [
                json.dumps({"type": "session_meta", "payload": {"id": "session-third", "cwd": project_b}}),
                json.dumps({"type": "response_item", "payload": {"id": "u1", "role": "user", "content": "third"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (codex_root / "session_index.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"id": "session-first", "thread_name": "较早的 EvoZeus 调试", "updated_at": "2026-06-17T08:00:00Z"}),
                json.dumps({"id": "session-second", "thread_name": "最新的 EvoZeus 调试", "updated_at": "2026-06-18T09:00:00Z"}),
                json.dumps({"id": "session-third", "thread_name": "OpenLifeOS 调试", "updated_at": "2026-06-18T07:00:00Z"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(fake_home))

    scanner = CodexScanner()
    refs = scanner.discover(ScanRequest(provider="codex"))

    assert [ref.session_id for ref in refs] == ["session-second", "session-first", "session-third"]
    assert refs[0].metadata["session_title"] == "最新的 EvoZeus 调试"
    assert refs[0].metadata["session_cwd"] == project_a
    assert refs[0].metadata["session_group_key"] == project_a
    assert refs[0].metadata["session_group_label"] == "evozeus"
    assert refs[0].metadata["session_updated_at"]
    assert refs[0].metadata["codex_source_root"] == str(codex_root)
