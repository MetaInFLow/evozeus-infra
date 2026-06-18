# Local Analysis Ledger 与 Bootstrap 设计文档

- Status: Draft
- Owner: EvoZeus Core
- Last updated: 2026-06-17

> Migration note: 本文已从 `EvoZeus` 主 repo 移入 `evozeus-runtime`。旧文中的 main-repo prototype 路径只作为历史设计线索；新的 runtime implementation 应落在本 repo，不应把执行层加回 `EvoZeus` 主 repo。

## 背景

EvoZeus 的本地 runtime 需要支持 Skill Driven Software 的最短闭环：

```text
扫描本地 session
-> 判断本地 factor 能力
-> 跑 pending / stale factor
-> 记录 result 和 event 级 evidence
-> 根据 factor_id 和 route 显示到 Sessions / Dashboards / Drawer
```

当前实现已经有 `.evozeus/runtime/index/results.sqlite3`，可以记录 session、event、analysis run、factor result、tag、evidence 和 event -> tag 映射。下一步需要把它从 result index 扩展为 Local Analysis Ledger，本地分析账本。

这个账本服务本地用户和本地 Agent。社区贡献、远程同步、factor marketplace、云端托管不进入当前设计范围。

## 目标

1. 第一次 bootstrap 后，本地有稳定的 `.evozeus/` runtime 状态。
2. 本地 SQLite 能回答“扫到了什么、跑过什么、什么时候跑、哪些还没跑”。
3. 本地 SQLite 能回答“有哪些 factor、什么时候安装、是否启用、支持哪些输入”。
4. factor result 的展示位置由 route registry 决定，UI 不硬编码 factor_id。
5. TUI、browser workspace、local companion backend 共享同一个 SQLite 事实账本。
6. 静态 Markdown/HTML report 继续作为导出和阅读产物。

## 非目标

P0 不做远程服务。

P0 不做社区贡献图谱。

P0 不做云同步。

P0 不默认上传任何 session、event、result。

P0 不做完整 GUI 应用，只做 TUI + local browser workspace。

## 核心原则

### 1. SQLite 是本地事实账本

SQLite 保存本地 runtime 的结构化事实。报告页面、TUI、companion backend 都只消费这个账本，不各自维护状态。

### 2. Bootstrap 只创建最小 runtime

第一次运行只创建 config、SQLite schema、bundled factor registry、空 runtime 目录。内容型目录按需创建。

### 3. Factor 是本地能力

factor pack 可以来自 bundled 或 downloaded。runtime 必须知道 factor 是否存在、是否启用、是否支持当前 provider / target。

### 4. Result 通过 route 展示

factor result 不直接绑定 UI。`factor_result_routes` 决定结果进入 Sessions 表格、Dashboard widget、Drawer section 或 TUI command。

### 5. 增量分析必须有 fingerprint

只记录 last run 不够。runtime 需要比较 source、factor、runtime config 的 fingerprint，判断首次运行、跳过、重跑、过期和失败。

## 本地目录

Bootstrap 后：

```text
.evozeus/
  config.json
  runtime/
    index/
      results.sqlite3
    factors/
      installed/
    scanners/
      installed/
    companion/
  sessions/
  logs/
```

按需创建：

```text
.evozeus/sessions/<session_id>/
  session-envelope.json
  events.jsonl
  factor-results.md
  factor-results.html
```

P0 bootstrap 不默认创建：

```text
.evozeus/drafts/
.evozeus/history/
.evozeus/skill-proposals/
```

这些目录等用户或 Agent 真的产生 proposal、history artifact、export artifact 时再创建。

## Workspace Config

`.evozeus/config.json`：

```json
{
  "schema_version": "workspace_config.v0",
  "workspace_id": "ewk_...",
  "created_at": "2026-06-17T00:00:00+00:00",
  "mode": "local_manual",
  "privacy": {
    "upload_default": false,
    "redaction_required_for_export": true
  },
  "scan": {
    "providers": ["codex"],
    "auto_load_events": true
  },
  "companion": {
    "host": "127.0.0.1",
    "port": 0
  }
}
```

`port=0` 表示启动时由系统分配可用端口。

## SQLite 分层

```text
Local Analysis Ledger
├── Source Layer
├── Scanner Layer
├── Capability Layer
├── Execution Layer
├── Result Layer
└── Route Layer
```

### Source Layer

记录本地扫描事实。

| Table | Purpose |
| --- | --- |
| `source_refs` | provider、source_path、mtime、size、source_fingerprint |
| `sessions` | session_id、provider、source_ref、event_count、discovered_at、loaded_at |
| `session_events` | event_id、role、hash、redacted preview、locator、tool_name、metadata_json |

