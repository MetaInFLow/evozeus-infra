import test from "node:test";
import assert from "node:assert/strict";
import { validateRuntimeInstallPlan } from "../scripts/validate-runtime-install-plan.mjs";

const validPlan = {
  user_approval: true,
  registry: {
    source: "EvoZeus",
    pointer: "factors/registry/index.json"
  },
  default_factor_set: {
    mode: "recommended",
    enablement: "explicit-selection"
  },
  permissions: {
    files_read: ["~/.codex/sessions"],
    files_written: [".evozeus/runtime/lockfile.json"],
    env_read: [],
    external_commands: [],
    network: {
      enabled: false
    }
  },
  factors: [
    {
      id: "default.tool-failure",
      selected: true,
      source: "official",
      review_state: "promoted",
      manifest: {
        path: "manifests/releases/evozeus-default-pack/v0.1.0.yaml"
      },
      checksum: {
        algorithm: "sha256",
        value: "a".repeat(64)
      },
      attestation: {
        path: "attestations/evozeus-default-pack/v0.1.0.attestation.json"
      },
      compatibility: {
        evozeus_protocol: ">=0.1.0"
      }
    }
  ],
  lockfile: {
    path: ".evozeus/runtime/lockfile.json"
  }
};

test("accepts an explicitly approved runtime plan backed by official factor metadata", () => {
  assert.deepEqual(validateRuntimeInstallPlan(validPlan), []);
});

test("rejects runtime enablement without explicit user approval", () => {
  const issues = validateRuntimeInstallPlan({ ...validPlan, user_approval: false });

  assert.match(issues.join("\n"), /user approval/i);
});

test("rejects default factors that bypass official release metadata", () => {
  const issues = validateRuntimeInstallPlan({
    ...validPlan,
    factors: [
      {
        ...validPlan.factors[0],
        source: "lab",
        manifest: { path: "evozeus-factor-lab/reviewed/main.yaml" },
        attestation: {}
      }
    ]
  });

  assert.match(issues.join("\n"), /official/i);
  assert.match(issues.join("\n"), /attestation/i);
});

test("rejects network access unless it is separately approved with a reason", () => {
  const issues = validateRuntimeInstallPlan({
    ...validPlan,
    permissions: {
      ...validPlan.permissions,
      network: {
        enabled: true
      }
    }
  });

  assert.match(issues.join("\n"), /network/i);
});
