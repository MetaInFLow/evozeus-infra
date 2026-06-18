# evozeus-runtime

Future EvoZeus runtime for CLI, TUI, local registry, reports, and selective Factor install.

本 repo 是 EvoZeus runtime 的预留空间。当前不代表稳定 CLI 产品；只有当 `EvoZeus` 主 repo 中的 protocol、schema、registry 和权限模型稳定后，才把 runtime 逻辑正式迁入。

## 目标能力

- `.evozeus/` local registry。
- Markdown / JSON report generation。
- selective Factor install。
- scanner sandbox。
- lockfile。
- CLI / TUI / browser companion 的边界验证。

## 当前边界

- 不自动上传 raw session。
- 不默认扫描本地所有文件。
- 不自动创建或合并 GitHub PR。
- 不绕过用户确认进行 contribution。

## 目录结构

- `docs/`：runtime 边界、权限模型和使用流设计。
- `examples/`：未来 CLI / TUI / report 示例。
- `packages/`：runtime package 预留位置。
- `schemas/`：runtime 自身配置或 lockfile schema 预留位置。
