# Scanner / Runner Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前 repo 从 JS infra probe + Python prototype archive 重构为正式 Python scanner/runner runtime。

**Architecture:** 根目录成为唯一 Python package。Scanner 使用 Adapter + Registry，Factor 使用 ABC + Template Method，Runner 使用 Serial Pipeline + Runtime Strategy，Ledger 使用 Repository Pattern。所有扫描、运行、报告都通过 use case 编排，并经过 policy gate。

**Tech Stack:** Python 3.11+, Typer, Pydantic v2, SQLite, pytest, pathlib, stdlib subprocess, optional Textual/FastAPI 不进入 P0。

---

## File Structure

最终文件结构：

```text
pyproject.toml
README.md
SKILL.md
src/evozeus_runtime/
  __init__.py
  cli/
    __init__.py
    main.py
  policy/
    __init__.py
    permissions.py
  sessions/
    __init__.py
    schema.py
    locator.py
  scanners/
    __init__.py
    base.py
    registry.py
    providers/
      __init__.py
      codex.py
  factors/
    __init__.py
    base.py
    manifest.py
    packs.py
    protocol.py
  runner/
    __init__.py
    runner.py
    runtime.py
    subprocess_worker.py
  registry/
    __init__.py
    manifest_verifier.py
  ledger/
    __init__.py
    paths.py
    repository.py
    migrations/
      001_initial.sql
  reports/
    __init__.py
    markdown.py
    json_report.py
    html.py
  use_cases/
    __init__.py
    scan_sessions.py
    run_factors.py
    generate_report.py
tests/
  unit/
  contract/
  integration/
  fixtures/
```

## Task 1: Remove JS Probe Runtime

**Files:**

- Delete: `package.json`
- Delete: `src/infra.mjs`
- Delete: `scripts/evozeus-infra-doctor.mjs`
- Delete: `scripts/validate-infra-install-plan.mjs`
- Delete: `tests/infra-components.test.mjs`
- Delete: `tests/infra-doctor.test.mjs`
- Delete: `tests/infra-install-plan.test.mjs`

- [ ] **Step 1: Delete tracked JS probe files**

Run:

```bash
git rm package.json \
  src/infra.mjs \
  scripts/evozeus-infra-doctor.mjs \
  scripts/validate-infra-install-plan.mjs \
  tests/infra-components.test.mjs \
  tests/infra-doctor.test.mjs \
  tests/infra-install-plan.test.mjs
```

Expected: files are staged as deleted.

- [ ] **Step 2: Verify no JS runtime references remain**

Run:

```bash
rg -n "infra\\.mjs|evozeus-infra-doctor|validate-infra-install-plan|npm run|node --test" .
```

Expected: only historical docs mention these names. Remove active README/SKILL references in Task 12.

- [ ] **Step 3: Commit**

```bash
git add -u
git commit -m "chore: remove js infra probe runtime"
```

## Task 2: Promote Python Package To Root

**Files:**

- Move: `prototypes/main-repo-runtime/pyproject.toml` -> `pyproject.toml`
- Modify: `pyproject.toml`
- Create: `src/evozeus_runtime/__init__.py`

- [ ] **Step 1: Move pyproject**

Run:

```bash
git mv prototypes/main-repo-runtime/pyproject.toml pyproject.toml
```

- [ ] **Step 2: Replace package metadata**

Set `pyproject.toml` to:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "evozeus-runtime"
version = "0.1.0"
description = "EvoZeus local scanner and factor runner runtime"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "typer>=0.12",
  "pydantic>=2.7",
  "jinja2>=3.1",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
]

[project.scripts]
evozeus-runtime = "evozeus_runtime.cli.main:app"

