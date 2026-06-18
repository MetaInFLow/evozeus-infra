# Factor Runtime Isolation 设计文档

- Status: Draft
- Owner: EvoZeus Core
- Last updated: 2026-06-16

> Migration note: 本文已从 `EvoZeus` 主 repo 移入 `evozeus-infra`。旧文中的 main-repo prototype 路径只作为历史设计线索；新的 infra implementation 应落在本 repo，不应把执行层加回 `EvoZeus` 主 repo。

## 背景

EvoZeus 的因子库会像 Skill 一样被下载、安装、删除和升级。随着因子数量增加，不同因子可能依赖不同版本的 Python 库，例如 `numpy`、`pydantic`、`paddle`、`torch`、浏览器自动化库等。

当前基础实现中，factor 通过 Python import 进入主进程运行。这适合轻量规则因子，但无法承载复杂依赖场景。一个 factor 的依赖升级可能影响整个 infra 主进程，甚至影响其他 factor 的运行结果。

因此需要定义一套 factor runtime isolation 机制，让因子库可以独立演进，同时保持统一输入输出协议。

## 目标

1. 支持轻量 factor 快速运行。
2. 支持有独立 Python 依赖的 factor。
3. factor 可以按文件夹下载、安装、删除、升级。
4. 主进程环境保持稳定，不被 factor 第三方依赖污染。
5. factor 输出统一为 `FactorResult`。
6. 安装失败、依赖冲突、运行超时都返回结构化诊断。
7. 为未来 container / remote runtime 预留扩展点。

## 非目标

P0 不默认支持 Docker runtime。

P0 不处理远程 factor 执行。

P0 不允许 factor 直接修改主进程状态。

P0 不把重依赖模型类 factor 作为默认安装内容。

## 核心原则

### 1. 协议统一

所有 factor 无论运行在哪里，都接收统一的 `SessionEnvelope`，输出统一的 `FactorResult`。

### 2. 运行环境分层

轻量 factor 使用主进程 `in_process` runtime。

有第三方依赖的 factor 使用独立 `subprocess_uv` runtime。

重依赖或高风险 factor 后续进入 `container` / `remote` runtime。

### 3. 安装单元是 factor folder

每个 factor 是一个独立目录。删除目录即可删除 factor。升级时新增 version 目录。

### 4. 依赖必须 lock

带第三方依赖的 factor 必须提供 lock file，避免运行结果随时间漂移。

## Runtime 分层

| Runtime | 适用场景 | 运行方式 |
| --- | --- | --- |
| `in_process` | 文本规则、统计、轻量 tag | 主进程 import |
| `subprocess_uv` | 有第三方 Python 依赖 | 独立 subprocess，依赖环境由 `uv` 管理 |
| `container` | Paddle、Torch、浏览器、大模型本地推理 | 预留 |
| `remote` | 云端重计算、社区托管因子 | 预留 |

P0 实现范围：

- `in_process`
- `subprocess_uv` 执行协议、timeout、结果校验、依赖声明校验

P0 后续补齐：

- `uv` 安装 cache
- per-factor `.venv` 的复用策略
- runtime index

## Factor Pack 目录规范

```text
.evozeus/infra/factors/installed/<factor_id>/<version>/
  factor.json
  FACTOR.xml
  factor.py
  pyproject.toml
  uv.lock
  .venv/
```

轻量 factor 示例：

```text
.evozeus/infra/factors/installed/default.tool_failure/0.1.0/
  factor.json
  FACTOR.xml
  factor.py
```

带依赖 factor 示例：

```text
.evozeus/infra/factors/installed/vision.ocr/0.1.0/
  factor.json
  FACTOR.xml
  factor.py
  pyproject.toml
  uv.lock
  .venv/
```

## Manifest 规范

`factor.json` 需要声明运行模式、依赖文件、兼容性和权限。

```json
{
  "schema_version": "factor.v0",
  "id": "vision.ocr",
  "version": "0.1.0",
  "name": "vision-ocr",
  "framework_id": "agent_session_review.v0",
  "stage": "signal_extraction",
  "runtime_profile": "community",
  "runtime": {
    "mode": "subprocess_uv",
    "python": ">=3.11,<3.13",
    "dependency_file": "pyproject.toml",
    "lock_file": "uv.lock",
    "timeout_ms": 30000
  },
  "compatibility": {
    "evozeus_sdk": ">=0.1,<0.2"
  },
  "permissions": ["read_session_events"],
  "network": false,
  "entrypoint": "factor:VisionOcrFactor",
  "rollback": "delete this factor folder or disable it in local config"
}
```

`FACTOR.xml` 提供固定介绍，供真人用户、Agent 和本地 TUI 读取。它不承载执行配置和可视化组件配置，必须和 `factor.json` 的 id、version、stage、runtime 保持一致。

```xml
<?xml version="1.0" encoding="UTF-8"?>
<factor id="vision.ocr" version="0.1.0">
  <name>vision-ocr</name>
  <summary>从截图或图片附件中抽取 OCR 文本信号。</summary>
  <category>vision-signal</category>
  <stage>signal_extraction</stage>
  <runtime>subprocess_uv</runtime>
  <inputs>
    <input>session.events</input>
    <input>attachment.image</input>
  </inputs>
  <outputs>
    <output>tag</output>
    <output>score</output>
    <output>evidence_ref</output>
  </outputs>
  <when_to_use>当任务复盘需要理解截图、图片附件或视觉工具输出时使用。</when_to_use>
  <limitations>OCR 质量受图片清晰度、语言和模型依赖影响。</limitations>
  <privacy>只读取经过 PII redaction 的 SessionEnvelope 和授权附件。</privacy>
</factor>
```

