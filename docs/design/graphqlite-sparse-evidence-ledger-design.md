# GraphQLite Sparse Evidence Ledger 总体方案

- Status: Draft
- Date: 2026-06-21
- Owner: EvoZeus infra
- Language: 中文为主，保留必要 English 专有名词

## 1. 结论

`evozeus-infra` 的 local ledger 迁到 **GraphQLite-first**。

当前 `results.sqlite3` 里的关系表只作为一次性迁移输入。迁移完成后，scanner、runner、report、cohort、cluster 都读写 GraphQLite graph store。GraphQLite 仍然是本地 SQLite 扩展，不引入外部图数据库服务，不改变 local-first / upload-off 的默认边界。

核心模型采用 **Sparse Evidence Graph**：

- `Session` 全量入图。
- `SourceRef`、`Project`、`Factor`、`FactorResult`、`Tag`、`TagAssertion`、`Cohort`、`Cluster` 等分析单位入图。
- session 内部 chat 不全量入图。
- 只有被 factor 用作 evidence、被打 tag、被人工 bookmark、被 cohort/cluster 需要解释的 chat，才创建 `ChatEventRef`。
- 原始完整 chat 继续留在 provider source file，通过 scanner resolver 和 locator 读取。

这样既能支持图查询和聚类，又不会把所有本地 chat 都复制进 graph。

## 2. 外部依赖

GraphQLite 是 SQLite graph extension，支持 Python API、SQL `cypher()`、Cypher 查询和内置图算法。

参考：

- https://colliery-io.github.io/graphqlite/latest/
- https://github.com/colliery-io/graphqlite
- https://colliery-io.github.io/graphqlite/latest/reference/python-api.html
- https://colliery-io.github.io/graphqlite/latest/reference/database-schema.html

依赖策略：

- P0 可以把 `graphqlite` 放进 optional dependency，例如 `evozeus-runtime[graph]`。
- 激进迁移分支里，GraphQLite 不再是 report 的可选投影层，而是 ledger repository 的 primary backend。
- 如果本机未安装 GraphQLite，CLI 必须给出明确安装提示，不 silent fallback 到 legacy SQLite ledger。

## 3. 目标

1. 把旧 SQLite ledger 迁成适合关系聚合、tag 查询、cohort 和 cluster 的 GraphQLite graph。
2. 保留 scanner 的隐私边界：scan 阶段不保存 message content、tool output 或 preview。
3. 把 tag 从展示字段升级为可追踪的一等判断对象。
4. 把 cohort 和 cluster 做成可复查、可命名、可迭代的 graph artifact。
5. 支持按项目、tag、factor、evidence、cluster 等维度查询历史 session。
6. 支持后续 Feishu、Cursor、Claude Code 等 scanner provider 接入同一图模型。

## 4. 非目标

- 不默认上传 raw session。
- 不默认联网。
- 不引入 Neo4j、Kuzu、remote graph service。
- 不把所有 chat 原文复制进 ledger。
- 不把未被 evidence/tag/cluster 引用的 chat 全量建成 graph node。
- 不在 GraphQLite schema 里保存 provider 私有 raw payload；provider 私有定位仍归 scanner resolver。

## 5. 存储路径

迁移期：

```text
.evozeus/runtime/index/results.sqlite3          legacy input
.evozeus/runtime/index/results.graph.sqlite3    GraphQLite migration output
.evozeus/runtime/index/results.sqlite3.legacy   legacy backup after cutover
```

切换后：

```text
.evozeus/runtime/index/results.sqlite3          GraphQLite primary ledger
```

`results.sqlite3` 这个文件名可以保留，避免上层路径和脚本全部改名；但文件内部 schema 变成 GraphQLite node / edge / property tables。

## 6. 稳定 ID 规则

GraphQLite 高层 API 接受 user-defined string node id。所有 node id 必须由 infra 生成，保证幂等迁移和重复 sync 不产生重复节点。

