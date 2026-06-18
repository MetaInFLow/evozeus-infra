# Local Analysis Ledger Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> Migration note: 本计划已从 `EvoZeus` 主 repo 移入 `evozeus-runtime`。旧 `__infra__/...` 路径表示 historical main-repo prototype 的原始文件位置，不是当前实现目标路径。执行新任务时应先把对应模块设计到本 repo 的 runtime 结构中，再实现和验证。

**Goal:** 将 EvoZeus 本地 runtime 从单次 report 生成升级为可 bootstrap、可增量分析、可被 TUI / browser workspace 共同消费的 Local Analysis Ledger。

**Architecture:** SQLite 是本地事实账本。CLI/TUI 负责 bootstrap 和入口，FastAPI companion backend 提供本地 API，browser workspace 通过 route registry 渲染 Sessions / Dashboards / Factor Packs。

**Tech Stack:** Python 3.11, Typer, FastAPI, SQLite, Pydantic, pytest, Ant Design browser workspace.

**Implementation status (2026-06-17):**

- Completed: Task 1-8 core implementation.
- Completed: Ant Design HTML workspace slice with Sessions / Dashboards / Factor Packs tabs.
- Verified: `pytest -q` passes, onboard -> scan -> analyze -> HTML closes on local test data.
- Remaining: broader browser workspace API documentation and future multi-provider scanner packs.

---

## File Map

| File | Responsibility |
| --- | --- |
| `__infra__/src/evozeus/workspace.py` | workspace bootstrap、config 写入、目录创建 |
| `__infra__/src/evozeus/runtime/paths.py` | `.evozeus` runtime 路径定义 |
| `__infra__/src/evozeus/storage/sqlite_result_store.py` | SQLite schema、source/capability/execution/result/route 写入与查询 |
| `__infra__/src/evozeus/factors/packs.py` | bundled/downloaded factor pack discovery |
| `__infra__/src/evozeus/scanners/base.py` | scanner metadata、locator、fingerprint contract |
| `__infra__/src/evozeus/scanners/resolver.py` | SourceResolver protocol、EventLocator、ResolvedEvent |
| `__infra__/src/evozeus/scanners/providers/codex.py` | Codex source discovery、canonical session id、locator、fingerprint |
| `__infra__/scanner_packs/codex/0.1.0/` | bundled Codex scanner pack、SKILL、resolver script |
| `__infra__/src/evozeus/cli.py` | `onboard`、scan/analyze 入口 |
| `__infra__/src/evozeus/companion/app.py` | local API |
| `__infra__/tests/test_workspace.py` | bootstrap 行为测试 |
| `__infra__/tests/test_sqlite_result_store.py` | SQLite schema 和查询测试 |
| `__infra__/tests/test_companion.py` | local backend API 测试 |
| `__infra__/tests/test_smoke_scripts.py` | 端到端 smoke |

## Task 1: Bootstrap Workspace Config

**Files:**

- Modify: `__infra__/src/evozeus/workspace.py`
- Modify: `__infra__/tests/test_workspace.py`

- [ ] **Step 1: Write failing test for minimal bootstrap layout**

Add a test that creates a workspace and asserts:

```python
def test_create_workspace_initializes_minimal_runtime(tmp_path: Path):
    workspace = create_workspace(tmp_path)

    assert workspace.root == tmp_path / ".evozeus"
    assert (workspace.root / "config.json").exists()
    assert (workspace.root / "runtime" / "index").is_dir()
    assert (workspace.root / "runtime" / "factors" / "installed").is_dir()
    assert (workspace.root / "runtime" / "scanners" / "installed").is_dir()
    assert (workspace.root / "sessions").is_dir()
    assert (workspace.root / "logs").is_dir()
    assert not (workspace.root / "drafts").exists()
    assert not (workspace.root / "history").exists()
```

- [ ] **Step 2: Write failing test for config fields**

```python
def test_create_workspace_writes_local_first_config(tmp_path: Path):
    workspace = create_workspace(tmp_path)
    config = json.loads((workspace.root / "config.json").read_text(encoding="utf-8"))

    assert config["schema_version"] == "workspace_config.v0"
    assert config["workspace_id"].startswith("ewk_")
    assert config["mode"] == "local_manual"
    assert config["privacy"]["upload_default"] is False
    assert config["privacy"]["redaction_required_for_export"] is True
    assert config["scan"]["providers"] == ["codex"]
    assert config["scan"]["auto_load_events"] is True
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest __infra__/tests/test_workspace.py -q
```

