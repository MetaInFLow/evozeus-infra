# evozeus-runtime

EvoZeus local scanner / runner runtime。

本 repo 负责扫描本地 session、标准化为 `SessionEnvelope`、运行 selected Factor、写入本地 ledger，并生成 Markdown / JSON / HTML report。

它不是默认上传工具，不是 Factor marketplace，不是未审 Factor 的安装源，也不承接 EvoZeus 主 repo 的 protocol / governance / registry pointer 语义。

## P0 Scope

- Codex local session scanner。
- `SessionEnvelope` / `SessionEvent` schema。
- `FactorPack` loader。
- `FactorRunner`。
- in-process 和 subprocess Factor runtime strategy。
- SQLite local ledger。
- Markdown / JSON / HTML report。
- Permission gate for local reads, writes, commands, env, and network。
- Official Factor release metadata 的 checksum / attestation / compatibility verifier。

## Non-goals

- 不默认全盘扫描。
- 不默认联网。
- 不默认上传 raw session。
- 不直接安装 lab branch 或未审 Factor。
- 不把 JS 作为 core runtime。
- P0 不做完整 TUI / companion / GUI。

## Architecture

```text
Local session source
  -> Scanner Adapter + Registry
  -> SessionEnvelope
  -> FactorPack Repository + Manifest Verifier
  -> FactorRunner
  -> Runtime Strategy
  -> SQLite Ledger
  -> Markdown / JSON / HTML Report
```

Scanner 层按不同本地应用拆成 provider adapter。Codex、Claude Code、Cursor、Feishu 等本地 session 格式不应进入 runner、ledger 或 factor；每个 scanner 只负责 discover / load / normalize 自己的 provider，并统一输出 `SessionEnvelope`。P0 内置 `CodexScanner`，后续 provider 放在 `src/evozeus_runtime/scanners/providers/` 并注册到 default scanner registry。

Scanner 原则：

- `scan` 阶段只发现并记录 `session_id` 和 `message_id`，不把 message content、tool output 或 preview 写入 SQLite。
- `sessions` 必须保存 `project_key` 和 `project_label`，用于按项目列出 chat records。
- SQLite 的 `session_events` 在 scan 后是 message id index，用于把后续 Factor evidence、tags、results 挂回对应 message。
- `load` 阶段才从 provider 原始 session materialize `SessionEnvelope`，并且必须通过 event generator 渐进式读取。
- Scanner adapter 必须声明将读取的 `source_dirs()`，permission gate 在读取前做检查。

核心设计模式：

| Area | Pattern |
| --- | --- |
| Scanner | Abstract Base Class + Adapter + Registry |
| Factor | Abstract Base Class + Template Method |
| Runner | Serial Pipeline |
| Runtime | Strategy / Resolver |
| Ledger | Repository Pattern |
| Report | Renderer functions over ledger results |

## Commands

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m evozeus_runtime.cli.main status
```

Installed console script:

```bash
evozeus-runtime status
evozeus-runtime scan --provider codex --workspace /tmp/evozeus-workspace
evozeus-runtime scan --provider codex --source tests/fixtures/codex_sessions --workspace /tmp/evozeus-workspace
evozeus-runtime run --session-id session-minimal --factor default.tool_failure --pack-root tests/fixtures/factor_packs --workspace /tmp/evozeus-workspace
evozeus-runtime report --session-id session-minimal --format markdown --format json --format html --workspace /tmp/evozeus-workspace
evozeus-runtime migrate-ledger --workspace /tmp/evozeus-workspace
evozeus-runtime graph-browser --workspace /tmp/evozeus-workspace
```

Repository scripts:

```bash
python scripts/run_scanner.py --provider codex --workspace /tmp/evozeus-workspace
python scripts/run_scanner.py --provider codex --source tests/fixtures/codex_sessions --workspace /tmp/evozeus-workspace
python scripts/run_runner.py --session-id session-minimal --factor default.tool_failure --pack-root tests/fixtures/factor_packs --workspace /tmp/evozeus-workspace
python scripts/render_sqlite_html.py --workspace /tmp/evozeus-workspace
python scripts/migrate_sqlite_to_graphqlite.py --workspace /tmp/evozeus-workspace
python scripts/render_graphqlite_html.py --workspace /tmp/evozeus-workspace
```

不传 `--source` 时，`codex` provider 默认扫描 `~/.codex/sessions` 和 `~/.codex/archived_sessions`。显式传 `--source` 适合测试 fixture 或受控目录。
不传 `--workspace` 时，ledger 和 report 默认写入当前工作目录下的 `.evozeus/`；需要放到别处时显式传 `--workspace /path/to/workspace`。
`render_sqlite_html.py` 只读取该 workspace 下的 `.evozeus/runtime/index/results.sqlite3`，生成静态 HTML 可视化，不会重新扫描原始 session。
`migrate_sqlite_to_graphqlite.py` 按 `docs/design/graphqlite-sparse-evidence-ledger-design.md` 把 legacy SQLite ledger 迁到 `.evozeus/runtime/index/results.graph.sqlite3`，并把原始 `results.sqlite3` 备份为 `results.sqlite3.legacy`。Graph ledger 分支运行时 hard require `graphqlite`；未安装时会明确提示安装，不 silent fallback。
`render_graphqlite_html.py` 只读取 GraphQLite graph ledger，生成 `.evozeus/runtime/reports/evozeus-graph.html`，用于查看 node / edge 分布、project、tag、factor、evidence 抽样和本地关系图。

## Directory Map

| Path | Purpose |
| --- | --- |
| `src/evozeus_runtime/scanners/` | Provider scanner adapters and registry |
| `src/evozeus_runtime/sessions/` | Session schema and source locators |
| `src/evozeus_runtime/factors/` | Factor schema, manifests, pack loading |
| `src/evozeus_runtime/runner/` | Factor runner and runtime strategies |
| `src/evozeus_runtime/ledger/` | SQLite legacy ledger、Graph ledger repository 和迁移工具 |
| `src/evozeus_runtime/reports/` | Markdown / JSON / HTML report renderers |
| `src/evozeus_runtime/policy/` | Permission gate |
| `src/evozeus_runtime/registry/` | Official release metadata verifier |
| `scripts/` | Direct scanner / runner helper scripts |
| `tests/fixtures/` | Contract fixtures for scanner and Factor packs |
| `docs/design/` | Active design docs |
| `docs/implementation/` | Active implementation plans |
| `docs/archive/` | Historical migration notes |

## Trust Contract

- Local-first。
- Upload off by default。
- Network off unless explicitly enabled。
- External commands off unless explicitly enabled。
- Factors are explicit-selection only。
- Official Factor assets require release metadata, checksum, attestation, compatibility, and promoted review state before install / execution.
