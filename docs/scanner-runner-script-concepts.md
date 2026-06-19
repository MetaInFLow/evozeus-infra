# Scanner / Runner 脚本概念说明

本文总结当前 `scripts/run_scanner.py`、`scripts/run_runner.py` 和 `scripts/render_sqlite_html.py` 范围内的一等概念、字段边界和数据流。

## 脚本范围

| 脚本 | 入口能力 | 写入 |
| --- | --- | --- |
| `scripts/run_scanner.py` | 扫描本地 provider session，发现 chat record 和 message id | SQLite local ledger |
| `scripts/run_runner.py` | 对一个已扫描的 `session_id` 跑 selected Factor | SQLite local ledger |
| `scripts/render_sqlite_html.py` | 从 SQLite local ledger 生成 provider/project/session/chat 静态 HTML | HTML report |

当前脚本不是上传入口，不联网，不安装未审 Factor，不把 raw message content 写入 scan 结果。

## 核心原则

1. Scanner `scan` 阶段只记录 `session_id` 和 `message_id`。
2. Scanner `scan` 阶段可以记录非内容元数据：project、role、tool_name、locator、source fingerprint。
3. Scanner `scan` 阶段不能写 message content、tool output、content preview 或 tool result preview。
4. Runner `run` 阶段才通过 scanner `iter_events()` 渐进式读取完整内容，再由 `load()` materialize `SessionEnvelope`。
5. Factor result 通过 `session_id + message_id(event_id)` 挂回 SQLite 中对应 message。
6. Provider 私有格式只能留在 scanner adapter 内，runner、ledger、factor 只依赖统一 contract。

## 数据流

```text
run_scanner.py
  -> scan_sessions()
  -> ScannerRegistry
  -> SessionScanner.discover()
  -> SessionScanner.discover_message_refs()
  -> LedgerRepository.record_session_refs()
  -> LedgerRepository.record_session_message_refs()
  -> SQLite sessions / session_events

run_runner.py
  -> run_factors()
  -> LedgerRepository.get_session_ref(session_id)
  -> ScannerRegistry.load(ref)
  -> SessionEnvelope
  -> FactorRunner
  -> LedgerRepository.record_factor_run()
  -> SQLite analysis_runs / factor_results / factor_evidence / event_factor_tags

render_sqlite_html.py
  -> generate_ledger_browser()
  -> LedgerRepository.list_session_statuses()
  -> LedgerRepository.list_session_events()
  -> render_ledger_browser_html()
  -> Static HTML visualizer
```

## 一级概念

| 概念 | 当前类型 / 表 | 含义 |
| --- | --- | --- |
| Provider | `ScanRequest.provider`, `SessionRef.provider` | 本地 session 来源类型。当前 P0 是 `codex`。 |
| Project | `sessions.project_key`, `sessions.project_label` | 一组 chat record 的项目归属。Codex 当前从 `session_group_key/session_group_label` 映射。 |
| Chat Record / Session | `SessionRef`, `sessions` | 一条本地对话记录。主键是 `session_id`。 |
| Message / Event | `SessionMessageRef`, `session_events` | chat record 内的一条 message/event id。SQLite 里字段名沿用 `event_id`。 |
| Source Ref | `source_refs`, `sessions.source_ref` | provider 原始 session 文件路径或 source reference。 |
| Source Fingerprint | `source_refs.source_fingerprint`, `session_events.source_fingerprint` | source 变更检测和 Factor stale 判断依据。 |
| Source Locator | `session_events.event_locator_json` | 回到 provider 原始记录的定位信息，例如 source path 和 JSONL line。 |
| Artifact Locator | `session_events.artifact_locator_json` | 指向未来 normalized artifact 的定位信息。scan 阶段只记录 locator，不写内容。 |
| SessionEnvelope | `sessions/schema.py` | runner 跑 Factor 前 materialize 的统一 session contract。scan 阶段不落完整 envelope 内容。 |
| Factor | `FactorPack`, `factor_id` | 被选择运行的分析单元。 |
| Analysis Run | `analysis_runs.analysis_run_id` | 一次 runner 执行记录。 |
| Factor Result | `factor_results`, `factor_evidence`, `event_factor_tags` | Factor 输出及其证据、标签。证据通过 `session_id + event_id` 关联 message。 |
| Ledger | `RuntimePaths.result_index_db` | 本地 SQLite 索引和结果库。默认位于 `<workspace>/.evozeus/runtime/index/results.sqlite3`。 |

