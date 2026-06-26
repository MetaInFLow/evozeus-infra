# EvoZeus Runtime Docs

本目录保存 `evozeus-runtime` 的 active design、implementation plan 和历史迁移材料。

## Active Docs

| Document | Purpose |
| --- | --- |
| [design/scanner-runner-runtime-design.md](design/scanner-runner-runtime-design.md) | Scanner / runner runtime 目标架构、语言决策、模块边界和 C4 图 |
| [design/graphqlite-sparse-evidence-ledger-design.md](design/graphqlite-sparse-evidence-ledger-design.md) | GraphQLite-first sparse evidence ledger、CRUD、历史 SQLite 迁移、cohort / cluster 总体方案 |
| [scanner-runner-tutorial.md](scanner-runner-tutorial.md) | 面向非开发者的 scanner / runner 入门教程和概念解释 |
| [scanner-runner-script-concepts.md](scanner-runner-script-concepts.md) | 当前 scanner / runner 脚本范围内的一等概念、SQLite 字段和数据流 |
| [implementation/scanner-runner-runtime-implementation.md](implementation/scanner-runner-runtime-implementation.md) | 从旧 infra shell / prototype 迁移到正式 Python runtime 的实施计划 |
| [factor-runtime-isolation.md](factor-runtime-isolation.md) | Factor runtime isolation、dependency boundary、subprocess/container/remote runtime 设计 |
| [local-analysis-ledger-bootstrap.md](local-analysis-ledger-bootstrap.md) | Local Analysis Ledger、workspace bootstrap、SQLite ledger 设计 |

## Archive

| Document | Purpose |
| --- | --- |
| [archive/main-repo-cleanup-intake.md](archive/main-repo-cleanup-intake.md) | 旧主 repo 清理后的历史承接说明 |
| [archive/local-analysis-ledger-bootstrap-implementation.md](archive/local-analysis-ledger-bootstrap-implementation.md) | 旧 prototype 迁移前的历史实施计划 |

## Current Boundary

`evozeus-runtime` 只负责本地 scanner / runner runtime：

```text
local session source
  -> Scanner Adapter
  -> SessionEnvelope
  -> FactorRunner
  -> SQLite Ledger
  -> Markdown / JSON / HTML Report
```

Factor pack 和 scanner module 的生命周期仍按 repo 边界处理：

```text
EvoZeus main registry pointer
  -> evozeus-factor-lab review
  -> future official Factor release mechanism
  -> evozeus-runtime selective local execution
```

`evozeus-session-signal-skill` 只承载 Session Signal SKILL 和 official review factor tools，不是 Factor pack release unit。