[tool.hatch.build.targets.wheel]
packages = ["src/evozeus_runtime"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
filterwarnings = [
  "ignore:Using `httpx` with `starlette.testclient` is deprecated",
]
```

- [ ] **Step 3: Create package init**

Create `src/evozeus_runtime/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Run packaging import check**

Run:

```bash
PYTHONPATH=src python -c "import evozeus_runtime; print(evozeus_runtime.__version__)"
```

Expected:

```text
0.1.0
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/evozeus_runtime/__init__.py
git commit -m "chore: promote python runtime package"
```

## Task 3: Move Session Schema And Locator

**Files:**

- Create: `src/evozeus_runtime/sessions/schema.py`
- Create: `src/evozeus_runtime/sessions/locator.py`
- Create: `src/evozeus_runtime/sessions/__init__.py`
- Test: `tests/unit/test_session_schema.py`

- [ ] **Step 1: Write schema test**

Create `tests/unit/test_session_schema.py`:

```python
from evozeus_runtime.sessions.schema import SessionEnvelope, SessionEvent


def test_session_envelope_defaults_schema_version():
    envelope = SessionEnvelope(
        session_id="s1",
        provider="codex",
        source_ref="session.jsonl",
        events=[SessionEvent(event_id="e1", role="user", content="hello")],
    )

    assert envelope.schema_version == "session_envelope.v0"
    assert envelope.events[0].event_id == "e1"
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
PYTHONPATH=src python -m pytest tests/unit/test_session_schema.py -q
```

Expected: import fails because `evozeus_runtime.sessions.schema` does not exist.

- [ ] **Step 3: Implement schema**

Create `src/evozeus_runtime/sessions/schema.py`:

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SessionEvent(BaseModel):
    event_id: str
    role: str
    content: str = ""
    tool_name: str | None = None
    tool_result: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionEnvelope(BaseModel):
    schema_version: str = "session_envelope.v0"
    session_id: str
    provider: str
    source_ref: str
    events: list[SessionEvent] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
```

Create `src/evozeus_runtime/sessions/locator.py`:

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EventLocator(BaseModel):
    schema_version: str = "locator.event.v0"
    provider: str
    source_ref: str
    source_fingerprint: str
    raw_line_index: int
    event_index: int
    payload: dict[str, Any] = Field(default_factory=dict)


class ResolvedEvent(BaseModel):
    locator: EventLocator
    raw_text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
```

Create `src/evozeus_runtime/sessions/__init__.py`:

```python
from evozeus_runtime.sessions.locator import EventLocator, ResolvedEvent
from evozeus_runtime.sessions.schema import SessionEnvelope, SessionEvent

__all__ = ["EventLocator", "ResolvedEvent", "SessionEnvelope", "SessionEvent"]
```

- [ ] **Step 4: Verify test passes**

Run:

```bash
PYTHONPATH=src python -m pytest tests/unit/test_session_schema.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/evozeus_runtime/sessions tests/unit/test_session_schema.py
git commit -m "feat: add runtime session schema"
```

## Task 4: Move Scanner Adapter And Registry

**Files:**

- Create: `src/evozeus_runtime/scanners/base.py`
- Create: `src/evozeus_runtime/scanners/registry.py`
- Create: `src/evozeus_runtime/scanners/providers/codex.py`
- Create: `tests/fixtures/codex_sessions/codex-source-ids.jsonl`
- Create: `tests/contract/test_codex_scanner_contract.py`

- [ ] **Step 1: Move fixture data**

Run:

```bash
mkdir -p tests/fixtures/codex_sessions
git mv prototypes/main-repo-runtime/__infra__/testdata/codex_sessions/codex-source-ids.jsonl \
  tests/fixtures/codex_sessions/codex-source-ids.jsonl
```

- [ ] **Step 2: Write scanner contract test**

Create `tests/contract/test_codex_scanner_contract.py`:

```python
from pathlib import Path

from evozeus_runtime.scanners.base import ScanRequest
from evozeus_runtime.scanners.providers.codex import CodexScanner


def test_codex_scanner_discovers_and_loads_fixture_sessions():
    scanner = CodexScanner()
    source = Path("tests/fixtures/codex_sessions")

    refs = scanner.discover(ScanRequest(provider="codex", source_dir=source))
    assert len(refs) >= 1

    envelope = scanner.load(refs[0])
    assert envelope.provider == "codex"
    assert envelope.session_id
    assert envelope.events
    assert envelope.metadata["scanner_id"] == "codex"
    assert envelope.metadata["scanner_version"] == "0.1.0"
```

- [ ] **Step 3: Move scanner code**

Move and update imports:

```bash
mkdir -p src/evozeus_runtime/scanners/providers
git mv prototypes/main-repo-runtime/__infra__/src/evozeus/scanners/base.py \
  src/evozeus_runtime/scanners/base.py
git mv prototypes/main-repo-runtime/__infra__/src/evozeus/scanners/registry.py \
  src/evozeus_runtime/scanners/registry.py
git mv prototypes/main-repo-runtime/__infra__/src/evozeus/scanners/resolver.py \
  src/evozeus_runtime/sessions/resolver.py
git mv prototypes/main-repo-runtime/__infra__/src/evozeus/scanners/providers/codex.py \
  src/evozeus_runtime/scanners/providers/codex.py
```

Update imports in moved files:

```text
evozeus.core.session -> evozeus_runtime.sessions.schema
evozeus.models -> evozeus_runtime.sessions.schema
evozeus.scanners.base -> evozeus_runtime.scanners.base
evozeus.scanners.resolver -> evozeus_runtime.sessions.resolver
```

- [ ] **Step 4: Add package init files**

Create `src/evozeus_runtime/scanners/__init__.py`:

```python
from evozeus_runtime.scanners.base import ScanRequest, SessionRef, SessionScanner
from evozeus_runtime.scanners.registry import ScannerRegistry

__all__ = ["ScanRequest", "ScannerRegistry", "SessionRef", "SessionScanner"]
```

Create `src/evozeus_runtime/scanners/providers/__init__.py`:

```python
from evozeus_runtime.scanners.providers.codex import CodexScanner

__all__ = ["CodexScanner"]
```

- [ ] **Step 5: Verify scanner contract**

Run:

```bash
PYTHONPATH=src python -m pytest tests/contract/test_codex_scanner_contract.py -q
```

Expected: test passes.

- [ ] **Step 6: Commit**

```bash
git add src/evozeus_runtime/scanners src/evozeus_runtime/sessions tests/contract tests/fixtures
git commit -m "feat: promote codex scanner adapter"
```

## Task 5: Move Factor Schema, Pack Repository, And Runner

**Files:**

- Create: `src/evozeus_runtime/factors/`
- Create: `src/evozeus_runtime/runner/`
- Create: `tests/fixtures/factor_packs/`
- Test: `tests/contract/test_factor_runner_contract.py`

- [ ] **Step 1: Move factor fixtures**

Run:

```bash
mkdir -p tests/fixtures/factor_packs
git mv prototypes/main-repo-runtime/__infra__/factor_packs/* tests/fixtures/factor_packs/
```

- [ ] **Step 2: Move factor and runner code**

Run:

```bash
mkdir -p src/evozeus_runtime/factors src/evozeus_runtime/runner
git mv prototypes/main-repo-runtime/__infra__/src/evozeus/factors/base.py src/evozeus_runtime/factors/base.py
git mv prototypes/main-repo-runtime/__infra__/src/evozeus/factors/manifest.py src/evozeus_runtime/factors/manifest.py
git mv prototypes/main-repo-runtime/__infra__/src/evozeus/factors/packs.py src/evozeus_runtime/factors/packs.py
git mv prototypes/main-repo-runtime/__infra__/src/evozeus/factors/protocol.py src/evozeus_runtime/factors/protocol.py
git mv prototypes/main-repo-runtime/__infra__/src/evozeus/factors/runner.py src/evozeus_runtime/runner/runner.py
git mv prototypes/main-repo-runtime/__infra__/src/evozeus/factors/runtime.py src/evozeus_runtime/runner/runtime.py
git mv prototypes/main-repo-runtime/__infra__/src/evozeus/factors/subprocess_worker.py src/evozeus_runtime/runner/subprocess_worker.py
```

Update imports:

```text
evozeus.core.session -> evozeus_runtime.sessions.schema
evozeus.factors.base -> evozeus_runtime.factors.base
evozeus.factors.manifest -> evozeus_runtime.factors.manifest
evozeus.factors.packs -> evozeus_runtime.factors.packs
evozeus.factors.protocol -> evozeus_runtime.factors.protocol
evozeus.factors.runner -> evozeus_runtime.runner.runner
evozeus.factors.runtime -> evozeus_runtime.runner.runtime
evozeus.factors.subprocess_worker -> evozeus_runtime.runner.subprocess_worker
```

- [ ] **Step 3: Write runner contract test**

Create `tests/contract/test_factor_runner_contract.py`:

```python
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
```

- [ ] **Step 4: Verify runner contract**

Run:

```bash
PYTHONPATH=src python -m pytest tests/contract/test_factor_runner_contract.py -q
```

Expected: test passes.

- [ ] **Step 5: Commit**

```bash
git add src/evozeus_runtime/factors src/evozeus_runtime/runner tests/fixtures/factor_packs tests/contract/test_factor_runner_contract.py
git commit -m "feat: promote factor runner runtime"
```

## Task 6: Add Policy Gate

**Files:**

- Create: `src/evozeus_runtime/policy/permissions.py`
- Create: `src/evozeus_runtime/policy/__init__.py`
- Test: `tests/unit/test_permission_gate.py`

- [ ] **Step 1: Write permission tests**

Create `tests/unit/test_permission_gate.py`:

```python
from pathlib import Path

from evozeus_runtime.policy.permissions import PermissionDeclaration, PermissionGate


def test_permission_gate_rejects_network_by_default():
    declaration = PermissionDeclaration(network_enabled=True, network_reason="download manifest")

    result = PermissionGate().approve(declaration)

    assert result.ok is False
    assert "network" in result.reason


def test_permission_gate_accepts_declared_local_read_inside_source():
    declaration = PermissionDeclaration(files_read=[Path("tests/fixtures/codex_sessions")])

    result = PermissionGate(allow_network=False).approve(declaration)

    assert result.ok is True
```

- [ ] **Step 2: Implement permission gate**

Create `src/evozeus_runtime/policy/permissions.py`:

```python
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class PermissionDeclaration(BaseModel):
    files_read: list[Path] = Field(default_factory=list)
    files_written: list[Path] = Field(default_factory=list)
    env_read: list[str] = Field(default_factory=list)
    external_commands: list[str] = Field(default_factory=list)
    network_enabled: bool = False
    network_reason: str = ""


class PermissionDecision(BaseModel):
    ok: bool
    reason: str = ""


class PermissionGate:
    def __init__(self, *, allow_network: bool = False, allow_external_commands: bool = False):
        self.allow_network = allow_network
        self.allow_external_commands = allow_external_commands

    def approve(self, declaration: PermissionDeclaration) -> PermissionDecision:
        if declaration.network_enabled and not self.allow_network:
            return PermissionDecision(ok=False, reason="network access requires explicit approval")
        if declaration.external_commands and not self.allow_external_commands:
            return PermissionDecision(ok=False, reason="external commands require explicit approval")
        return PermissionDecision(ok=True)
```

Create `src/evozeus_runtime/policy/__init__.py`:

```python
from evozeus_runtime.policy.permissions import PermissionDeclaration, PermissionDecision, PermissionGate

__all__ = ["PermissionDeclaration", "PermissionDecision", "PermissionGate"]
```

- [ ] **Step 3: Verify permission tests**

Run:

```bash
PYTHONPATH=src python -m pytest tests/unit/test_permission_gate.py -q
```

Expected: `2 passed`.

- [ ] **Step 4: Commit**

```bash
git add src/evozeus_runtime/policy tests/unit/test_permission_gate.py
git commit -m "feat: add runtime permission gate"
```

## Task 7: Add Ledger Repository With Migration

**Files:**

- Create: `src/evozeus_runtime/ledger/paths.py`
- Create: `src/evozeus_runtime/ledger/repository.py`
- Create: `src/evozeus_runtime/ledger/migrations/001_initial.sql`
- Test: `tests/integration/test_ledger_repository.py`

- [ ] **Step 1: Write ledger integration test**

Create `tests/integration/test_ledger_repository.py`:

```python
from evozeus_runtime.ledger.paths import RuntimePaths
from evozeus_runtime.ledger.repository import LedgerRepository
from evozeus_runtime.scanners.base import SessionRef


def test_ledger_records_session_refs(tmp_path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()
    ledger = LedgerRepository(paths)

    ledger.record_session_refs([
        SessionRef(provider="codex", session_id="s1", source_path=tmp_path / "s1.jsonl")
    ])

    refs = ledger.list_session_refs()
    assert len(refs) == 1
    assert refs[0].session_id == "s1"
```

- [ ] **Step 2: Implement paths**

Create `src/evozeus_runtime/ledger/paths.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    workspace_root: Path

    @classmethod
    def for_workspace(cls, workspace_root: Path) -> "RuntimePaths":
        return cls(workspace_root=workspace_root)

    @property
    def state_root(self) -> Path:
        return self.workspace_root / ".evozeus" / "runtime"

    @property
    def index_dir(self) -> Path:
        return self.state_root / "index"

    @property
    def ledger_db(self) -> Path:
        return self.index_dir / "results.sqlite3"

    @property
    def sessions_dir(self) -> Path:
        return self.workspace_root / ".evozeus" / "sessions"

    def session_dir(self, session_id: str) -> Path:
        return self.sessions_dir / session_id

    def ensure(self) -> "RuntimePaths":
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        return self
```

- [ ] **Step 3: Add initial migration**

Create `src/evozeus_runtime/ledger/migrations/001_initial.sql`:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_refs (
  provider TEXT NOT NULL,
  session_id TEXT PRIMARY KEY,
  source_path TEXT NOT NULL,
  discovered_at TEXT NOT NULL
);
```

- [ ] **Step 4: Implement repository**

Create `src/evozeus_runtime/ledger/repository.py`:

```python
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from evozeus_runtime.ledger.paths import RuntimePaths
from evozeus_runtime.scanners.base import SessionRef


@dataclass(frozen=True)
class StoredSessionRef:
    provider: str
    session_id: str
    source_path: Path


class LedgerRepository:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        self.db_path = paths.ledger_db
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def record_session_refs(self, refs: list[SessionRef]) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            for ref in refs:
                conn.execute(
                    """
                    INSERT INTO session_refs(provider, session_id, source_path, discovered_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                      provider = excluded.provider,
                      source_path = excluded.source_path
                    """,
                    (ref.provider, ref.session_id, str(ref.source_path), now),
                )

    def list_session_refs(self) -> list[StoredSessionRef]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT provider, session_id, source_path FROM session_refs ORDER BY session_id"
            ).fetchall()
        return [
            StoredSessionRef(provider=row[0], session_id=row[1], source_path=Path(row[2]))
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _migrate(self) -> None:
        migration_path = Path(__file__).parent / "migrations" / "001_initial.sql"
        with self._connect() as conn:
            conn.executescript(migration_path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                ("001_initial", datetime.now(UTC).isoformat()),
            )
```

- [ ] **Step 5: Verify ledger integration**

Run:

```bash
PYTHONPATH=src python -m pytest tests/integration/test_ledger_repository.py -q
```

Expected: test passes.

- [ ] **Step 6: Commit**

```bash
git add src/evozeus_runtime/ledger tests/integration/test_ledger_repository.py
git commit -m "feat: add sqlite runtime ledger"
```

## Task 8: Add Use Cases

**Files:**

- Create: `src/evozeus_runtime/use_cases/scan_sessions.py`
- Create: `src/evozeus_runtime/use_cases/run_factors.py`
- Create: `src/evozeus_runtime/use_cases/generate_report.py`
- Test: `tests/integration/test_scan_run_report_flow.py`

- [ ] **Step 1: Write integration flow test**

Create `tests/integration/test_scan_run_report_flow.py`:

```python
from pathlib import Path

from evozeus_runtime.use_cases.scan_sessions import scan_sessions


def test_scan_sessions_use_case_writes_ledger(tmp_path):
    result = scan_sessions(
        workspace_root=tmp_path,
        provider="codex",
        source_dir=Path("tests/fixtures/codex_sessions"),
    )

    assert result.session_count >= 1
    assert result.ledger_path.exists()
```

- [ ] **Step 2: Implement scan use case**

Create `src/evozeus_runtime/use_cases/scan_sessions.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from evozeus_runtime.ledger.paths import RuntimePaths
from evozeus_runtime.ledger.repository import LedgerRepository
from evozeus_runtime.policy.permissions import PermissionDeclaration, PermissionGate
from evozeus_runtime.scanners.base import ScanRequest
from evozeus_runtime.scanners.providers.codex import CodexScanner


@dataclass(frozen=True)
class ScanSessionsResult:
    session_count: int
    ledger_path: Path


def scan_sessions(*, workspace_root: Path, provider: str, source_dir: Path) -> ScanSessionsResult:
    decision = PermissionGate().approve(PermissionDeclaration(files_read=[source_dir]))
    if not decision.ok:
        raise PermissionError(decision.reason)

    if provider != "codex":
        raise ValueError(f"unsupported provider: {provider}")

    paths = RuntimePaths.for_workspace(workspace_root).ensure()
    scanner = CodexScanner()
    refs = scanner.discover(ScanRequest(provider=provider, source_dir=source_dir))
    ledger = LedgerRepository(paths)
    ledger.record_session_refs(refs)
    return ScanSessionsResult(session_count=len(refs), ledger_path=paths.ledger_db)
```

Create `src/evozeus_runtime/use_cases/run_factors.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunFactorsResult:
    result_count: int
    error_count: int
    ledger_path: Path
```

Create `src/evozeus_runtime/use_cases/generate_report.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GenerateReportResult:
    report_path: Path
```

Create `src/evozeus_runtime/use_cases/__init__.py`:

```python
from evozeus_runtime.use_cases.scan_sessions import ScanSessionsResult, scan_sessions

__all__ = ["ScanSessionsResult", "scan_sessions"]
```

- [ ] **Step 3: Verify flow test**

Run:

```bash
PYTHONPATH=src python -m pytest tests/integration/test_scan_run_report_flow.py -q
```

Expected: test passes.

- [ ] **Step 4: Commit**

```bash
git add src/evozeus_runtime/use_cases tests/integration/test_scan_run_report_flow.py
git commit -m "feat: add scanner runtime use case"
```

## Task 9: Add CLI

**Files:**

- Create: `src/evozeus_runtime/cli/main.py`
- Test: `tests/integration/test_cli.py`

- [ ] **Step 1: Write CLI test**

Create `tests/integration/test_cli.py`:

```python
from typer.testing import CliRunner

from evozeus_runtime.cli.main import app


def test_status_command_prints_runtime_status():
    result = CliRunner().invoke(app, ["status"])

    assert result.exit_code == 0
    assert "scanner-runner-runtime" in result.stdout
```

- [ ] **Step 2: Implement CLI**

Create `src/evozeus_runtime/cli/main.py`:

```python
from __future__ import annotations

from pathlib import Path

import typer

from evozeus_runtime import __version__
from evozeus_runtime.use_cases.scan_sessions import scan_sessions

app = typer.Typer(help="EvoZeus local scanner and factor runner runtime.")


@app.command()
def status() -> None:
    typer.echo(f"evozeus-runtime {__version__}: scanner-runner-runtime")


@app.command()
def scan(
    provider: str = typer.Option("codex", "--provider"),
    source: Path = typer.Option(..., "--source"),
    workspace: Path = typer.Option(Path("."), "--workspace"),
) -> None:
    result = scan_sessions(workspace_root=workspace, provider=provider, source_dir=source)
    typer.echo(f"scanned_sessions={result.session_count}")
    typer.echo(f"ledger={result.ledger_path}")
```

Create `src/evozeus_runtime/cli/__init__.py`:

```python
from evozeus_runtime.cli.main import app

__all__ = ["app"]
```

- [ ] **Step 3: Verify CLI test**

Run:

```bash
PYTHONPATH=src python -m pytest tests/integration/test_cli.py -q
```

Expected: test passes.

- [ ] **Step 4: Commit**

```bash
git add src/evozeus_runtime/cli tests/integration/test_cli.py
git commit -m "feat: add runtime cli"
```

## Task 10: Move Reports

**Files:**

- Create: `src/evozeus_runtime/reports/markdown.py`
- Create: `src/evozeus_runtime/reports/json_report.py`
- Create: `src/evozeus_runtime/reports/html.py`
- Test: `tests/unit/test_reports.py`

- [ ] **Step 1: Write report test**

Create `tests/unit/test_reports.py`:

```python
from evozeus_runtime.factors.protocol import FactorResult
from evozeus_runtime.reports.markdown import render_factor_results_markdown


def test_markdown_report_includes_factor_id():
    result = FactorResult(factor_id="default.tool_failure", status="matched")

    markdown = render_factor_results_markdown("s1", [result])

    assert "# EvoZeus Runtime Report" in markdown
    assert "default.tool_failure" in markdown
```

- [ ] **Step 2: Implement markdown report**

Create `src/evozeus_runtime/reports/markdown.py`:

```python
from __future__ import annotations

from evozeus_runtime.factors.protocol import FactorResult


def render_factor_results_markdown(session_id: str, results: list[FactorResult]) -> str:
    lines = ["# EvoZeus Runtime Report", "", f"- session_id: {session_id}", "", "## Factor Results", ""]
    for result in results:
        lines.extend([
            f"### {result.factor_id}",
            "",
            f"- status: {result.status}",
            f"- confidence: {result.confidence}",
            "",
        ])
    return "\n".join(lines)
```

Create `src/evozeus_runtime/reports/json_report.py`:

```python
from __future__ import annotations

from evozeus_runtime.factors.protocol import FactorResult


def render_factor_results_json(session_id: str, results: list[FactorResult]) -> dict[str, object]:
    return {
        "session_id": session_id,
        "results": [result.model_dump(mode="json") for result in results],
    }
```

Create `src/evozeus_runtime/reports/html.py`:

```python
from __future__ import annotations

from html import escape

from evozeus_runtime.factors.protocol import FactorResult


def render_factor_results_html(session_id: str, results: list[FactorResult]) -> str:
    rows = "\n".join(
        f"<tr><td>{escape(result.factor_id)}</td><td>{escape(result.status)}</td></tr>"
        for result in results
    )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>EvoZeus Runtime Report</title></head>"
        f"<body><h1>EvoZeus Runtime Report</h1><p>session_id: {escape(session_id)}</p>"
        f"<table><thead><tr><th>Factor</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table>"
        "</body></html>"
    )
