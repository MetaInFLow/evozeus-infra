# AGENTS.md

## 项目约定

- 项目产出文件默认用中文，关键专有名词、专业名词可以用英文。
- Feishu 相关的操作用 `larkcli`。
- 本 repo 属于 EvoZeus repo 体系，归属 `metainflow private`。

## Repo 职责

- 承接未来 EvoZeus runtime 的 CLI / TUI / local registry / report generation 能力。
- 在 protocol、schema 和 trust policy 稳定前，不作为默认用户入口。
- runtime 相关联网、扫描、上传能力必须显式启用并经过权限设计。

## Agent 入口

- Runtime 相关任务先读 `SKILL.md` 和 `README.md`。
- 不绕过 `EvoZeus` main registry pointer、official manifest、checksum、SBOM / attestation。