```text
workspace:{workspace_id}
provider:{provider}
source:{provider}:{sha256(source_ref)}
project:{provider}:{sha256(project_key)}
scanner:{scanner_id}:{scanner_version}
session:{provider}:{session_id}
chat_event:{provider}:{session_id}:{event_id}
factor:{factor_id}:{version}
analysis_run:{analysis_run_id}
factor_result:{result_run_id}
tag:{tag_type}:{tag_value}
tag_assertion:{result_run_id}:{target_node_id}:{tag_type}:{tag_value}
dataset:{result_run_id}:{dataset_id}
dataset_record:{result_run_id}:{dataset_id}:{record_id}
presentation:{result_run_id}:{presentation_id}
route:{route_area}:{route_key}
run_error:{analysis_run_id}:{factor_id}:{ordinal}
cohort:{cohort_id}
cluster_run:{cluster_run_id}
cluster:{cluster_run_id}:{cluster_id}
feature_set:{feature_set_id}
source_issue:{provider}:{session_id}:{issue_id}
```

如果 legacy data 缺少引用目标，建 stub：

```text
event_stub:{provider}:{session_id}:{event_id}
factor_stub:{factor_id}
target_stub:{target_type}:{target_id}
```

stub node 必须带：

```text
stub = true
stub_reason
created_from_migration_id
```

后续真实数据进入时用同一稳定 ID merge。

## 7. Node 模型

### 7.1 Workspace

代表一个 local workspace。

关键属性：

```text
workspace_id
root_path
created_at
schema_version
privacy_upload_default
```

### 7.2 Provider

代表 session source provider，例如 `codex`。

关键属性：

```text
provider
display_name
```

### 7.3 SourceRef

代表一个本地 source 文件或 source manifest。

关键属性：

```text
provider
source_ref
source_size
source_mtime
source_fingerprint
last_seen_at
source_kind
exists_at_migration
```

### 7.4 Project

按 provider 归一化后的项目维度。

关键属性：

```text
provider
project_key
project_label
```

### 7.5 Session

每条 chat session 的主节点。Session 全量入图。

关键属性：

```text
session_id
provider
title
cwd
project_key
project_label
source_ref
event_count
indexed_event_count
evidence_event_count
discovered_at
first_seen_at
last_seen_at
loaded_at
updated_at
first_user_preview
last_assistant_preview
quality_score
candidate_label
```

`indexed_event_count` 可以来自 legacy `session_events` 或 scanner count，但不代表每个 event 都有 `ChatEventRef`。

### 7.6 ChatEventRef

稀疏 chat 引用节点。只在以下情况创建：

- factor evidence 引用了该 event。
- event 上存在 `TagAssertion`。
- event 被人工 bookmark。
- event 被 cluster explanation 引用。
- legacy event 有 materialized preview，并且需要展示或复查。

关键属性：

```text
event_id
event_index
role
raw_role
chat_role
content_kind
factor_channel
record_type
payload_type
tool_name
source_ref
source_line_start
source_line_end
content_hash
content_preview_redacted
tool_result_hash
tool_result_preview_redacted
locator_json
artifact_locator_json
materialization_reason
completeness
```

`completeness` 取值：

```text
source_resolved
legacy_preview_only
legacy_index_only
stub
```

### 7.7 Factor

代表一个可执行 factor 版本。

关键属性：

```text
factor_id
version
source
enabled
runtime_mode
status
manifest_path
factor_xml_path
```

### 7.8 AnalysisRun

一次 runner 执行。

关键属性：

```text
analysis_run_id
provider
started_at
completed_at
factor_ids_json
result_count
error_count
status
```

### 7.9 FactorResult

一次 factor 对某个 target 的整体结果。

关键属性：

```text
result_run_id
factor_id
factor_version
framework_id
stage
target_type
target_id
status
confidence
verdict_signals_json
scores_json
statistics_json
notes_json
created_at
```

不要把 `FactorResult` 用作“某条 chat 上的某个判断”。那个粒度属于 `TagAssertion` 或 `Finding`。

### 7.10 Tag

规范化 tag 词表节点。

关键属性：

```text
type
value
display_label
namespace
```

例如：

```text
type = user_sentiment
value = dissatisfaction
```