## 一级概念详解和例子

| 概念 | 它是什么意思 | 例子 | 为什么脚本需要它 |
| --- | --- | --- | --- |
| Provider | session 来源应用或来源协议。不同应用的本地记录格式不同，所以需要 provider 区分。 | `codex` | `run_scanner.py --provider codex` 通过 provider 选择 `CodexScanner`。 |
| Project | 一组 chat records 的项目归属。它是用户理解和筛选记录的第一层分组。 | `project_key=/Users/anthonyf/Documents/EvoZeus-community`，`project_label=EvoZeus-community` | UI 或查询可以按 project 列出这个 repo 下的所有 chat records。 |
| Chat Record / Session | 一条完整对话记录，也就是一次 Codex chat / thread / rollout 文件对应的逻辑 session。 | `session_id=019ecc42-5ef3-7e82-8f05-ec83b90b9c3a`，title 是 `优化 Agent 唯一注册机制` | `run_runner.py --session-id <id>` 用它选择要跑 Factor 的 chat。 |
| Message / Event | session 内的一条消息或事件。当前 SQLite 字段名叫 `event_id`，业务语义上可以理解为 message id。 | `event_id=event_0002`，或真实 Codex 行定位 id `2026-06-15T17:10:38.553Z#L4` | Factor evidence、tags、结果都要挂回具体 message。 |
| Source Ref | provider 原始 session 的来源地址，P0 通常是本地 JSONL 文件路径。 | `/Users/anthonyf/.codex/sessions/2026/06/16/rollout-...jsonl` | Runner 需要从它重新加载完整 session；resolver 也靠它回源。 |
| Source Fingerprint | 对 source 文件状态的 fingerprint，用于判断 session 是否变化。 | `sha256:10cbf36f77a7b...` | Factor 跑完后，如果 source fingerprint 变了，可以判断已有结果 stale。 |
| Source Locator | 指向原始 provider record 的精确定位信息。Codex JSONL 里通常是文件路径和行号。 | `line_start=2`，`record_type=response_item`，`payload_type=message` | 不存 message 内容也能在需要时回到原始行。 |
| Artifact Locator | 指向未来 normalized artifact 的定位信息。当前是预留定位，不代表 scan 阶段已经写 artifact 内容。 | `.evozeus/sessions/session-minimal/events.jsonl` 第 1 行 | 后续如果生成 normalized artifact，可以保持稳定引用。 |
| SessionEnvelope | runner 阶段 materialize 出来的统一 session 对象，Factor 只读它，不直接读 provider 私有格式。 | `SessionEnvelope(session_id="session-minimal", provider="codex", events=[...])` | `FactorRunner` 需要完整 message 内容时，从这里读取。scan 阶段不写它的内容。 |
| Factor | 一个被选择运行的分析逻辑单元。它读取 `SessionEnvelope`，输出结构化结果。 | `default.tool_failure` | `run_runner.py --factor default.tool_failure` 指定要跑哪个 Factor。 |
| Analysis Run | 一次 runner 执行。一次执行可以包含一个或多个 Factor。 | `analysis_run_id=arun_5191021c20604f80b511315f3a0f3197` | 用于追踪这次运行的输入、状态、结果数量和错误数量。 |
| Factor Result | Factor 的输出结果，以及它引用的 evidence 和 tags。 | `factor_id=default.tool_failure`，evidence ref 指向 `event_0003` | 结果需要能回到 session 和 message，才能解释“为什么这个 Factor 这么判断”。 |
| Ledger | 本地 SQLite 数据库，保存扫描索引和运行结果。 | `/tmp/workspace/.evozeus/runtime/index/results.sqlite3` | scanner 和 runner 通过它衔接：scan 先建索引，runner 后写结果。 |

