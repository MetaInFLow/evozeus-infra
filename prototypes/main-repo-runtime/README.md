# Main Repo Runtime Prototype

- Status: migrated prototype
- Source: former `EvoZeus` main repo execution layer
- Migrated: 2026-06-18

本目录承接从 `EvoZeus` 主 repo 清理出来的旧 Python runtime prototype。它保留 scanner、Factor runner、local storage、report generation、TUI / companion 和原测试上下文，用作 runtime implementation 的迁移素材。

这不是默认用户入口，不是 installable release，也不是 official Factor pack source。

## What Is Here

| Path | Contents |
| --- | --- |
| `__infra__/src/evozeus/scanners/` | scanner contracts, registry, Codex provider prototype, source resolver |
| `__infra__/src/evozeus/factors/` | Factor manifest, registry, runner, subprocess runtime, default factor helpers |
| `__infra__/src/evozeus/runtime/` | runtime path and analysis service prototype |
| `__infra__/src/evozeus/storage/` | SQLite result store and file repository prototype |
| `__infra__/src/evozeus/reports/` | Markdown / HTML report prototype |
| `__infra__/scanner_packs/` | old bundled scanner pack examples |
| `__infra__/factor_packs/` | old bundled default factor examples |
| `__infra__/tests/` | original prototype tests |
| `pyproject.toml` | original Python package/test configuration |

## Boundary

Runtime owns scanner execution, factor runner execution, local state, lockfile, report generation, and permission gates.

Factor Lab owns review of draft scanner modules and Factor packs.

Official Factors owns promoted immutable release units.

The old pack examples in this prototype are not automatically reviewed or official. To make any pack consumable:

```text
prototype reference
  -> evozeus-factor-lab/submissions
  -> evozeus-factor-lab/reviewed
  -> evozeus-factors-official release unit
  -> EvoZeus main registry pointer
  -> runtime selective install
```

## Rebuild Rule

When converting prototype code into active runtime code, first declare:

- files read
- files written
- environment variables read
- external commands
- network behavior
- dependencies and licenses
- sandbox boundary
- rollback path

Do not copy prototype code into an active runtime path without rechecking those gates.