### 7.11 TagAssertion

某个 source 对某个 target 做出的 tag 判断。

关键属性：

```text
assertion_id
tag_type
tag_value
target_node_id
target_type
source_kind
source_factor_id
source_result_run_id
analysis_run_id
confidence
status
created_at
updated_at
reason
```

`TagAssertion` 是可追踪事实，`Tag` 只是标签词表。

### 7.12 Dataset / DatasetRecord

FactorResult 产出的结构化数据。

`Dataset` 属性：

```text
dataset_id
semantic_type
shape
primary_key
schema_json
record_count
evidence_policy_json
records_json
```

P0 可以把 `records_json` 存在 Dataset 属性里。若 records 里有 `event_id`、`evidence_event_id`、`sample_event_ids`，再拆出 `DatasetRecord` 方便证据下钻。

### 7.13 Presentation / Route

用于 report / browser / drawer / dashboard 路由。

`Presentation` 属性：

```text
presentation_id
title
component_ref
data_ref
bindings_json
props_json
fallback_json
priority
```

`Route` 属性：

```text
route_area
route_key
component
title
priority
enabled
```

### 7.14 Cohort

可复用 session 集合。

关键属性：

```text
cohort_id
name
scope_type
scope_key
target_type
filter_cypher
params_json
created_at
refreshed_at
member_count
description
```

示例：`EvoZeus 项目里 user_sentiment=dissatisfaction 的 session`。

### 7.15 FeatureSet

聚类使用的特征定义。

关键属性：

```text
feature_set_id
name
feature_sources_json
weights_json
embedding_model
version
created_at
```

### 7.16 ClusterRun / Cluster

一次聚类运行和聚类结果。

`ClusterRun` 属性：

```text
cluster_run_id
method
created_at
status
input_count
cluster_count
params_json
```

`Cluster` 属性：

```text
cluster_id
label
summary
size
quality_score
created_at
human_review_status
```

## 8. Relationship 模型

基础索引：

```text
Workspace -[:HAS_PROVIDER]-> Provider
Provider -[:DISCOVERED]-> SourceRef
Provider -[:HAS_PROJECT]-> Project
Project -[:HAS_SESSION]-> Session
SourceRef -[:MATERIALIZED_AS]-> Session
Scanner -[:INDEXED]-> SourceRef
Scanner -[:INDEXED_EVENT]-> ChatEventRef
Session -[:HAS_EVIDENCE_EVENT {event_index, materialization_reason}]-> ChatEventRef
ChatEventRef -[:NEXT_EVIDENCE_EVENT]-> ChatEventRef
```

factor 执行：

```text
AnalysisRun -[:ANALYZED]-> Session
Factor -[:RAN_IN]-> AnalysisRun
AnalysisRun -[:PRODUCED]-> FactorResult
FactorResult -[:ABOUT]-> Session|ChatEventRef|TargetStub
Session -[:HAS_FACTOR_STATE]-> Factor
Session -[:LATEST_FACTOR_RESULT]-> FactorResult
```

tag / evidence：

```text
FactorResult -[:USES_EVIDENCE {kind}]-> ChatEventRef
FactorResult -[:EMITTED]-> TagAssertion
TagAssertion -[:ASSERTS]-> Tag
TagAssertion -[:ON]-> Session|ChatEventRef|FactorResult
ChatEventRef -[:TAGGED_AS]-> Tag
Session -[:HAS_TAG_ROLLUP {count, evidence_count, latest_at, confidence_max}]-> Tag
```

dataset / presentation：

```text
FactorResult -[:HAS_DATASET]-> Dataset
Dataset -[:HAS_RECORD]-> DatasetRecord
DatasetRecord -[:EVIDENCES]-> ChatEventRef
FactorResult -[:HAS_PRESENTATION]-> Presentation
Presentation -[:ROUTES_TO]-> Route
Factor -[:ROUTES_TO]-> Route
```

错误：

```text
AnalysisRun -[:FAILED_WITH]-> RunError
RunError -[:ABOUT_FACTOR]-> Factor
```