Expected: fails because `logs` and config schema are not implemented.

- [ ] **Step 4: Implement minimal workspace config**

Update `create_workspace()` to:

```python
from datetime import UTC, datetime
from uuid import uuid4
import json
```

Create only runtime folders, sessions, and logs. Write config with `workspace_id`, `created_at`, privacy, scan, companion.

- [ ] **Step 5: Verify green**

Run:

```bash
.venv/bin/python -m pytest __infra__/tests/test_workspace.py -q
```

Expected: all workspace tests pass.

## Task 2: Add Companion and Log Runtime Paths

**Files:**

- Modify: `__infra__/src/evozeus/runtime/paths.py`
- Modify: `__infra__/tests/test_runtime_paths.py`

- [ ] **Step 1: Write failing path test**

```python
def test_runtime_paths_include_logs_and_companion(tmp_path: Path):
    paths = RuntimePaths.for_workspace(tmp_path)

    assert paths.logs_dir == tmp_path / ".evozeus" / "logs"
    assert paths.companion_runtime_dir == tmp_path / ".evozeus" / "runtime" / "companion"
```

- [ ] **Step 2: Verify failure**

Run:

```bash
.venv/bin/python -m pytest __infra__/tests/test_runtime_paths.py -q
```

Expected: missing properties.

- [ ] **Step 3: Implement properties and `ensure()`**

Add:

```python
@property
def logs_dir(self) -> Path:
    return self.state_root / "logs"

@property
def companion_runtime_dir(self) -> Path:
    return self.runtime_root / "companion"
```

Include both in `ensure()`.

- [ ] **Step 4: Verify green**

Run:

```bash
.venv/bin/python -m pytest __infra__/tests/test_runtime_paths.py -q
```

Expected: pass.

## Task 3: Add Capability and Route Tables

**Files:**

- Modify: `__infra__/src/evozeus/storage/sqlite_result_store.py`
- Modify: `__infra__/tests/test_sqlite_result_store.py`

- [ ] **Step 1: Write failing schema test**

Add assertions that the DB has:

```text
source_refs
installed_factors
factor_capabilities
factor_result_routes
```

Use SQLite `sqlite_master`.

- [ ] **Step 2: Write failing factor registry test**

Create a minimal fake factor pack object or use real `FactorPackRepository(PACK_ROOT).discover()` and call:

```python
store.record_installed_factors(packs, source="bundled")
factors = store.list_installed_factors()
```

Assert:

```python
assert any(row.factor_id == "default.tool_failure" for row in factors)
assert row.source == "bundled"
assert row.enabled is True
assert row.status == "available"
```

- [ ] **Step 3: Write failing route test**

Call:

```python
store.record_default_routes(packs)
routes = store.list_factor_result_routes()
```

Assert:

```python
assert any(route.factor_id == "default.tool_failure" and route.route_area == "dashboard" for route in routes)
assert any(route.route_area == "sessions_table" for route in routes)
```

- [ ] **Step 4: Verify failure**

Run:

```bash
.venv/bin/python -m pytest __infra__/tests/test_sqlite_result_store.py -q
```

Expected: methods and tables missing.

- [ ] **Step 5: Implement schema and dataclasses**

Add dataclasses:

```python
InstalledFactor
FactorCapability
FactorResultRoute
```

Add tables with `CREATE TABLE IF NOT EXISTS`.

- [ ] **Step 6: Implement registry methods**

Add:

```python
record_installed_factors(packs, source: str)
list_installed_factors()
record_default_routes(packs)
list_factor_result_routes()
```

Default route mapping can be conservative:

```text
all factors -> drawer/factor_result
all factors -> sessions_table/factor_tags
tool_failure/open_loop/correction/task_span/success -> dashboard/<name>
```

- [ ] **Step 7: Verify green**

Run:

```bash
.venv/bin/python -m pytest __infra__/tests/test_sqlite_result_store.py -q
```

Expected: pass.

## Task 4: Scanner-Owned Source Locator

