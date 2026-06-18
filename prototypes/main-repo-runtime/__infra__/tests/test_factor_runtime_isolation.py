import json
import os
import textwrap
from pathlib import Path

from evozeus.core.session import SessionEnvelope
from evozeus.factors.base import FactorContext
from evozeus.factors.packs import FactorPackRepository
from evozeus.factors.runner import FactorRunner
from evozeus.models import SessionEvent


def test_factor_runner_resolves_in_process_pack(tmp_path: Path):
    pack = _write_factor_pack(
        tmp_path,
        factor_id="test.in_process",
        runtime={"mode": "in_process", "timeout_ms": 1000},
        code=_factor_code(
            """
            return FactorResult(
                factor_id=self.manifest.id,
                factor_version=self.manifest.version,
                framework_id=self.manifest.framework_id,
                stage=self.manifest.stage,
                target_type="session",
                target_id=context.session.session_id,
                session_id=context.session.session_id,
                tags=[{"type": "runtime", "value": "in_process"}],
                confidence=0.8,
            )
            """
        ),
    )

    summary = FactorRunner([pack]).run(_context())

    assert not summary.errors
    assert summary.results[0].factor_id == "test.in_process"
    assert summary.results[0].tags == [{"type": "runtime", "value": "in_process"}]


def test_subprocess_uv_factor_runs_outside_parent_process(tmp_path: Path):
    pack = _write_factor_pack(
        tmp_path,
        factor_id="test.subprocess",
        runtime={"mode": "subprocess_uv", "timeout_ms": 5000},
        code=_factor_code(
            """
            import os
            return FactorResult(
                factor_id=self.manifest.id,
                factor_version=self.manifest.version,
                framework_id=self.manifest.framework_id,
                stage=self.manifest.stage,
                target_type="session",
                target_id=context.session.session_id,
                session_id=context.session.session_id,
                tags=[{"type": "pid", "value": str(os.getpid())}],
                confidence=0.9,
            )
            """
        ),
    )

    summary = FactorRunner([pack]).run(_context())

    assert not summary.errors
    assert summary.results[0].factor_id == "test.subprocess"
    assert summary.results[0].tags[0]["value"] != str(os.getpid())


def test_subprocess_uv_timeout_is_reported_and_next_factor_continues(tmp_path: Path):
    slow_pack = _write_factor_pack(
        tmp_path,
        factor_id="test.slow",
        runtime={"mode": "subprocess_uv", "timeout_ms": 100},
        code=_factor_code(
            """
            import time
            time.sleep(2)
            return FactorResult(
                factor_id=self.manifest.id,
                factor_version=self.manifest.version,
                framework_id=self.manifest.framework_id,
                stage=self.manifest.stage,
                target_type="session",
                target_id=context.session.session_id,
                session_id=context.session.session_id,
                confidence=0.1,
            )
            """
        ),
    )
    next_pack = _write_factor_pack(
        tmp_path,
        factor_id="test.next",
        runtime={"mode": "in_process", "timeout_ms": 1000},
        code=_factor_code(
            """
            return FactorResult(
                factor_id=self.manifest.id,
                factor_version=self.manifest.version,
                framework_id=self.manifest.framework_id,
                stage=self.manifest.stage,
                target_type="session",
                target_id=context.session.session_id,
                session_id=context.session.session_id,
                confidence=0.7,
            )
            """
        ),
    )

    summary = FactorRunner([slow_pack, next_pack]).run(_context())

    assert [result.factor_id for result in summary.results] == ["test.next"]
    assert summary.errors[0].factor_id == "test.slow"
    assert summary.errors[0].error_type == "FactorTimeoutError"


def test_subprocess_uv_invalid_stdout_is_reported(tmp_path: Path):
    pack = _write_factor_pack(
        tmp_path,
        factor_id="test.invalid_stdout",
        runtime={"mode": "subprocess_uv", "timeout_ms": 5000},
        code=_factor_code(
            """
            import os
            os.write(1, b"not-json\\n")
            return FactorResult(
                factor_id=self.manifest.id,
                factor_version=self.manifest.version,
                framework_id=self.manifest.framework_id,
                stage=self.manifest.stage,
                target_type="session",
                target_id=context.session.session_id,
                session_id=context.session.session_id,
                confidence=0.7,
            )
            """
        ),
    )

    summary = FactorRunner([pack]).run(_context())

    assert not summary.results
    assert summary.errors[0].factor_id == "test.invalid_stdout"
    assert summary.errors[0].error_type == "FactorInvalidResultError"