cohort / cluster：

```text
Cohort -[:INCLUDES {matched_at}]-> Session
ClusterRun -[:INPUT]-> Cohort
ClusterRun -[:USES_FEATURE_SET]-> FeatureSet
ClusterRun -[:PRODUCED]-> Cluster
Cluster -[:HAS_MEMBER {score, rank}]-> Session
Cluster -[:EXPLAINED_BY]-> Tag|ChatEventRef|DatasetRecord|FactorResult
```

## 9. Session 内 chat 如何存在

不使用：

```text
Session -[:HAS_CHAT]-> ChatEvent
```

全量 chat 节点会让 graph 体积快速膨胀，而且很多 context / tool output 对 cohort 查询没有长期价值。

使用：

```text
Session -[:HAS_EVIDENCE_EVENT]-> ChatEventRef
ChatEventRef <-[:ON]- TagAssertion
FactorResult -[:USES_EVIDENCE]-> ChatEventRef
```

即：

- Chat 原始内容在 source JSONL。
- Graph 里只存 `ChatEventRef`。
- `ChatEventRef` 保存定位、hash、类型、preview 和 materialization reason。
- resolver 可按 locator 回源读取完整 event。

Chat 类型归一化：

| 原始类型 | Graph 中的 ChatEventRef |
| --- | --- |
| Codex context / AGENTS / environment | 默认不建节点；如果被 factor 引用则 `content_kind=context` |
| 真实用户消息 | `content_kind=user_message` / `factor_channel=user_input` |
| assistant 回复 | `content_kind=assistant_message` / `factor_channel=assistant_result` |
| tool call | `content_kind=tool_call` / `factor_channel=tool_usage` / `tool_name` |
| tool output | `content_kind=tool_output` / `factor_channel=tool_result` / `tool_name` |
| task_complete | `content_kind=task_complete` / `factor_channel=assistant_result` |
| image / file payload | `content_kind=attachment`，必要时连 `Attachment` 节点 |
| unknown runtime event | `content_kind=runtime_event` |
| malformed JSONL line | 不建 ChatEventRef，建 `SourceIssue` |

## 10. CRUD 设计

### 10.1 Generic Graph API

底层 repository 提供通用图操作：

```python
upsert_node(node_id: str, labels: list[str], props: dict) -> None
upsert_edge(source_id: str, target_id: str, rel_type: str, props: dict) -> None
set_node_property(node_id: str, key: str, value: object, source: str) -> None
set_edge_property(edge_id: str, key: str, value: object, source: str) -> None
delete_node(node_id: str, cascade_policy: str) -> None
delete_edge(source_id: str, target_id: str, rel_type: str | None = None) -> None
query(cypher: str, params: dict | None = None) -> list[dict]
```

所有写入使用稳定 ID + upsert，保证 migration / rerun 幂等。

### 10.2 Scanner Write API

```python
record_source_ref(provider, source_ref, metadata)
record_session_ref(provider, session_id, source_ref, project_key, project_label, metadata)
record_source_issue(provider, session_id, source_ref, issue)
```

scanner `scan` 阶段只写：

- `Provider`
- `SourceRef`
- `Project`
- `Session`
- `Scanner`
- 必要的 source issue

不写全量 `ChatEventRef`。

### 10.3 Factor Run Write API

```python
record_analysis_run(session, factor_ids, status)
record_factor_result(result)
ensure_chat_event_ref(session_id, event_id, locator, metadata, reason)
add_tag_assertion(target_id, tag_type, tag_value, source_result_id, confidence, evidence_ids)
refresh_session_tag_rollup(session_id)
```

规则：

- `FactorResult.evidence_refs` 中出现的 event 必须 `ensure_chat_event_ref`。
- `event_factor_tags` / dataset record 中出现的 event 也必须 `ensure_chat_event_ref`。
- result 级 tag 建 `TagAssertion -[:ON]-> Session|FactorResult`。
- event 级 tag 建 `TagAssertion -[:ON]-> ChatEventRef`。
- 每次 factor 写入后刷新 `Session -[:HAS_TAG_ROLLUP]-> Tag`。

