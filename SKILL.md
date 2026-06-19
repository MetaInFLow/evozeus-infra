---
name: evozeus-runtime
description: Use when designing, implementing, reviewing, or debugging EvoZeus local scanner, SessionEnvelope, factor runner, local ledger, report generation, permission gate, manifest verification, or FactorPack execution.
---

# EvoZeus Runtime

This repo is the Python scanner / runner runtime for EvoZeus.

## Component Role

```text
local session source
  -> scanner adapter
  -> SessionEnvelope
  -> selected FactorPack
  -> FactorRunner
  -> local ledger
  -> local report
```

## Before Runtime Execution

Identify and, when needed, confirm:

- files and directories to read
- files and local state to write
- environment variables to read
- external commands to run
- network access, if any
- selected scanner
- selected factors
- rollback and cleanup path

Default behavior is local-first, upload-off, network-off, external-command-off, and explicit-selection for factors.

## Architecture Rules

- Scanner uses Abstract Base Class + Adapter + Registry. 每个本地应用或 session provider 必须实现独立 scanner adapter。
- Scanner `scan` 阶段只记录 `session_id` 和 `message_id`，不得写入 message content、tool output 或 preview。
- Scanner `load` 阶段才 materialize `SessionEnvelope`，必须通过 event generator 渐进式读取，只给 selected Factor runtime 使用。
- SQLite `session_events` 在 scan 后是 message id index，用于关联后续 Factor evidence、tags、results。
- P0 built-in scanner is `CodexScanner`; future provider adapters register through the scanner registry instead of branching inside use cases.
- Factor uses Abstract Base Class + Template Method.
- Runner uses Serial Pipeline.
- Runtime isolation uses Strategy / Resolver.
- Ledger uses Repository Pattern.
- Report generation reads ledger / results and does not rescan or rerun factors.

## Development Boundary

Runtime changes belong here when they touch:

- local session scanner adapters
- `SessionEnvelope` / event locator schema
- FactorPack loading and validation
- Factor runner and runtime isolation
- local SQLite ledger
- report generation
- permission gate
- manifest checksum / attestation / compatibility verification

Protocol, governance, and registry pointer semantics belong in the `EvoZeus` main repo.

## Output Shape

For runtime plans or reviews, output:

```text
Capability -> Inputs -> Outputs -> Permissions -> Verification -> Rollback -> User approval gate
```
