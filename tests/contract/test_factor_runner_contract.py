from pathlib import Path

from evozeus_runtime.factors.base import FactorContext
from evozeus_runtime.factors.packs import FactorPackRepository
from evozeus_runtime.runner.runner import FactorRunner
from evozeus_runtime.sessions.schema import SessionEnvelope, SessionEvent


def test_factor_runner_executes_selected_factor_pack():
    session = SessionEnvelope(
        session_id="s1",
        provider="codex",
        source_ref="fixture.jsonl",
        events=[
            SessionEvent(
                event_id="tool-1",
                role="tool",
                content="command failed with traceback",
                tool_name="exec_command",
                tool_result={"status": "error", "output": "Traceback"},
            )
        ],
    )
    factor = FactorPackRepository(Path("tests/fixtures/factor_packs")).get("default.tool_failure")

    summary = FactorRunner([factor]).run(FactorContext(session=session))

    assert summary.errors == []
    assert len(summary.results) == 1
    assert summary.results[0].factor_id == "default.tool_failure"
    assert summary.results[0].status == "matched"