### 10.4 Tag CRUD

```python
create_tag(type, value, display_label="", namespace="")
add_tag_assertion(target_id, type, value, source, confidence, evidence_ids)
update_tag_assertion(assertion_id, status, confidence, reason)
delete_tag_assertion(assertion_id)
refresh_tag_rollup(target_session_id)
```

人工标注和 factor 标注都走 `TagAssertion`，区别在 `source_kind`：

```text
factor
human
migration
import
```

### 10.5 Cohort CRUD

```python
create_cohort(name, target_type, filter_cypher, params, scope)
refresh_cohort(cohort_id)
list_cohort_members(cohort_id)
delete_cohort(cohort_id)
```

示例：EvoZeus 项目里用户不满意情绪的 session。

```cypher
MATCH (:Project {project_label: $project_label})-[:HAS_SESSION]->(s:Session)
MATCH (s)-[:HAS_TAG_ROLLUP]->(:Tag {
  type: "user_sentiment",
  value: "dissatisfaction"
})
RETURN DISTINCT s
```

需要解释命中原因时再下钻：

```cypher
MATCH (s:Session {session_id: $session_id})-[:HAS_EVIDENCE_EVENT]->(e:ChatEventRef)
MATCH (e)<-[:ON]-(a:TagAssertion)-[:ASSERTS]->(t:Tag)
RETURN e, a, t
ORDER BY e.event_index
```

### 10.6 Cluster CRUD

```python
create_feature_set(name, feature_sources, weights, embedding_model="")
create_cluster_run(cohort_id, feature_set_id, method, params)
add_cluster_member(cluster_id, session_id, score, rank)
label_cluster(cluster_id, label, summary, reviewer)
add_cluster_explanation(cluster_id, node_id, rel_type="EXPLAINED_BY")
delete_cluster_run(cluster_run_id)
```

聚类输入来自 `Cohort`，聚类结果回写成 `ClusterRun / Cluster / HAS_MEMBER / EXPLAINED_BY`。

### 10.7 Read API

替代旧 `LedgerRepository` 的查询方法：

```python
list_session_statuses(factor_ids=None)
list_session_events(session_id=None)              # 只返回 sparse ChatEventRef
list_factor_results(session_id)
list_event_factor_tags(session_id=None)
list_sessions_by_tag(project_label, tag_type, tag_value)
list_cohorts()
list_clusters(cohort_id=None)
get_evidence_for_session(session_id)
query(cypher, params)
```

旧 report 如果需要“聊天时间线”，只能展示 sparse evidence timeline；要展示完整原文时间线时必须通过 scanner resolver 回源读取，并经过 permission gate。

## 11. Delete / Cleanup 策略

本地测试数据可以 hard delete，但 repository 必须显式执行级联策略，避免 orphan 节点误导图查询。

删除 Session：

```text
delete Session
delete ChatEventRef only referenced by this Session
delete AnalysisRun / FactorResult under this Session
delete TagAssertion under deleted results/events
delete Dataset / DatasetRecord / Presentation under deleted results
delete Cohort membership and Cluster membership
keep Project / Provider / Factor / Tag
```

删除 FactorResult：

```text
delete FactorResult
delete emitted TagAssertion
delete evidence edges
delete Dataset / DatasetRecord / Presentation
refresh Session tag rollup
```

删除 TagAssertion：

```text
delete TagAssertion
delete Event/Session shortcut rollup if no remaining assertions
keep Tag dictionary node unless orphan cleanup is requested
```

删除 Cohort：

```text
delete Cohort
delete INCLUDES edges
keep Sessions
keep ClusterRun unless delete_with_clusters=true
```

删除 ClusterRun：

```text
delete ClusterRun
delete Cluster nodes produced by it
delete HAS_MEMBER and EXPLAINED_BY edges
keep Cohort / Sessions / TagAssertions
```

## 12. 旧 SQLite 表迁移

迁移原则：

