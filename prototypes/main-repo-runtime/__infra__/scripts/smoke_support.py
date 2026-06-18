from __future__ import annotations

import json
from pathlib import Path

from evozeus.core.session import SessionEnvelope
from evozeus.models import SessionEvent


def write_sample_codex_session(source_dir: Path) -> Path:
    source_dir.mkdir(parents=True, exist_ok=True)
    session_path = source_dir / "session-a.jsonl"
    session_path.write_text(
        "\n".join(
            [
                json.dumps({"id": "u1", "role": "user", "content": "请修复 runtime，还是有 timeout"}),
                json.dumps({"id": "a1", "role": "assistant", "content": "我会检查 scanner 和 factor。"}),
                json.dumps(
                    {
                        "id": "t1",
                        "role": "tool",
                        "tool_name": "exec_command",
                        "tool_result": {"stderr": "fatal: network timeout"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return session_path


def sample_session() -> SessionEnvelope:
    return SessionEnvelope(
        session_id="session-a",
        provider="codex",
        source_ref="memory",
        events=[
            SessionEvent(event_id="u1", role="user", content="请修复 runtime，还是有 timeout"),
            SessionEvent(event_id="a1", role="assistant", content="我会检查 scanner 和 factor。"),
            SessionEvent(
                event_id="t1",
                role="tool",
                tool_name="exec_command",
                tool_result={"stderr": "fatal: network timeout"},
            ),
        ],
    )
