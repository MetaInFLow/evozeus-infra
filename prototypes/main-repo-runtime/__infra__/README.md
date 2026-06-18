# __infra__

- Status: migration-source prototype
- Last updated: 2026-06-16

`__infra__/` 是 EvoZeus 早期 Skill as Software runtime prototype，存放 Python runtime、业务模型、scanner framework、factor framework、TUI、companion 和自动化测试。

## Migration Notice

`EvoZeus` 主 repo 当前采用 Protocol-only 目标职责。`__infra__/` 只作为待迁移 prototype / reference material，不是默认用户入口、安装源或 official runtime contract。

后续执行层应迁到 `evozeus-runtime`；installable Factor pack、scanner pack 和 resolver 资产应走 `evozeus-factor-lab` -> `evozeus-factors-official` -> `EvoZeus` registry pointer 生命周期。

不要在主 repo 中继续扩展 `__infra__` 作为新的 runtime 产品面。任何需要读取本地文件、写 `.evozeus/` state、维护 SQLite ledger、运行 scanner、安装 pack、生成 report 或暴露 local API 的新增工作，都应路由到 `evozeus-runtime` 或 Factor lifecycle repo。

## Scope

| Path | Responsibility |
| --- | --- |
| `src/evozeus/` | Python package and runtime business logic |
| `src/evozeus/core/` | SessionEnvelope 等核心数据结构 |
| `src/evozeus/scanners/` | 多厂商 session scanner adapter 和 registry |
| `src/evozeus/factors/` | Factor manifest、抽象基类、registry、runner 和 result contract |
| `src/evozeus/runtime/` | `.evozeus/runtime` 下载资产和本地状态路径 |
| `src/evozeus/storage/` | session、event、factor result 的持久化 adapter |
| `scanner_packs/` | 默认 scanner pack 示例，每个 provider 一个独立目录，携带 resolver、脚本和 Agent 使用说明 |
| `factor_packs/` | 默认 factor pack 示例，每个 factor 一个独立目录，便于下载、替换和删除 |
| `testdata/` | 固定测试集，覆盖 Codex flat JSONL 和 archived wrapper JSONL 两类输入 |
| `scripts/` | session 扫描、factor 扫描、指定 factor 运行和 session report 生成脚本 |
| `tests/` | Python tests for runtime behavior |

## Runtime Asset Layout

用户下载的 scanner 和 factor pack 放在本地 runtime，不进入主代码目录：

```text
.evozeus/
  runtime/
    scanners/
      installed/<provider>/<version>/
    factors/
      installed/<factor_id>/<version>/
    index/
      results.sqlite3
  sessions/<session_id>/
    session-envelope.json
    events.jsonl
    factor-results.md
    factor-results.html
```

主代码只负责框架、协议、runner 和 storage。下载资产由 manifest 描述，由 registry 选择，由 runner 执行。

## Scanner Pack Layout

Scanner pack 以 provider/version 文件夹为最小安装单元：

```text
scanner_packs/
  <scanner_id>/
    <version>/
      scanner.json
      SCANNER.xml
      SKILL.md
      scanner.py
      resolver.py
      scripts/
        resolve_event_source.py
```

SQLite result index 只保存 `scanner_id`、`scanner_version`、`source_ref`、fingerprint、locator envelope 和 redacted preview。如何把这些字段还原到 provider 原始 event，由对应 scanner pack 的 `resolver.py`、脚本和 `SKILL.md` 负责。

## Factor Pack Layout

Factor pack 以文件夹为最小安装单元：

```text
factor_packs/
  <factor_id>/
    <version>/
      factor.json
      FACTOR.xml
      factor.py
```

`factor.json` 声明 id、version、stage、runtime profile、entrypoint、输入输出和回滚方式。`FACTOR.xml` 提供固定介绍，给真人用户和 Agent 读取，包括用途、输入输出、适用场景、限制和隐私边界。`factor.py` 只实现该 factor 的运行逻辑。删除一个 factor 时，删除对应 `<factor_id>/<version>/` 文件夹即可。

Repository 扫描 factor 时会同时读取 `factor.json` 和 `FACTOR.xml`，并校验二者的 id、version、stage 和 runtime 一致。

SQLite result index 会记录扫描到的 session、每个 session 的 events、analysis run、factor result、tags、evidence refs，以及 event -> factor tag 的最新映射。它用于增量分析、跨 session 查询和 dashboard 聚合。