- 先备份旧 DB。
- 尽量从旧表迁完整分析事实。
- session 内 chat 不全量迁成 `ChatEventRef`。
- 只有 referenced / materialized / tagged / evidence / preview 相关 event 迁成 `ChatEventRef`。
- 如果原始 source file 存在，可以用 scanner resolver 补齐 locator、hash、preview。
- 如果 source file 不存在，迁移 legacy index 并标记 `completeness=legacy_index_only` 或 `stub`。

### 12.1 表级映射

| Legacy table | GraphQLite 迁移 |
| --- | --- |
| `schema_meta` | `LedgerMeta` 节点，记录 legacy schema version、migration id、迁移时间 |
| `source_refs` | `SourceRef`；`Provider -[:DISCOVERED]-> SourceRef` |
| `sessions` | `Session`、`Project`；`Project -[:HAS_SESSION]-> Session`；`SourceRef -[:MATERIALIZED_AS]-> Session` |
| `session_events` | 不全量建 node；被 evidence/tag/preview 引用的行建 `ChatEventRef`；其余只汇总到 `Session.indexed_event_count` |
| `analysis_runs` | `AnalysisRun`；`AnalysisRun -[:ANALYZED]-> Session` |
| `factor_results` | `FactorResult`；`AnalysisRun -[:PRODUCED]-> FactorResult`；`FactorResult -[:ABOUT]-> target` |
| `factor_tags` | `Tag` + `TagAssertion`；result 级 assertion 默认 `ON Session` 或 `ON FactorResult` |
| `event_factor_tags` | `ChatEventRef` + `TagAssertion -[:ON]-> ChatEventRef` + `ChatEventRef -[:TAGGED_AS]-> Tag` |
| `factor_evidence` | `FactorResult -[:USES_EVIDENCE]-> ChatEventRef`；event 不存在则建 `EventStub` |
| `factor_datasets` | `Dataset`；有 evidence event 的 record 拆成 `DatasetRecord` 并连 `ChatEventRef` |
| `factor_presentations` | `Presentation`；`Presentation -[:ROUTES_TO]-> Route` |
| `factor_run_index` | `Session -[:HAS_FACTOR_STATE]-> Factor`；有 latest result 时补 `LATEST_FACTOR_RESULT` |
| `factor_result_latest` | `Session/Target -[:LATEST_FACTOR_RESULT]-> FactorResult` |
| `factor_run_errors` | `RunError`；`AnalysisRun -[:FAILED_WITH]-> RunError` |
| `installed_factors` | `Factor` |
| `factor_capabilities` | `Factor -[:SUPPORTS]-> Provider` 和 `Factor -[:SUPPORTS_TARGET]-> TargetType` |
| `factor_result_routes` | `Route`；`Factor -[:ROUTES_TO]-> Route` |

### 12.2 维度完整性

| 维度 | legacy 是否齐全 | GraphQLite 处理 |
| --- | --- | --- |
| Workspace | legacy 没有正式表 | 从 workspace path / config 推断 `Workspace` |
| Provider | 齐 | 从 `sessions.provider`、`source_refs.provider` 建 `Provider` |
| Project | 基本齐 | 从 `sessions.project_key/project_label` 建 `Project` |
| SourceRef | 齐 | 原样建 `SourceRef` |
| Scanner | 部分齐 | 从 event metadata / session metadata 建 `Scanner`，缺失则建 `scanner:unknown` |
| Session | 齐 | 原样建 `Session` |
| ChatEventRef | 不应全量齐 | 只迁 tagged/evidence/materialized event；其他保留 count 和 source locator |
| AnalysisRun | 齐 | 原样建 `AnalysisRun` |
| Factor | 基本齐 | 从 installed_factors 和 factor_results 补齐；缺失建 FactorStub |
| FactorResult | 齐 | 原样建 `FactorResult` |
| Tag | 齐但语义弱 | 迁成 `Tag` + `TagAssertion` |
| Evidence | 基本齐 | 迁成 `USES_EVIDENCE`，缺 event 建 stub |
| Dataset | 齐 | 迁成 Dataset；必要 records 拆节点 |
| Presentation / Route | 齐 | 迁成 Presentation / Route |
| RunError | 齐 | 迁成 RunError |
| Cohort | legacy 没有 | 迁移后由用户或 CLI 创建 |
| Cluster | legacy 没有 | 迁移后由 cluster run 创建 |

