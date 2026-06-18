import test from "node:test";
import assert from "node:assert/strict";
import { validateInfraInstallPlan } from "../scripts/validate-infra-install-plan.mjs";

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
    files_written: [".evozeus/infra/lockfile.json"],
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
    path: ".evozeus/infra/lockfile.json"
  },
  rollback: {
    disable: "Disable selected factors in the local lockfile.",
    delete: "Remove .evozeus/infra after explicit user confirmation."
  }
};

test("accepts an explicitly approved infra plan backed by official factor metadata", () => {
  assert.deepEqual(validateInfraInstallPlan(validPlan), []);
});

test("rejects infra enablement without explicit user approval", () => {
  const issues = validateInfraInstallPlan({ ...validPlan, user_approval: false });

  assert.match(issues.join("\n"), /user approval/i);
});

test("rejects default factors that bypass official release metadata", () => {
  const issues = validateInfraInstallPlan({
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
  assert.match(issues.join("\n"), /lab moving branches/i);
});

test("rejects network access unless it is separately approved with a reason", () => {
  const issues = validateInfraInstallPlan({
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

test("rejects lockfiles and registry pointers outside approved paths", () => {
  const issues = validateInfraInstallPlan({
    ...validPlan,
    registry: {
      source: "EvoZeus",
      pointer: "docs/runtime.json"
    },
    lockfile: {
      path: ".evozeus/runtime/lockfile.json"
    }
  });

  assert.match(issues.join("\n"), /factors\/registry/);
  assert.match(issues.join("\n"), /\.evozeus\/infra/);
});

test("rejects infra plans without rollback instructions", () => {
  const { rollback: _rollback, ...withoutRollback } = validPlan;
  const issues = validateInfraInstallPlan(withoutRollback);

  assert.match(issues.join("\n"), /rollback/i);
});
