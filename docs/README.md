# Infra Docs

本目录承接从 `EvoZeus` 主 repo 移出的 infra 设计和实施材料。

`EvoZeus` 主 repo 现在只保留 protocol、governance、registry pointer 和贡献路由；CLI、TUI、local registry、scanner execution、Factor execution、report generation、`.evozeus/` state、lockfile 和 local API 都属于本 repo。

## Current Docs

| Document | Purpose |
| --- | --- |
| [factor-runtime-isolation.md](factor-runtime-isolation.md) | Factor runtime isolation、dependency boundary、subprocess/container/remote runtime 设计 |
| [local-analysis-ledger-bootstrap.md](local-analysis-ledger-bootstrap.md) | Local Analysis Ledger、workspace bootstrap、SQLite ledger、TUI / companion shared state 设计 |
| [local-analysis-ledger-bootstrap-implementation.md](local-analysis-ledger-bootstrap-implementation.md) | 从旧 main-repo runtime prototype 迁出的实施计划和任务拆解 |
| [main-repo-cleanup-intake.md](main-repo-cleanup-intake.md) | 主 repo 清理后 infra / scanner / factor execution 的承接边界 |

## Prototypes

| Path | Purpose |
| --- | --- |
| `../prototypes/main-repo-runtime/` | 从 `EvoZeus` 主 repo 移出的 Python runtime prototype，包含 scanner、Factor runner、storage、report、TUI / companion 和原测试上下文 |

## Migration Note

这些文档中出现的旧 `__infra__/...` 路径来自 `EvoZeus` 主 repo 的 historical prototype。该目录已经不再属于主 repo 结构；对应 prototype 已承接到 `prototypes/main-repo-runtime/`。继续实现时应在本 repo 建立当前 infra 路径，而不是把执行层加回主 repo。

Factor pack 和 scanner module 的生命周期仍按 repo 边界处理：

```text
EvoZeus main registry pointer
  -> evozeus-factor-lab review
  -> evozeus-factors-official release unit
  -> evozeus-infra selective install / execution
```