```

- [ ] **Step 3: Verify report test**

Run:

```bash
PYTHONPATH=src python -m pytest tests/unit/test_reports.py -q
```

Expected: test passes.

- [ ] **Step 4: Commit**

```bash
git add src/evozeus_runtime/reports tests/unit/test_reports.py
git commit -m "feat: add runtime report renderers"
```

## Task 11: Remove Prototype Directory

**Files:**

- Delete: `prototypes/main-repo-runtime/`

- [ ] **Step 1: Verify all promoted imports use new package**

Run:

```bash
rg -n "prototypes/main-repo-runtime|__infra__|from evozeus\\.|import evozeus\\." src tests
```

Expected: no output.

- [ ] **Step 2: Remove prototype directory**

Run:

```bash
git rm -r prototypes/main-repo-runtime
```

- [ ] **Step 3: Verify no smoke files remain**

Run:

```bash
rg -n "smoke" .
```

Expected: no active runtime or tests contain smoke references. Historical archive docs may be removed in Task 12.

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "chore: remove migrated prototype tree"
```

## Task 12: Rewrite README, SKILL, And Docs Index

**Files:**

- Modify: `README.md`
- Modify: `SKILL.md`
- Modify: `docs/README.md`
- Move: `docs/main-repo-cleanup-intake.md` -> `docs/archive/main-repo-cleanup-intake.md`
- Move: `docs/local-analysis-ledger-bootstrap-implementation.md` -> `docs/archive/local-analysis-ledger-bootstrap-implementation.md`