**Decision:** SQLite 只记录 locator 和 lightweight index。回到原始 event 的逻辑、脚本和 Agent 使用方法跟随 scanner pack，不写进 factor、browser workspace 或通用 storage 层。

**Files:**

- Create: `__infra__/src/evozeus/scanners/resolver.py`
- Modify: `__infra__/src/evozeus/scanners/base.py`
- Modify: `__infra__/src/evozeus/scanners/providers/codex.py`
- Modify: `__infra__/src/evozeus/storage/sqlite_result_store.py`
- Create: `__infra__/scanner_packs/codex/0.1.0/SKILL.md`
- Create: `__infra__/scanner_packs/codex/0.1.0/scanner.json`
- Create: `__infra__/scanner_packs/codex/0.1.0/SCANNER.xml`
- Create: `__infra__/scanner_packs/codex/0.1.0/resolver.py`
- Create: `__infra__/scanner_packs/codex/0.1.0/scripts/resolve_event_source.py`
- Test: `__infra__/tests/test_codex_scanner.py`
- Test: `__infra__/tests/test_sqlite_result_store.py`
- Test: `__infra__/tests/test_source_resolver.py`

- [ ] **Step 1: Write failing scanner locator test**

Extend Codex scanner tests so loaded events include scanner-owned locator metadata:

```python
event = envelope.events[0]
locator = event.metadata["event_locator_json"]

assert locator["schema_version"] == "locator.v0"
assert locator["scanner_id"] == "codex"
assert locator["scanner_version"] == "0.1.0"
assert locator["locator_schema"] == "locator.codex_jsonl.v0"
assert locator["kind"] == "source_event"
assert locator["payload"]["line_start"] == 1
assert event.metadata["content_hash"].startswith("sha256:")
assert "content_preview_redacted" in event.metadata
```

- [ ] **Step 2: Write failing SQLite lightweight event test**

Update SQLite tests so `session_events` no longer stores full raw content:

```python
columns = {
    row[1]
    for row in conn.execute("PRAGMA table_info(session_events)").fetchall()
}

assert "content" not in columns
assert "tool_result_json" not in columns
assert "content_hash" in columns
assert "content_preview_redacted" in columns
assert "event_locator_json" in columns
assert "artifact_locator_json" in columns
assert "scanner_id" in columns
assert "scanner_version" in columns
```

- [ ] **Step 3: Write failing resolver contract test**

Create a Codex JSONL source, scan it, then resolve one event through Codex resolver:

```python
resolver = CodexSourceResolver()
resolved = resolver.resolve_event(EventLocator.model_validate(locator))

assert resolved.content == "请修复测试"
assert resolver.verify_hash(resolved, event.metadata["content_hash"]) is True
```

- [ ] **Step 4: Verify failure**

Run:

```bash
.venv/bin/python -m pytest __infra__/tests/test_codex_scanner.py __infra__/tests/test_sqlite_result_store.py __infra__/tests/test_source_resolver.py -q
```

Expected: locator fields, resolver protocol, and lightweight columns are missing.

- [ ] **Step 5: Implement resolver protocol**

Create `__infra__/src/evozeus/scanners/resolver.py` with:

```python
from typing import Protocol, Any
from pydantic import BaseModel, Field


class EventLocator(BaseModel):
    schema_version: str = "locator.v0"
    scanner_id: str
    scanner_version: str
    locator_schema: str
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ResolvedEvent(BaseModel):
    scanner_id: str
    scanner_version: str
    session_id: str = ""
    event_id: str = ""
    source_ref: str
    content: str
    content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceResolver(Protocol):
    scanner_id: str
    scanner_version: str

    def resolve_event(self, locator: EventLocator) -> ResolvedEvent:
        ...

    def verify_hash(self, resolved: ResolvedEvent, expected_hash: str) -> bool:
        ...
```

- [ ] **Step 6: Implement Codex locator and resolver**

Codex scanner should emit `event_locator_json`, `artifact_locator_json`, `content_hash`, `content_preview_redacted`, `scanner_id`, and `scanner_version` in event metadata.

Codex resolver should read the original JSONL line from `payload.source_path` and `payload.line_start`, normalize content the same way scanner does, and verify hash.

- [ ] **Step 7: Add scanner pack docs and script**

Create bundled Codex scanner pack files:

```text
__infra__/scanner_packs/codex/0.1.0/SKILL.md
__infra__/scanner_packs/codex/0.1.0/scanner.json
__infra__/scanner_packs/codex/0.1.0/SCANNER.xml
__infra__/scanner_packs/codex/0.1.0/scripts/resolve_event_source.py
```

`SKILL.md` must explain how an Agent uses SQLite `scanner_id/scanner_version` to call the resolver.

- [ ] **Step 8: Verify green**

Run:

```bash
.venv/bin/python -m pytest __infra__/tests/test_codex_scanner.py __infra__/tests/test_sqlite_result_store.py __infra__/tests/test_source_resolver.py -q
```

Expected: pass.

## Task 5: Source Fingerprint and Incremental Status

**Files:**

- Modify: `__infra__/src/evozeus/scanners/base.py`
- Modify: `__infra__/src/evozeus/scanners/providers/codex.py`
- Modify: `__infra__/src/evozeus/storage/sqlite_result_store.py`
- Modify: `__infra__/tests/test_codex_scanner.py`
- Modify: `__infra__/tests/test_sqlite_result_store.py`

- [ ] **Step 1: Extend SessionRef metadata test**

Assert discovered refs include:

```python
assert refs[0].metadata["source_size"]
assert refs[0].metadata["source_mtime"]
assert refs[0].metadata["source_fingerprint"]
```

- [ ] **Step 2: Add stale test**

Record a factor run with fingerprint `A`, then update the same source ref with fingerprint `B`.

Assert `list_session_statuses()` returns:

```python
row.pending_factor_count == 1
row.stale_reason == "source_changed"
```

- [ ] **Step 3: Verify failure**

Run:

```bash
.venv/bin/python -m pytest __infra__/tests/test_codex_scanner.py __infra__/tests/test_sqlite_result_store.py -q
```

Expected: fingerprint metadata and stale fields missing.

- [ ] **Step 4: Implement source fingerprint**

Use provider-local logic:

```text
fingerprint = sha256(path + size + mtime_ns + first_64kb + last_64kb)
```

Store it in `SessionRef.metadata`.

- [ ] **Step 5: Store fingerprint in SQLite**

Add `source_refs` table fields:

```text
provider
source_ref
source_size
source_mtime
source_fingerprint
last_seen_at
```

Add fields to `factor_run_index`:

```text
source_fingerprint
factor_fingerprint
runtime_fingerprint
run_reason
stale_reason
```

- [ ] **Step 6: Verify green**

Run:

```bash
.venv/bin/python -m pytest __infra__/tests/test_codex_scanner.py __infra__/tests/test_sqlite_result_store.py -q
```

Expected: pass.

## Task 6: Bootstrap CLI Registers Bundled Factors

**Files:**

- Modify: `__infra__/src/evozeus/cli.py`
- Modify: `__infra__/tests/test_cli.py`
- Modify: `__infra__/tests/test_smoke_scripts.py`

- [ ] **Step 1: Write failing CLI test**

Invoke `evozeus onboard` in a temp cwd. Assert:

```text
.evozeus/config.json exists
.evozeus/runtime/index/results.sqlite3 exists
installed_factors count >= 8
factor_result_routes count > 0
```

- [ ] **Step 2: Verify failure**

Run:

```bash
.venv/bin/python -m pytest __infra__/tests/test_cli.py -q
```

Expected: `onboard` only prints text.

- [ ] **Step 3: Implement onboard**

`onboard` should:

```text
create_workspace(Path.cwd())
open SQLiteResultStore
discover bundled factor packs
record installed factors
record default routes
print workspace path and sqlite path
```

- [ ] **Step 4: Verify green**

Run:

```bash
.venv/bin/python -m pytest __infra__/tests/test_cli.py __infra__/tests/test_smoke_scripts.py -q
```

Expected: pass.

## Task 7: Companion Backend Read APIs

**Files:**

- Modify: `__infra__/src/evozeus/companion/app.py`
- Modify: `__infra__/tests/test_companion.py`

- [ ] **Step 1: Write failing API tests**

Use `TestClient` and a temp workspace.

Assert:

```text
GET /api/bootstrap/status returns initialized=false before bootstrap
POST /api/bootstrap creates workspace
GET /api/factors returns installed factors
GET /api/routes returns factor result routes
GET /api/sessions returns sessions after scan data exists
```