一个具体例子：

```text
Provider:
  codex

Project:
  project_key=/Users/anthonyf/Documents/EvoZeus-community
  project_label=EvoZeus-community

Chat Record / Session:
  session_id=019ecc42-5ef3-7e82-8f05-ec83b90b9c3a
  title=优化 Agent 唯一注册机制
  event_count=680

Message / Event:
  event_id=2026-06-15T17:10:38.553Z#L4
  event_index=3
  role=user

Source Locator:
  source_path=/Users/anthonyf/.codex/sessions/2026/06/16/rollout-2026-06-16T01-09-22-019ecc42-5ef3-7e82-8f05-ec83b90b9c3a.jsonl
  line_start=4

Factor Result:
  factor_id=default.tool_failure
  evidence_ref=session_id + event_id
```

这个例子里，scanner 只写 project、session id、message id、role 和 locator。message 原文不进入 scan 结果。runner 后续按 `session_id` 找回 source，再 materialize `SessionEnvelope` 给 selected Factor 使用。

## Abstract Class 和 Adapter

`SessionScanner` 是 scanner 的 abstract base class。每个 provider scanner 必须实现同一组方法：

| 方法 | 阶段 | 作用 |
| --- | --- | --- |
| `source_dirs(request)` | scan 前 | 声明将读取的本地目录，给 permission gate 使用。 |
| `can_discover(request)` | scan | 判断当前 scanner 是否能处理指定 source。 |
| `discover(request)` | scan | 发现 chat record，返回 `SessionRef`。 |
| `discover_message_refs(ref)` | scan | 发现 message id，返回 `SessionMessageRef`。 |
| `iter_events(ref)` | run | 用 generator 渐进式读取完整 event。 |
| `load(ref)` | run | 消费 `iter_events(ref)`，返回完整 `SessionEnvelope`。 |

当前内置 adapter：

| Adapter | Provider | 默认 source dirs |
| --- | --- | --- |
| `CodexScanner` | `codex` | `~/.codex/sessions`, `~/.codex/archived_sessions` |

`ScannerRegistry` 负责按 `provider` 路由 scanner。use case 不应该直接硬编码某个 provider。

## Project 字段

`Project` 已经是 `sessions` 表的一等字段：

| 字段 | 含义 | Codex 映射来源 |
| --- | --- | --- |
| `project_key` | 稳定项目键，优先用完整路径 | `session_group_key`，缺省回退 `session_cwd` |
| `project_label` | UI 展示名 | `session_group_label`，缺省取 `project_key` basename |

示例：

```text
project_key=/Users/anthonyf/Documents/EvoZeus-community
project_label=EvoZeus-community
```

按项目列 chat records 时，应查询 `sessions.project_key/project_label`，不要从 `metadata_json` 临时解析。

## Session 字段

`sessions` 表记录 chat record 级别信息。

| 字段 | 是否 scan 阶段写入 | 用途 |
| --- | --- | --- |
| `session_id` | 是 | chat record 主键。 |
| `provider` | 是 | provider 路由，例如 `codex`。 |
| `project_key` | 是 | 项目聚合键。 |
| `project_label` | 是 | 项目展示名。 |
| `source_ref` | 是 | 原始 session 来源。 |
| `discovered_at` | 是 | 本次发现时间。 |
| `first_seen_at` | 是 | 首次发现时间。 |
| `last_seen_at` | 是 | 最近发现时间。 |
| `loaded_at` | 否，runner load 后写 | 最近 materialize 完整 session 的时间。 |
| `event_count` | 是 | scan 阶段发现的 message/event 数。 |
| `metadata_json` | 是 | provider metadata 兼容字段，不作为主要查询面。 |

