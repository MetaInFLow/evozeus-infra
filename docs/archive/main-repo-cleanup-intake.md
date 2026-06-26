# Main Repo Cleanup Intake

- Status: active routing note
- Last updated: 2026-06-18

本文记录 `EvoZeus` 主 repo 清理执行层遗留结构后，本 repo 当前承接的内容和后续落点。

## 已承接内容

| Source from main repo | Current infra location | State |
| --- | --- | --- |
| Factor runtime isolation design | `docs/factor-runtime-isolation.md` | migrated design doc |
| Local Analysis Ledger design | `docs/local-analysis-ledger-bootstrap.md` | migrated design doc |
| Local Analysis Ledger implementation plan | `docs/local-analysis-ledger-bootstrap-implementation.md` | migrated historical plan |
| Python runtime prototype with scanner / factor runner / storage / reports | `prototypes/main-repo-runtime/` | migrated prototype, not default infra |
| Infra trust policy, component probes, and doctor | `SKILL.md`, `README.md`, `src/infra.mjs`, `scripts/evozeus-infra-doctor.mjs`, `tests/` | active shell |

## Prototype Handling

旧主 repo 的 Python runtime prototype 已作为非默认迁移素材进入 `prototypes/main-repo-runtime/`。它承接 scanner contracts、scanner provider prototype、Factor runner、local storage、report generation、TUI / companion 和测试上下文。

它没有成为 installable infra，也没有绕过 lab / official release gate。后续如果要把这些能力重建为 active infra code，必须按当前 infra contract 重新声明：

- file reads and writes
- `.evozeus/` state
- environment variables
- external commands
- network access
- scanner sandbox
- dependency and license review
- rollback path

## Asset Routes

| Asset kind | Target repo |
| --- | --- |
| CLI / TUI / companion / local API | `evozeus-infra` |
| local registry / lockfile / `.evozeus/infra` state | `evozeus-infra` |
| scanner execution / sandbox | `evozeus-infra` after lab / official metadata |
| factor runner implementation | `evozeus-infra` |
| draft Factor pack or scanner module | `evozeus-factor-lab` |
| Session Signal SKILL / official review factor tools | `evozeus-session-signal-skill` |
| official promoted Factor pack | future official Factor release mechanism |
| registry pointer | `EvoZeus` main repo |

Infra must consume official assets through the main registry pointer and release metadata. It must not install from lab moving branches or old main-repo prototype paths.
