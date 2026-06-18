import test from "node:test";
import assert from "node:assert/strict";
import {
  RUNTIME_INFRA_COMPONENTS,
  verifyRuntimeInfraComponents
} from "../src/runtime-infra.mjs";

const expectedComponents = [
  "workspace",
  "permission-gate",
  "registry",
  "manifest-verifier",
  "lockfile",
  "scanner-sandbox",
  "factor-runner",
  "report-generator"
];

test("verifies availability of every runtime infra component", async () => {
  assert.deepEqual(Object.keys(RUNTIME_INFRA_COMPONENTS).sort(), expectedComponents.sort());

  const verification = await verifyRuntimeInfraComponents();

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

test("runtime infra probe runs a selected factor and writes local state", async () => {
  const verification = await verifyRuntimeInfraComponents();
  const byName = Object.fromEntries(
    verification.components.map((component) => [component.name, component])
  );

  assert.equal(byName["factor-runner"].details.result.factor_id, "fixed.tool-failure");
  assert.equal(byName["factor-runner"].details.result.status, "matched");
  assert.ok(byName["factor-runner"].details.result.evidence_refs.length > 0);
  assert.match(byName.lockfile.details.path, /\.evozeus\/runtime\/lockfile\.json$/);
  assert.match(byName["report-generator"].details.markdown, /fixed\.tool-failure/);
});
