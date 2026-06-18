import test from "node:test";
import assert from "node:assert/strict";
import {
  INFRA_COMPONENTS,
  verifyInfraComponents
} from "../src/infra.mjs";

const expectedComponents = [
  "workspace",
  "workspace-config",
  "local-ledger",
  "permission-gate",
  "registry",
  "manifest-verifier",
  "lockfile",
  "rollback-plan",
  "scanner-sandbox",
  "factor-runner",
  "report-generator"
];

test("verifies availability of every infra component", async () => {
  assert.deepEqual(Object.keys(INFRA_COMPONENTS).sort(), expectedComponents.sort());

  const verification = await verifyInfraComponents();

  assert.deepEqual(
    verification.components.map((component) => component.name).sort(),
    expectedComponents.sort()
  );
  assert.equal(verification.available, true);
  assert.deepEqual(
    verification.components.map((component) => component.status),
    expectedComponents.map(() => "available")
  );
});

test("infra probe runs a selected factor and writes local state", async () => {
  const verification = await verifyInfraComponents();
  const byName = Object.fromEntries(
    verification.components.map((component) => [component.name, component])
  );

  assert.equal(byName["factor-runner"].details.result.factor_id, "fixed.tool-failure");
  assert.equal(byName["factor-runner"].details.result.status, "matched");
  assert.ok(byName["factor-runner"].details.result.evidence_refs.length > 0);
  assert.equal(byName["workspace-config"].details.schema_version, "workspace_config.v0");
  assert.equal(byName["workspace-config"].details.upload_default, false);
  assert.equal(byName["local-ledger"].details.state, "not_initialized");
  assert.match(byName.lockfile.details.path, /\.evozeus\/infra\/lockfile\.json$/);
  assert.match(byName["rollback-plan"].details.delete, /\.evozeus\/infra/);
  assert.match(byName.registry.details.selected_factors[0].manifest_path, /^manifests\/releases\//);
  assert.match(byName.registry.details.selected_factors[0].attestation_path, /^attestations\//);
  assert.equal(byName.registry.details.selected_factors[0].compatibility.evozeus_protocol, ">=0.1.0");
  assert.match(byName["report-generator"].details.markdown, /fixed\.tool-failure/);
});