HTML report 会把指定的 `FactorResult` 拼到同一个 `factor-results.html`。页面使用 React + Ant Design CDN 渲染本地 dashboard，包含 summary statistics、词云、factor result matrix 和 result cards。可视化由 report layer 生成，例如词云会读取 selected results 的 tags、verdict signals，并保留 factor 来源用于追溯。

## Factor Runtime

Factor pack 通过 `factor.json` 的 `runtime.mode` 选择运行方式：

| Mode | Use Case | Behavior |
| --- | --- | --- |
| `in_process` | 默认轻量规则因子 | 主进程 import 并执行 |
| `subprocess_uv` | 需要隔离的 Python 因子 | 通过 subprocess 执行，stdin 接收 `SessionEnvelope`，stdout 返回 `FactorResult` |
| `container` | 重依赖、高风险因子 | 预留 |
| `remote` | 云端或社区托管因子 | 预留 |

当前代码已支持 `in_process` 和 `subprocess_uv` 的执行路由、timeout、结果 schema 校验和依赖声明校验。完整设计见 `docs/design/active/factor-runtime-isolation.md`。

当前默认示例：

| Factor | Purpose |
| --- | --- |
| `default.negative_feedback` | 识别用户纠偏、负反馈和返工信号 |
| `default.open_loop` | 识别后续确认、blocked、TODO 等未闭环信号 |
| `default.repeated_user_requests` | 识别同一目标上的重复用户请求 |
| `default.same_target_rework` | 识别同一目标上的重复修正 |
| `default.success_closure_quality` | 评估闭环质量，结合未闭环、工具失败、纠偏和验证语言 |
| `default.task_span_extraction` | 抽取轻量 task span、任务类型和开闭状态 |
| `default.tool_failure` | 识别工具调用失败、timeout、traceback 等环境问题 |
| `default.user_correction_loop` | 识别多轮用户纠偏循环 |

## Test Dataset

`testdata/codex_sessions/` 固定保留小型 session 样例：

- flat JSONL：直接包含 `role/content/tool_result`。
- archived wrapper JSONL：包含 `type/payload`，覆盖 `session_meta`、`response_item`、`event_msg`、`function_call` 和 `function_call_output`。

这些样例用于验证 scanner 能输出统一的 `SessionEnvelope`，factor pack 能基于统一事件格式运行。

## Design Patterns

| Area | Pattern | Reason |
| --- | --- | --- |
| Scanner | Adapter + Registry | Codex、Claude Code、Cursor 等厂商输入格式不同，统一输出 `SessionEnvelope` |
| Factor | Abstract Base Class + Template Method | 每个 factor 只实现 `run()`，通用校验、错误隔离和结果规范由框架处理 |
| Runner | Serial Pipeline | P0 优先可复现和可调试，同一 stage 内并发放到后续版本 |
| Storage | Repository Pattern | SQLite index 负责结构化查询，Markdown/HTML 负责 Agent 和真人阅读 |

## Boundary

- 根目录保留 README、SKILL、docs、cases、factors、patterns 和治理入口。
- `__infra__` 不存放公开案例库、文档叙事或社区治理规则。
- 本地运行产物仍写入 `.evozeus/`，不写入 `__infra__`。

## Run

From repository root:

```bash
python -m pytest
evozeus status
```

Smoke checks:

```bash
PYTHONPATH=__infra__/src python __infra__/scripts/scan_sessions_smoke.py --source __infra__/testdata/codex_sessions --min-sessions 4
PYTHONPATH=__infra__/src python __infra__/scripts/scan_factors_smoke.py --pack-root __infra__/factor_packs
PYTHONPATH=__infra__/src python __infra__/scripts/run_factor_smoke.py default.tool_failure --pack-root __infra__/factor_packs --source __infra__/testdata/codex_sessions
PYTHONPATH=__infra__/src python __infra__/scripts/result_report_smoke.py
```

Generate a report for one scanned session with selected factors:

```bash
PYTHONPATH=__infra__/src python __infra__/scripts/run_session_report.py \
  --source __infra__/testdata/codex_sessions \
  --pack-root __infra__/factor_packs \
  --workspace . \
  --factor default.tool_failure \
  --factor default.open_loop
```

This writes:

```text
.evozeus/runtime/index/results.sqlite3
.evozeus/sessions/<session_id>/factor-results.md
.evozeus/sessions/<session_id>/factor-results.html
```