### 12.3 迁移顺序

1. `LedgerMeta` / `Workspace`。
2. `Provider` / `Scanner` / `Factor` / `Route`。
3. `SourceRef` / `Project` / `Session`。
4. `AnalysisRun` / `FactorResult` / `RunError`。
5. 从 `factor_evidence`、`event_factor_tags`、dataset records 收集 required event ids。
6. 从 `session_events` 迁 required event ids 为 `ChatEventRef`。
7. 写 `Tag` / `TagAssertion` / `HAS_TAG_ROLLUP`。
8. 写 `Dataset` / `DatasetRecord` / `Presentation`。
9. 写 latest / factor state / capabilities。
10. 校验 count 和抽样 Cypher 查询。

### 12.4 校验

必须校验：

```text
legacy sessions count == graph Session count
legacy source_refs count == graph SourceRef count
legacy factor_results count == graph FactorResult count
legacy analysis_runs count == graph AnalysisRun count
legacy factor_tags count <= graph TagAssertion count
legacy event_factor_tags count == graph event-level TagAssertion count
legacy factor_evidence count == graph USES_EVIDENCE edge count
legacy factor_run_errors count == graph RunError count
```

允许不相等：

```text
legacy session_events count >= graph ChatEventRef count
```

因为新模型明确采用 sparse event graph。

## 13. 查询场景

### 13.1 按 tag 找项目内 session

```cypher
MATCH (:Project {project_label: $project_label})-[:HAS_SESSION]->(s:Session)
MATCH (s)-[:HAS_TAG_ROLLUP]->(:Tag {
  type: $tag_type,
  value: $tag_value
})
RETURN DISTINCT s
ORDER BY s.updated_at DESC
```

### 13.2 下钻 tag evidence

```cypher
MATCH (s:Session {session_id: $session_id})-[:HAS_EVIDENCE_EVENT]->(e:ChatEventRef)
MATCH (e)<-[:ON]-(a:TagAssertion)-[:ASSERTS]->(t:Tag)
RETURN e, a, t
ORDER BY e.event_index
```

### 13.3 找出某个 factor 产生的问题类型

```cypher
MATCH (:Factor {factor_id: $factor_id})-[:RAN_IN]->(:AnalysisRun)-[:PRODUCED]->(r:FactorResult)
MATCH (r)-[:EMITTED]->(:TagAssertion)-[:ASSERTS]->(t:Tag)
RETURN t.type, t.value, count(*) AS count
ORDER BY count DESC
```

### 13.4 创建 cohort 后聚类

cohort filter：

```cypher
MATCH (:Project {project_label: "EvoZeus"})-[:HAS_SESSION]->(s:Session)
MATCH (s)-[:HAS_TAG_ROLLUP]->(:Tag {
  type: "user_sentiment",
  value: "dissatisfaction"
})
RETURN DISTINCT s
```

cluster input:

```cypher
MATCH (:Cohort {cohort_id: $cohort_id})-[:INCLUDES]->(s:Session)
OPTIONAL MATCH (s)-[:HAS_TAG_ROLLUP]->(t:Tag)
OPTIONAL MATCH (s)-[:HAS_EVIDENCE_EVENT]->(e:ChatEventRef)
RETURN s, collect(DISTINCT t) AS tags, collect(DISTINCT e) AS evidence
```

## 14. Permission 与隐私边界

GraphQLite 迁移不改变 infra 的 permission 原则。

写 graph 允许：

- session id
- project key / label
- source locator
- redacted preview
- content hash
- tool result hash
- factor result summary
- tag assertion
- evidence edge

默认不写：

- raw full chat content
- raw full tool output
- secret-like content
- provider private raw payload

需要完整原文时：

```text
ChatEventRef.locator_json
  -> scanner resolver
  -> permission gate
  -> source file
  -> resolved event
```

