---
name: evozeus-runtime
description: Use when enabling, designing, implementing, reviewing, or debugging EvoZeus runtime behavior, local registry, CLI, TUI, scanner execution, report generation, lockfile, or selective official factor install.
---

# EvoZeus Runtime

Runtime is the executable component of EvoZeus. It is enabled only after the user approves local execution, file access, installs, network behavior, and local state changes.

## Component Role

```text
EvoZeus registry pointer
  -> official release manifest
  -> checksum / SBOM / attestation
  -> selected factors
  -> local judgment
  -> local report
```

## Before Enabling Runtime

Explain and confirm:

- files and directories to read
- files and local state to write
- environment variables to read
- external commands to run
- network access, if any
- selected official factors
- rollback and cleanup path

If the user does not approve, stop at the protocol-only judgment path.

## Default Official Factors

Default factors are recommended, not silently enabled.

Runtime must:

1. read the `EvoZeus` registry pointer
2. resolve only official release manifests
3. verify checksum, SBOM / attestation, compatibility, and review state
4. write a local lockfile before execution
5. run only selected factors
6. keep raw session data local

If registry pointer, manifest, checksum, SBOM / attestation, or compatibility is missing, report the blocker instead of inventing an install path.

## Development Boundary

Runtime PRs belong in this repo when they touch:

- CLI / TUI / companion / local API
- local registry or lockfile
- `.evozeus/` state
- scanner execution
- factor execution
- report generation
- runtime upload, network, sandbox, dependency, or rollback behavior

Protocol, governance, and registry pointer semantics belong in the `EvoZeus` main repo.

## Output Shape

For runtime plans or reviews, output:

```text
Capability -> Inputs -> Outputs -> Permissions -> Verification -> Rollback -> User approval gate
```