报告层负责结果集合的可视化。P0 生成 React + Ant Design 本地 dashboard，包含 summary statistics、词云、factor result matrix 和 result cards。后续 TUI 或浏览器 companion 可以基于同一组 `ResultVisualization` 数据替换成 richer component。

## 安装流程

1. 用户或 Agent 下载 factor folder。
2. Runtime 读取 `factor.json` 和 `FACTOR.xml`。
3. 校验 `schema_version`、`id`、`version`、`runtime.mode`。
4. 校验 `FACTOR.xml` 和 `factor.json` 的 id、version、stage、runtime 一致。
5. 检查是否兼容当前 EvoZeus SDK。
6. 如果是 `in_process`，注册 factor。
7. 如果是 `subprocess_uv`，检查 `.venv`。
8. `.venv` 不存在时，用 `uv` 创建环境并安装 lock 依赖。
9. 安装结果写入本地 runtime index。

## 运行流程

```text
SessionEnvelope
  -> FactorRunner
  -> RuntimeResolver
  -> in_process / subprocess_uv
  -> FactorResult
  -> SQLiteResultStore
  -> Markdown report / HTML report
```

`subprocess_uv` 的运行方式：

1. 主进程选择 factor pack。
2. 将 `SessionEnvelope` 序列化后传入 subprocess。
3. subprocess 加载 `factor.py`。
4. factor 执行并返回 `FactorResult`。
5. 主进程校验结果 schema。
6. 写入本地 SQLite result index。
7. 按需生成 Markdown / HTML report。

## 错误处理

| 场景 | 处理方式 |
| --- | --- |
| manifest 缺字段 | 安装失败，返回 schema error |
| Python 版本不兼容 | 安装失败，提示所需版本 |
| lock 安装失败 | 安装失败，记录依赖错误 |
| factor 运行超时 | 返回 timeout error，不中断其他 factor |
| factor 输出非法 | 返回 invalid result error |
| factor 抛异常 | 记录 factor error，继续跑其他 factor |

## 安全与隐私

PII redaction 发生在 factor 运行前。

默认 factor 只能读取经过标准化的 `SessionEnvelope`。

`network=false` 的 factor 不允许主动访问网络。P0 先记录权限声明，后续通过 sandbox 或 runtime policy 执行。

未来可增加权限声明：

```json
{
  "permissions": [
    "read_session_events",
    "read_redacted_content",
    "write_local_cache"
  ]
}
```

## 测试要求

每个 factor pack 必须有 contract test：

1. 输入固定 `SessionEnvelope`。
2. 跑 factor。
3. 校验输出是合法 `FactorResult`。
4. 校验 evidence ref 指向存在的 event。
5. 校验 factor 失败时不会中断 runner。

P0 测试集需要覆盖：

- 多个 Codex session 扫描。
- flat JSONL 输入。
- archived wrapper JSONL 输入。
- `function_call` / `function_call_output` 标准化。
- in-process factor。
- subprocess factor。
- factor 安装失败。
- factor 超时。
- factor 输出非法。

## 开发计划

### Phase 1: Factor Pack 基础

- factor folder 规范
- `factor.json`
- `FACTOR.xml`
- `FactorPackRepository`
- 默认 8 个 factor pack 示例
- 测试集

### Phase 2: Subprocess Runtime

- `RuntimeResolver`
- `SubprocessUvRuntime`
- stdin/stdout 协议
- timeout
- result schema 校验

### Phase 3: Dependency Installer

- `uv` 环境创建
- per-factor `.venv`
- lock file 安装
- install cache
- 安装失败诊断

### Phase 4: Runtime Index

- 已安装 factor index
- factor enable / disable
- version selection
- rollback

### Phase 5: Heavy Runtime 预留

- container manifest 字段
- resource limit 字段
- remote runtime 字段

## 推荐默认策略

P0 默认启用 `in_process` factor。

用户主动下载带依赖 factor 时，才触发 `subprocess_uv` 安装。

系统不默认安装重依赖 factor。

Agent 可以提示：

> 某某场景下你一直在纠偏同类问题，可能需要安装某个场景下的 factor pack。

## 当前实现状态

- 旧 `prototypes/main-repo-runtime/__infra__` 已实现：`FactorRuntimeConfig`、`runtime.mode` manifest 字段、`RuntimeResolver`、`SubprocessUvRuntime`、`subprocess_worker`、timeout、非法输出校验、依赖声明文件校验。
- 旧 prototype 已实现：`FactorRunner` 可同时运行 `Factor` 实例和 `FactorPack`。
- 旧 prototype 已实现：默认 8 个 factor pack 显式声明 `runtime.mode=in_process`。
- 当前 active JS infra 只提供 component probe、install plan gate 和轻量 factor runner smoke；`subprocess_uv`、timeout、错误隔离和 result schema validation 尚未迁移为 active implementation。
- 待实现：完整 `uv` install cache、runtime index、container / remote runtime。

核心决策：主程序负责协议和调度，因子库作为独立能力包演进；轻量因子直接运行，复杂因子隔离运行。