## Message / Event 字段

`session_events` 表在 scan 后是 message id index，不是内容仓库。

| 字段 | 是否 scan 阶段写入 | 用途 |
| --- | --- | --- |
| `session_id` | 是 | 关联 chat record。 |
| `event_id` | 是 | message id。Factor evidence 使用这个 id。 |
| `event_index` | 是 | message 顺序。 |
| `provider` | 是 | provider 路由。 |
| `scanner_id` | 是 | scanner 标识。 |
| `scanner_version` | 是 | scanner 版本。 |
| `role` | 是 | 非内容元数据，例如 `user`、`assistant`、`tool`、`task_complete`。 |
| `tool_name` | 是，可能为空 | tool message 的工具名，例如 `exec_command`。 |
| `source_ref` | 是 | 原始 session 来源。 |
| `source_fingerprint` | 是 | source 变更检测。 |
| `event_locator_json` | 是 | 回源定位。 |
| `artifact_locator_json` | 是 | normalized artifact 定位预留。 |
| `content_hash` | scan 阶段为空 | runner load 后可写内容 hash。 |
| `content_preview_redacted` | scan 阶段为空 | 不在 scan 阶段保存 preview。 |
| `tool_result_hash` | scan 阶段为空 | runner load 后可写 tool result hash。 |
| `tool_result_preview_redacted` | scan 阶段为空 | 不在 scan 阶段保存 tool result preview。 |
| `metadata_json` | 是 | 非内容 metadata 和 locator 兼容存储。 |

## Runner 结果字段

Runner 使用 `session_id` 找到 `SessionRef`，再通过 scanner `load()` 得到完整 `SessionEnvelope`。Factor 执行后写入：

| 表 | 作用 |
| --- | --- |
| `analysis_runs` | 一次 runner 执行记录，包含 selected factor ids、result/error count、status。 |
| `factor_results` | Factor 输出主表。 |
| `factor_evidence` | Factor 证据引用，引用 `session_id + event_id`。 |
| `event_factor_tags` | message 级标签，用于把 Factor 结论挂回具体 message。 |
| `factor_run_index` | session/factor 的最近运行状态和 stale 判断索引。 |

## 当前脚本输出

`run_scanner.py` 标准输出：

```text
scanned_sessions=<count>
ledger=<workspace>/.evozeus/runtime/index/results.sqlite3
```

`run_runner.py` 标准输出：

```text
results=<count>
errors=<count>
analysis_run_id=<id>
ledger=<workspace>/.evozeus/runtime/index/results.sqlite3
```

`render_sqlite_html.py` 标准输出：

```text
html=<workspace>/.evozeus/runtime/reports/evozeus-sqlite.html
ledger=<workspace>/.evozeus/runtime/index/results.sqlite3
providers=<count>
projects=<count>
sessions=<count>
messages=<count>
```

脚本 stdout 只用于快速确认。判断字段是否够用，应直接查 SQLite。

## 字段够用性的当前判断

当前 scanner 输出足够支持：

- 按 `project_key/project_label` 列 project 下的 chat records。
- 按 `session_id` 找到 chat record。
- 按 `session_id + event_id` 把 Factor evidence 和 tags 挂回 message。
- 按 `event_index` 还原 message 顺序。
- 按 `role/tool_name` 做基础过滤和 evidence 展示。
- 按 `source_fingerprint` 判断 source 是否变化。
- 按 `event_locator_json` 回到原始 provider record。

当前 scanner 输出刻意不支持：

- scan 阶段展示 message 原文。
- scan 阶段存储 tool output。
- scan 阶段生成内容摘要。

这些必须在 runner 或显式 resolver 阶段按权限加载。
