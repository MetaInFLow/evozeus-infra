#!/usr/bin/env node

import { verifyInfraComponents } from "../src/infra.mjs";

function detailOf(components, name) {
  return components.find((component) => component.name === name)?.details ?? {};
}

function printDoctor(report) {
  for (const [key, value] of Object.entries(report)) {
    if (Array.isArray(value)) {
      console.log(`${key}: ${value.join("; ")}`);
    } else {
      console.log(`${key}: ${value}`);
    }
  }
}

try {
  const verification = await verifyInfraComponents();
  const components = verification.components;
  const workspace = detailOf(components, "workspace");
  const workspaceConfig = detailOf(components, "workspace-config");
  const localLedger = detailOf(components, "local-ledger");
  const lockfile = detailOf(components, "lockfile");
  const rollbackPlan = detailOf(components, "rollback-plan");
  const scannerSandbox = detailOf(components, "scanner-sandbox");
  const factorRunner = detailOf(components, "factor-runner");
  const reportGenerator = detailOf(components, "report-generator");

  const unavailable = components
    .filter((component) => component.status !== "available")
    .map((component) => component.name);

  printDoctor({
    component: "evozeus-infra",
    infra_status: verification.available ? "available" : "unavailable",
    available_components: components
      .filter((component) => component.status === "available")
      .map((component) => component.name),
    unavailable_components: unavailable.length > 0 ? unavailable : ["none"],
    workspace_state_root: ".evozeus/infra",
    probe_workspace_state_root: workspace.infra_dir,
    workspace_config_schema: workspaceConfig.schema_version ?? "unknown",
    probe_workspace_config_path: workspaceConfig.path ?? "unknown",
    local_ledger_state: localLedger.state ?? "unknown",
    probe_local_ledger_dir: localLedger.directory ?? "unknown",
    lockfile_schema: "infra-lock.v0",
    probe_lockfile_path: lockfile.path,
    rollback_path: rollbackPlan.delete ?? "unknown",
    scanner_sandbox_network_allowed: scannerSandbox.network_allowed === true,
    factor_runner_smoke: factorRunner.result?.status ?? "unknown",
    report_generator_smoke: reportGenerator.markdown ? "available" : "unavailable",
    next_step: verification.available
      ? "Infra is ready for approved local execution. Ask before scanning user workspace data, running selected factors on user data, or writing persistent reports."
      : "Fix unavailable infra components before local execution."
  });

  if (!verification.available) {
    process.exitCode = 1;
  }
} catch (error) {
  console.error(`evozeus-infra-doctor: ${error.message}`);
  process.exitCode = 1;
}