## 15. Graph projection / 可视化规则

存储 graph 和可视化 graph 必须分开设计。

GraphQLite 内部可以保留 `Tag` 词表节点和 `Session -[:HAS_TAG_ROLLUP]-> Tag` 边，用于查询、聚合、去重和 drilldown。但默认 ReactFlow 可视化不能把高扇出 tag materialize 成节点。

原因：

- `负面情绪`、`工具失败`、`用户不满意` 这类 factor 输出标签可能连接数百到数千个 session。
- 如果把它们画成节点，会形成不可读的 star graph，ReactFlow 也只能忠实渲染噪声。
- 这类信息在用户心智里是 session 的属性 / filter / badge，而不是需要在主图中占位置的实体。

默认 ReactFlow projection：

```text
Factor -> Session -> ChatEventRef
```

`Tag` 不进入默认 nodes / edges，而是写入 `Session.data.tags`：

```text
Session {
  label: session_id,
  tags: ["sentiment:negative", "signal:tool_failure"],
  search: "... sentiment:negative signal:tool_failure ..."
}
```

交互规则：

- 搜索 tag 时，命中带该 tag 的 session 节点。
- session 节点上展示前 3 个 tag badge，剩余用 `+N` 收起。
- 点击 session 后展示邻域：Factor、Evidence、tag badges。
- `Relations` / drilldown 视图可以展示 `Session -> Tag` 关系，但这是审计视图，不是默认 graph projection。
- 只有在 tag 词表管理、tag 合并、tag taxonomy 编辑等场景，才把 `Tag` 作为中心节点单独展开。

因此 schema 允许 `Tag` 是 node，但 visualization projection 默认把 tag 当 node property。这个规则同样适用于 cohort / cluster：高扇出维度默认做 filter/badge/summary，不直接画成中心节点。

## 16. 实施切片

### Slice 1: Graph backend skeleton

- 加 optional dependency `graphqlite`。
- 新增 `GraphLedgerRepository`。
- 新增 node id / edge type helpers。
- 增加最小 CRUD 测试。

### Slice 2: SQLite legacy migration

- 新增 `legacy_sqlite.py` 只读 adapter。
- 新增 `migrate_sqlite_to_graphqlite.py`。
- 实现表级迁移和 count 校验。

### Slice 3: Scanner / runner cutover

- `scan_sessions` 写 GraphQLite。
- `run_factors` 写 GraphQLite。
- 保留旧 repository 只用于 migration tests。

### Slice 4: Report / browser cutover

- `generate_ledger_browser` 从 GraphQLite 读。
- UI 改名为 Graph Ledger Browser。
- 默认 ReactFlow 图展示 `Factor -> Session -> ChatEventRef`。
- tag rollup 展示为 session badge / filter，不在默认 graph projection 中 materialize 成节点。
- `Relations` / drilldown 视图保留 `Session -> Tag` 审计关系。
- 展示 session、tag rollup、evidence event、factor result、cohort、cluster。

### Slice 5: Cohort / cluster

- 增加 cohort CRUD。
- 增加 cluster run artifact。
- P0 cluster feature 可以先用共享 tag / evidence / factor statistics，不必立即引入 embedding。

## 17. 需要后续决策

1. `results.sqlite3` 是否直接原地替换，还是长期保留 `results.graph.sqlite3` 文件名。
2. GraphQLite 是否作为 hard dependency，还是先放 optional dependency。
3. `content_preview_redacted` 的最大长度。
4. Dataset records 是全部拆节点，还是只拆含 evidence/event id 的 records。
5. Cluster P0 使用 rule-based similarity、GraphQLite algorithm，还是 embedding-based similarity。

当前建议：

- 文件名最终保留 `results.sqlite3`。
- GraphQLite 先作为 `graph` optional dependency，但 GraphQLite ledger 分支运行时 hard require。
- `ChatEventRef` preview 保持短文本，仅用于解释和 report。
- Dataset 只拆 evidence-aware records。
- Cluster P0 先用 tag/factor/evidence similarity，后续再加 embedding。