`source_fingerprint` 用于判断 session 文件是否变化。P0 可以使用 `mtime + size + partial content hash`。

SQLite 不默认保存完整原文。`session_events` 保存定位和索引字段：

```text
provider
scanner_id
scanner_version
source_ref
source_fingerprint
event_locator_json
artifact_locator_json
content_hash
content_preview_redacted
tool_result_hash
tool_result_preview_redacted
```

原文读取由对应 scanner pack 的 resolver 处理。

### Scanner Layer

记录本地 scanner 能力和原文定位机制。

| Table | Purpose |
| --- | --- |
| `installed_scanners` | scanner_id、version、provider、installed_at、enabled、status |
| `scanner_capabilities` | scanner_id、version、source_format、locator_schema、supported |

Scanner pack 是 provider-specific 能力包。Core runtime 只保存统一 locator envelope，不理解 provider 私有格式。

### Scanner-Owned Source Resolution

SQLite 和原始数据之间的对应机制归属 scanner pack。

| Layer | Owns |
| --- | --- |
| SQLite | `scanner_id`、`scanner_version`、`source_ref`、fingerprint、locator envelope、redacted preview |
| Core runtime | 通用 scanner / resolver contract、resolver registry、权限边界 |
| Scanner pack | provider 私有 locator payload、原始文件解析、hash 校验、定位脚本、Agent 使用说明 |
| Factor | 读取标准化 `SessionEnvelope`，只写 `FactorResult`、tags、evidence refs |
| Browser / TUI | 默认展示 preview 和 locator summary，点击展开时通过 backend 调 scanner resolver |

这个归属避免 SQLite 绑定 Codex、Claude Code、Cursor、Feishu 等私有格式。下载、升级或删除某个 scanner pack 时，它携带的 resolver、脚本和 `SKILL.md` 一起变化；Local Analysis Ledger 只保留可路由的引用。

Bundled scanner pack 可以放在：

```text
__infra__/scanner_packs/<scanner_id>/<version>/
```

用户下载的 scanner pack 放在：

```text
.evozeus/runtime/scanners/installed/<scanner_id>/<version>/
```

每个 scanner pack 至少包含：

```text
scanner.json
SCANNER.xml
SKILL.md
scanner.py
resolver.py
scripts/resolve_event_source.py
```

`scanner.py` 负责 discover / load / normalize。`resolver.py` 负责根据 SQLite 的 locator 找回原始 event。`SKILL.md` 负责告诉 Agent 如何使用该 scanner 定位原文、校验 hash、处理 source missing 或 hash mismatch。

原文定位链路：

```text
event_factor_tags
  -> session_events(session_id, event_id)
  -> scanner_id / scanner_version
  -> event_locator_json / artifact_locator_json
  -> installed scanner pack
  -> scanner pack SKILL.md
  -> resolver.py
  -> provider 原始 event 或 normalized artifact
```

### Capability Layer

记录本地 factor 能力。

| Table | Purpose |
| --- | --- |
| `installed_factors` | factor_id、version、source、installed_at、enabled、runtime_mode、status |
| `factor_capabilities` | factor_id、version、provider、target_type、supported、reason |

`source` 取值：

```text
bundled
downloaded
local_dev
```

`status` 取值：

```text
available
disabled
invalid_manifest
runtime_missing
unsupported
```

### Execution Layer

记录分析运行事实。

| Table | Purpose |
| --- | --- |
| `analysis_runs` | 一次分析运行，包含 session、factor 列表、开始/完成时间、状态 |
| `factor_run_index` | 每个 session/factor 的最新运行状态 |
| `factor_run_errors` | factor 失败诊断 |

`factor_run_index` 需要包含：

```text
session_id
factor_id
factor_version
last_run_at
last_status
source_fingerprint
factor_fingerprint
runtime_fingerprint
run_reason
stale_reason
```

`run_reason` 取值：

```text
first_run
source_changed
factor_changed
runtime_changed
manual_rerun
scheduled_incremental
```

`stale_reason` 为空表示当前结果 fresh。

### Result Layer

记录 factor 输出。

| Table | Purpose |
| --- | --- |
| `factor_results` | 保存 `FactorResult` 的结构化字段、scores、verdict signals |
| `factor_tags` | 保存 result-level tags |
| `factor_evidence` | 保存 result 到 event 的 evidence refs |
| `event_factor_tags` | 保存 event -> factor tag 的最新映射 |

`FactorResult.target_type` 和 `target_id` 必须进入查询索引。P0 默认 target 是 `session`，后续支持 `event`、`task_span`、`case`。

