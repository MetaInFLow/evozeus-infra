# evozeus-runtime

EvoZeus 的 future local runtime：CLI、TUI、local registry、report generation 和 selective Factor install。

这个 repo 当前不是稳定 CLI 产品。它是 runtime trust policy 和可执行能力的落点，只有当 `EvoZeus` 主 repo 的 protocol、registry、manifest 和权限模型稳定后，才进入用户默认路径。

```text
EvoZeus protocol
  -> official manifest
  -> local registry
  -> opt-in scanner / factor pack
  -> local report
```

## What It Is

`evozeus-runtime` 负责把 EvoZeus protocol 变成可执行的本地工具面。

它最终要回答：

- 如何在本地读取 session evidence。
- 如何生成 Markdown / JSON / HTML report。
- 如何选择性安装 official Factor pack。
- 如何验证 manifest、checksum 和 attestation。
- scanner 如何在最小权限和 sandbox 下运行。
- 用户如何明确同意联网、上传或贡献。

## What It Is Not

当前阶段不承诺：

- 不是稳定 CLI。
- 不默认安装 scanner。
- 不默认扫描本地所有文件。
- 不自动上传 raw session。
- 不直接消费 Discord thread、lab moving branch 或未审 submission。
- 不绕过 `EvoZeus` 主 repo registry 和 official release manifest。

## Start Here

如果你要规划 runtime 变更：

1. 先读 `EvoZeus` 主 repo 的 protocol、schema、privacy 和 verdict docs。
2. 确认要消费的是 main registry pointer，而不是 lab branch。
3. 写清楚 permission model：
   - files read
   - files written
   - env vars read
   - external commands
   - network access
4. 定义 local-first fallback。
5. 再设计 CLI / TUI / report surface。

给 Agent 的最短指令：

```text
Read evozeus-runtime/SKILL.md and README.md, then draft a runtime change plan. Start from trust policy, local-first behavior, manifest verification, scanner permission boundaries, and user approval gates. Do not assume runtime can upload, scan, or install by default.
```

## Who Should Use This

| Role | Use this repo when | Stop when |
| --- | --- | --- |
| Runtime maintainer | 需要实现 CLI/TUI/local registry/report | protocol 或 registry pointer 未稳定 |
| Security reviewer | 需要审查 scanner、upload、network、plugin execution | permission model 不完整 |
| Factor pack consumer | 需要选择性安装 official pack | pack 没有 manifest/checksum/attestation |
| Product maintainer | 需要设计用户使用路径 | 默认路径违反 local-first 或 opt-in |

## User View

| 用户问题 | Runtime 应该提供的入口 |
| --- | --- |
| 我能先本地审判一次 session 吗？ | local report generation |
| 我能看证据从哪里来吗？ | local evidence packet / source locator |
| 我能选择安装哪些 Factors 吗？ | selective install + lockfile |
| 我怎么知道 pack 可信？ | manifest + checksum + attestation verification |
| 我能禁止上传吗？ | upload off by default |
| 我能回滚吗？ | local registry state + lockfile |

## Trust Contract

Runtime 的默认契约：

- Local-first。
- Markdown / JSON first。
- Upload off by default。
- Scanner off by default。
- Network off unless explicitly enabled。
- Official pack only through registry + manifest + checksum。
- User approval before contribution, upload, install, or external issue / PR creation。

## Runtime Lifecycle

```text
protocol read
  -> workspace detect
  -> evidence packet
  -> factor / scanner selection
  -> local verdict report
  -> user-approved contribution
```

每一步都必须可停止、可解释、可回滚。

## Directory Map

| Path | Purpose |
| --- | --- |
| `docs/` | runtime 边界、权限模型、使用流设计 |
| `prototypes/` | 从主 repo 清理出来的旧 runtime prototype，仅作迁移素材 |
| `examples/` | future CLI / TUI / report 示例 |
| `packages/` | runtime package 预留位置 |
| `schemas/` | runtime config、lockfile 或 local registry schema |

## Current Status

- Repo status: private / future shell。
- Public target: 出现用户可安装 runtime 前必须 public。
- Stable CLI: no。
- Default user entry: no。
- Runtime docs intake: `docs/` 已承接从 `EvoZeus` 主 repo 移出的 runtime-heavy 设计材料。
- Runtime prototype intake: `prototypes/main-repo-runtime/` 已承接旧 scanner / Factor runner / storage / report prototype。
- Runtime code migration: active implementation 仍 pending protocol / registry / trust policy stability。

## Not Stable Yet

- 没有稳定 CLI 命令。
- 没有 install contract。
- 没有 scanner sandbox implementation。
- 没有 lockfile schema。
- 没有 registry consumer implementation。

## Validation

当前可执行的职责校验：

```bash
git diff --check
npm test
npm run test:infra-components
npm run test:runtime-contract
```

`test:infra-components` 校验 runtime infra 的 workspace、permission gate、registry、manifest verifier、lockfile、scanner sandbox、factor runner 和 report generator 是否可用，并实际运行一个 selected factor、写入 `.evozeus/runtime/lockfile.json`、生成 report。

`test:runtime-contract` 校验 runtime install plan 是否满足 explicit user approval、main registry pointer、official factor metadata、checksum、attestation、lockfile 和 network approval gate。