- [ ] **Step 1: Archive historical docs**

Run:

```bash
mkdir -p docs/archive
git mv docs/main-repo-cleanup-intake.md docs/archive/main-repo-cleanup-intake.md
git mv docs/local-analysis-ledger-bootstrap-implementation.md docs/archive/local-analysis-ledger-bootstrap-implementation.md
```

- [ ] **Step 2: Rewrite README**

README must state:

```markdown
# evozeus-runtime

EvoZeus local scanner / runner runtime.

本 repo 负责扫描本地 session、标准化为 `SessionEnvelope`、运行 selected Factor、写入本地 ledger，并生成 Markdown / JSON / HTML report。

## P0 Scope

- Codex local session scanner
- SessionEnvelope schema
- FactorPack loader
- FactorRunner
- SQLite local ledger
- Markdown / JSON / HTML report
- Permission gate for local reads, writes, commands, env, and network

## Non-goals

- 不默认全盘扫描
- 不默认联网
- 不默认上传 raw session
- 不直接安装 lab branch 或未审 factor
- 不把 JS 作为 core runtime
```

- [ ] **Step 3: Rewrite SKILL**

SKILL must state:

```markdown
---
name: evozeus-runtime
description: Use when designing, implementing, reviewing, or debugging EvoZeus local scanner, SessionEnvelope, factor runner, local ledger, report generation, permission gate, or FactorPack execution.
---

# EvoZeus Runtime

This repo is the Python scanner / runner runtime for EvoZeus.

Before changing runtime behavior, identify:

- files read
- files written
- environment variables read
- external commands
- network access
- selected scanner
- selected factors
- rollback path

Default behavior is local-first, upload-off, network-off, and explicit-selection for factors.
```