All requests must include `?token=<token>`.

- [ ] **Step 2: Verify failure**

Run:

```bash
.venv/bin/python -m pytest __infra__/tests/test_companion.py -q
```

Expected: endpoints missing.

- [ ] **Step 3: Implement API**

Keep API thin:

```text
request -> token check -> SQLiteResultStore / workspace service -> JSON response
```

Do not add duplicate state inside FastAPI app.

- [ ] **Step 4: Verify green**

Run:

```bash
.venv/bin/python -m pytest __infra__/tests/test_companion.py -q
```

Expected: pass.

## Task 8: Scan and Analyze Action APIs

**Files:**

- Modify: `__infra__/src/evozeus/companion/app.py`
- Modify: `__infra__/scripts/run_session_report.py`
- Create: `__infra__/src/evozeus/runtime/analysis_service.py`
- Test: `__infra__/tests/test_companion.py`
- Test: `__infra__/tests/test_smoke_scripts.py`

- [ ] **Step 1: Extract shared analysis service**

Create `analysis_service.py` so CLI and backend use one flow:

```text
discover sessions
record refs
load selected session
run selected factors
record SQLite run
write optional md/html artifacts
```

- [ ] **Step 2: Write failing API tests**

Assert:

```text
POST /api/scan records sessions
POST /api/analyze/{session_id} writes factor_results
GET /api/sessions shows pending=0 for analyzed session
```

- [ ] **Step 3: Verify failure**

Run:

```bash
.venv/bin/python -m pytest __infra__/tests/test_companion.py -q
```

- [ ] **Step 4: Implement service and wire CLI/backend**

Keep `run_session_report.py` as a thin CLI wrapper around the service.

- [ ] **Step 5: Verify green**

Run:

```bash
.venv/bin/python -m pytest __infra__/tests/test_companion.py __infra__/tests/test_smoke_scripts.py -q
```

Expected: pass.

## Task 9: Browser Workspace Data Contract

**Files:**

- Modify: `docs/reference/report-templates.md`
- Modify: `docs/reference/factor-analysis-protocol.md`
- Create: `docs/reference/browser-workspace-api.md`
- Modify: `docs/reference/scanner-pack-protocol.md`
- Modify: `docs/reference/source-locator-protocol.md`

- [ ] **Step 1: Document API payloads**

Create examples for:

```text
GET /api/sessions
GET /api/factors
GET /api/routes
GET /api/dashboards
GET /api/sessions/{session_id}/factor-results
```

- [ ] **Step 2: Document route areas**

Document:

```text
sessions_table
dashboard
drawer
tui
```

- [ ] **Step 3: Document scanner-owned source resolution**

Add browser workspace notes:

```text
Event detail drawer receives locator summary from SQLite.
Raw event expansion calls backend resolver API.
Backend chooses resolver by scanner_id / scanner_version.
Resolver implementation comes from installed scanner pack.
```

- [ ] **Step 4: Verify docs links**

Run:

```bash
rg -n "browser-workspace-api|factor_result_routes|Local Analysis Ledger|scanner-pack-protocol|source-locator-protocol" docs __infra__/README.md
git diff --check
```

Expected: references exist and diff check passes.

## Task 10: Full Verification and Commit

**Files:**

- All touched files.

- [ ] **Step 1: Run full tests**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run smoke scripts**

Run:

```bash
PYTHONPATH=__infra__/src .venv/bin/python __infra__/scripts/scan_sessions_smoke.py --source __infra__/testdata/codex_sessions --min-sessions 4
PYTHONPATH=__infra__/src .venv/bin/python __infra__/scripts/result_report_smoke.py
```

Expected:

```text
scan sessions ok
result report ok
```

- [ ] **Step 3: Verify git diff**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only intended files changed.

- [ ] **Step 4: Commit**

```bash
git add __infra__ docs
git commit -m "Add local analysis ledger bootstrap plan"
```

## Implementation Notes

- Keep backend local-only: bind `127.0.0.1`, token required.
- Keep SQLite as the only persistent state source.
- Do not create proposal/history directories during bootstrap.
- Do not upload data.
- Keep factor execution serial in P0.
- Add migrations with `CREATE TABLE IF NOT EXISTS`; schema-breaking migrations can wait until after P0.
