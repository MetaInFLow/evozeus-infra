import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";

test("infra doctor reports available component status and approval gate", () => {
  const result = spawnSync(process.execPath, ["scripts/evozeus-infra-doctor.mjs"], {
    encoding: "utf8"
  });

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /component: evozeus-infra/);
  assert.match(result.stdout, /infra_status: available/);
  assert.match(result.stdout, /available_components: .*workspace/);
  assert.match(result.stdout, /available_components: .*factor-runner/);
  assert.match(result.stdout, /workspace_state_root: \.evozeus\/infra/);
  assert.match(result.stdout, /workspace_config_schema: workspace_config\.v0/);
  assert.match(result.stdout, /local_ledger_state: not_initialized/);
  assert.match(result.stdout, /lockfile_schema: infra-lock\.v0/);
  assert.match(result.stdout, /rollback_path: .*\.evozeus\/infra/);
  assert.match(result.stdout, /factor_runner_smoke: matched/);
  assert.match(result.stdout, /Ask before scanning user workspace data/);
});