def test_subprocess_uv_declared_dependency_requires_lock_file(tmp_path: Path):
    pack = _write_factor_pack(
        tmp_path,
        factor_id="test.missing_lock",
        runtime={
            "mode": "subprocess_uv",
            "dependency_file": "pyproject.toml",
            "lock_file": "uv.lock",
            "timeout_ms": 5000,
        },
        code=_factor_code(
            """
            return FactorResult(
                factor_id=self.manifest.id,
                factor_version=self.manifest.version,
                framework_id=self.manifest.framework_id,
                stage=self.manifest.stage,
                target_type="session",
                target_id=context.session.session_id,
                session_id=context.session.session_id,
                confidence=0.7,
            )
            """
        ),
    )
    (pack.root / "pyproject.toml").write_text("[project]\nname = \"test-missing-lock\"\nversion = \"0.1.0\"\n", encoding="utf-8")

    summary = FactorRunner([pack]).run(_context())

    assert not summary.results
    assert summary.errors[0].factor_id == "test.missing_lock"
    assert summary.errors[0].error_type == "FactorInstallError"
    assert "uv.lock" in summary.errors[0].message


def _context() -> FactorContext:
    return FactorContext(
        session=SessionEnvelope(
            session_id="session-runtime",
            provider="codex",
            source_ref="memory",
            events=[SessionEvent(event_id="u1", role="user", content="检查 runtime isolation")],
        )
    )


def _write_factor_pack(tmp_path: Path, factor_id: str, runtime: dict[str, object], code: str):
    root = tmp_path / "packs"
    pack_dir = root / factor_id / "0.1.0"
    pack_dir.mkdir(parents=True)
    manifest = {
        "schema_version": "factor.v0",
        "id": factor_id,
        "name": factor_id.replace(".", "-"),
        "framework_id": "agent_session_review.v0",
        "stage": "signal_extraction",
        "runtime_profile": "default",
        "default_enabled": True,
        "version": "0.1.0",
        "status": "active",
        "description": "runtime isolation test factor",
        "entrypoint": "factor:TestFactor",
        "inputs": ["session.events"],
        "outputs": ["factor_result"],
        "permissions": ["read_session_events"],
        "risks": [],
        "rollback": "delete this factor folder",
        "runtime": runtime,
    }
    (pack_dir / "factor.json").write_text(json.dumps(manifest), encoding="utf-8")
    (pack_dir / "FACTOR.xml").write_text(_factor_xml(factor_id, runtime), encoding="utf-8")
    (pack_dir / "factor.py").write_text(code, encoding="utf-8")
    return FactorPackRepository(root).discover()[0]


def _factor_xml(factor_id: str, runtime: dict[str, object]) -> str:
    runtime_mode = runtime.get("mode", "in_process")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<factor id="{factor_id}" version="0.1.0">
  <name>
    <zh>运行时隔离测试因子</zh>
    <en>{factor_id.replace(".", "-")}</en>
  </name>
  <summary>
    <zh>runtime isolation 测试因子。</zh>
    <en>Runtime isolation test factor.</en>
  </summary>
  <category>test</category>
  <stage>signal_extraction</stage>
  <runtime>{runtime_mode}</runtime>
  <inputs>
    <input>session.events</input>
  </inputs>
  <outputs>
    <output>factor_result</output>
  </outputs>
  <tag_labels>
    <tag type="runtime" value="in_process">
      <zh>进程内运行</zh>
      <en>In-process runtime</en>
    </tag>
    <tag type="pid" value="*">
      <zh>子进程编号</zh>
      <en>Subprocess pid</en>
    </tag>
  </tag_labels>
  <when_to_use>
    <zh>测试 runtime runner 行为时使用。</zh>
    <en>Use this for testing runtime runner behavior.</en>
  </when_to_use>
  <limitations>
    <zh>只用于测试，不代表真实分析能力。</zh>
    <en>Test-only factor; it does not represent real analysis capability.</en>
  </limitations>
  <privacy>
    <zh>只读取测试 SessionEnvelope。</zh>
    <en>Reads only the test SessionEnvelope.</en>
  </privacy>
</factor>
"""


def _factor_code(run_body: str) -> str:
    body = textwrap.indent(textwrap.dedent(run_body).strip(), " " * 8)
    return (
        "from __future__ import annotations\n\n"
        "from pathlib import Path\n\n"
        "from evozeus.factors.base import Factor, FactorContext\n"
        "from evozeus.factors.manifest import load_manifest\n"
        "from evozeus.factors.protocol import FactorResult\n\n\n"
        "class TestFactor(Factor):\n"
        "    def __init__(self) -> None:\n"
        "        self.manifest = load_manifest(Path(__file__).with_name(\"factor.json\"))\n\n"
        "    def run(self, context: FactorContext) -> FactorResult:\n"
        f"{body}\n"
    )