### Route Layer

记录 result 显示路由。

| Table | Purpose |
| --- | --- |
| `factor_result_routes` | factor_id 到 UI 区域和组件的映射 |

字段：

```text
factor_id
result_type
route_area
route_key
component
title
priority
enabled
```

`route_area` 取值：

```text
sessions_table
dashboard
drawer
tui
```

示例：

```text
default.tool_failure -> dashboard/tool_failure_overview
default.tool_failure -> sessions_table/risk_tags
default.tool_failure -> drawer/evidence_list
default.task_span_extraction -> dashboard/task_flow
```

## Bootstrap 流程

```text
evozeus onboard 或 evozeus tui
  -> detect .evozeus
  -> create config.json
  -> create runtime directories
  -> create SQLite schema
  -> register bundled factor packs
  -> register default result routes
  -> print local status
```

Bootstrap 后，SQLite 里应该有：

```text
schema_meta
installed_factors
factor_capabilities
factor_result_routes
```

Bootstrap 后，SQLite 里不应该有：

```text
sessions
session_events
analysis_runs
factor_results
event_factor_tags
```

这些数据等 scan/analyze 后写入。

## Scan 流程

```text
scan provider=codex
  -> discover SessionRef
  -> update source_refs
  -> upsert sessions
  -> if auto_load_events: load SessionEnvelope
  -> generate scanner-owned locators
  -> write normalized artifact if configured
  -> upsert lightweight session_events
  -> compute source_fingerprint
```

Scan 后可以回答：

- 扫到了哪些 session
- 每个 session 有多少 event
- 哪些 session 还没有跑 factor
- 哪些 session 的 source 已变化

## Analyze 流程

```text
select target sessions
  -> read installed_factors where enabled=true
  -> filter factor_capabilities by provider/target_type
  -> compare source/factor/runtime fingerprint
  -> build analysis plan
  -> run pending or stale factors
  -> write analysis_runs
  -> write factor_results / tags / evidence
  -> update event_factor_tags
  -> update factor_run_index
```

状态：

```text
unsupported
pending
running
fresh
stale
error
```

P0 可以串行运行 factor。并发留给后续版本。

## Local Companion Backend

需要一个轻量 backend，绑定 `127.0.0.1`，启动时生成 token。它只负责 API 和 runtime action dispatch，不保存第二份状态。

P0 API：

```text
GET  /api/bootstrap/status
POST /api/bootstrap
GET  /api/sessions
GET  /api/sessions/{session_id}
GET  /api/sessions/{session_id}/events
GET  /api/sessions/{session_id}/factor-results
GET  /api/factors
GET  /api/routes
GET  /api/dashboards
POST /api/scan
POST /api/analyze
POST /api/analyze/{session_id}
```

所有 API 必须校验 token。

## Browser Workspace

主 Tab：

```text
Sessions
Dashboards
Factor Packs
```

约束：

1. 一个页面只有一个 major function。
2. Dashboard 页可以堆叠多个 widget。
3. 所有详情通过点击打开 Drawer。
4. Sessions 选择状态可传给 Dashboards。
5. Dashboard widget 数量由 `factor_result_routes` 和 installed factors 决定。

## 隐私边界

SQLite 默认不保存完整原文，只保存 hash、redacted preview 和 locator。

Raw session content 留在 provider 原始文件或 `.evozeus/sessions/<session_id>/events.jsonl` normalized artifact 中。读取原文必须通过 scanner pack resolver。

导出、社区贡献、远程分享必须经过 redaction。

P0 backend 不提供上传接口。

## 验收标准

1. 新 workspace 运行 `evozeus onboard` 后出现 `.evozeus/config.json` 和 `results.sqlite3`。
2. Bootstrap 后 DB 有 bundled factors 和 default routes。
3. Bootstrap 后 DB 没有 session result 数据。
4. Scan 后 DB 有 sessions / source_refs / session_events。
5. Analyze 后 DB 有 analysis_runs / factor_results / event_factor_tags / factor_run_index。
6. 重复 analyze 未变化 session 时能判断 fresh。
7. 修改 source 或 factor fingerprint 后能判断 stale。
8. 通过 scanner pack resolver 可以从 SQLite locator 找回原始 event 或 normalized artifact。
9. Browser workspace 可以从 backend 读取 sessions、factors、routes、dashboard payload。

## Open Questions

1. P0 是否需要默认扫描所有 Codex session，还是只在用户点击 Scan 后执行。
2. P0 是否允许用户在 browser workspace 触发 Analyze All。
3. source fingerprint 是否先用 `mtime + size`，还是直接做内容 hash。