- [ ] **Step 4: Verify docs no longer present old active positioning**

Run:

```bash
rg -n "future shell|src/infra.mjs|npm run doctor|Stable CLI: no|Default user entry: no" README.md SKILL.md docs
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add README.md SKILL.md docs
git commit -m "docs: reposition repo as scanner runner runtime"
```

## Task 13: Final Verification

**Files:**

- All runtime files
- All tests
- All docs

- [ ] **Step 1: Run full Python test suite**

Run:

```bash
PYTHONPATH=src python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run import sweep**

Run:

```bash
PYTHONPATH=src python - <<'PY'
import evozeus_runtime
from evozeus_runtime.cli.main import app
from evozeus_runtime.scanners.providers.codex import CodexScanner
from evozeus_runtime.runner.runner import FactorRunner
print(evozeus_runtime.__version__)
print(app.info.name)
print(CodexScanner.provider)
print(FactorRunner.__name__)
PY
```

Expected:

```text
0.1.0
None
codex
FactorRunner
```

- [ ] **Step 3: Verify no old active paths remain**

Run:

```bash
test ! -e package.json
test ! -e src/infra.mjs
test ! -d prototypes/main-repo-runtime
rg -n "from evozeus\\.|import evozeus\\.|__infra__|node --test|npm run" src tests README.md SKILL.md
```

Expected: `test` commands exit 0 and `rg` prints no output.

- [ ] **Step 4: Verify git diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: `git diff --check` exits 0. `git status --short` only shows intentional changed files if the final commit has not been created.

- [ ] **Step 5: Commit final cleanup**

```bash
git add -A
git commit -m "chore: complete scanner runner runtime migration"
```

## Self-Review

- Spec coverage: The plan covers deletion of JS probes, Python package promotion, scanner contract, runner contract, policy gate, ledger, reports, CLI, docs repositioning, and prototype removal.
- Placeholder scan: This document avoids placeholder labels and gives concrete paths, commands, expected outputs, and minimal code skeletons.
- Type consistency: The plan consistently uses `evozeus_runtime`, `SessionEnvelope`, `SessionEvent`, `FactorRunner`, `RuntimePaths`, `LedgerRepository`, and `scan_sessions`.

