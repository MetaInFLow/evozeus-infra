import { readFile } from "node:fs/promises";

const HEX_SHA256 = /^[a-f0-9]{64}$/i;

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasText(value) {
  return typeof value === "string" && value.trim().length > 0;
}

function requireString(value, path, issues) {
  if (!hasText(value)) {
    issues.push(`${path} is required`);
  }
}

function requireArray(value, path, issues) {
  if (!Array.isArray(value)) {
    issues.push(`${path} must be an array`);
  }
}

export function validateInfraInstallPlan(plan) {
  const issues = [];

  if (!isPlainObject(plan)) {
    return ["infra install plan must be an object"];
  }

  if (plan.user_approval !== true) {
    issues.push("infra enablement requires explicit user approval");
  }

  if (!isPlainObject(plan.registry)) {
    issues.push("registry metadata is required");
  } else {
    if (plan.registry.source !== "EvoZeus") {
      issues.push("registry source must be EvoZeus");
    }
    requireString(plan.registry.pointer, "registry.pointer", issues);
    if (hasText(plan.registry.pointer) && !plan.registry.pointer.startsWith("factors/registry/")) {
      issues.push("registry.pointer must stay under factors/registry/");
    }
  }

  if (!isPlainObject(plan.default_factor_set)) {
    issues.push("default_factor_set is required");
  } else {
    if (plan.default_factor_set.mode !== "recommended") {
      issues.push("default_factor_set.mode must be recommended");
    }
    if (plan.default_factor_set.enablement !== "explicit-selection") {
      issues.push("default factors must use explicit-selection enablement");
    }
  }

  if (!isPlainObject(plan.permissions)) {
    issues.push("permissions declaration is required");
  } else {
    requireArray(plan.permissions.files_read, "permissions.files_read", issues);
    requireArray(plan.permissions.files_written, "permissions.files_written", issues);
    requireArray(plan.permissions.env_read, "permissions.env_read", issues);
    requireArray(plan.permissions.external_commands, "permissions.external_commands", issues);

    if (!isPlainObject(plan.permissions.network)) {
      issues.push("permissions.network declaration is required");
    } else if (
      plan.permissions.network.enabled === true &&
      (plan.permissions.network.approved !== true || !hasText(plan.permissions.network.reason))
    ) {
      issues.push("network access requires separate approval and a reason");
    }
  }

  if (!isPlainObject(plan.lockfile)) {
    issues.push("lockfile declaration is required");
  } else if (!hasText(plan.lockfile.path) || !plan.lockfile.path.startsWith(".evozeus/infra/")) {
    issues.push("lockfile.path must stay under .evozeus/infra/");
  }

  if (!isPlainObject(plan.rollback)) {
    issues.push("rollback declaration is required");
  } else {
    requireString(plan.rollback.disable, "rollback.disable", issues);
    requireString(plan.rollback.delete, "rollback.delete", issues);
  }

  if (!Array.isArray(plan.factors) || plan.factors.length === 0) {
    issues.push("at least one official factor must be selected");
  } else {
    plan.factors.forEach((factor, index) => {
      const prefix = `factors[${index}]`;

      if (!isPlainObject(factor)) {
        issues.push(`${prefix} must be an object`);
        return;
      }

      requireString(factor.id, `${prefix}.id`, issues);

      if (factor.selected !== true) {
        issues.push(`${prefix} must be explicitly selected`);
      }
      if (factor.source !== "official") {
        issues.push(`${prefix} must come from official release metadata`);
      }
      if (factor.review_state !== "promoted") {
        issues.push(`${prefix}.review_state must be promoted`);
      }

      if (!isPlainObject(factor.manifest)) {
        issues.push(`${prefix}.manifest is required`);
      } else {
        requireString(factor.manifest.path, `${prefix}.manifest.path`, issues);
        if (
          hasText(factor.manifest.path) &&
          factor.manifest.path.includes("evozeus-factor-lab")
        ) {
          issues.push(`${prefix}.manifest.path must not point to lab moving branches`);
        }
      }

      if (!isPlainObject(factor.checksum)) {
        issues.push(`${prefix}.checksum is required`);
      } else {
        if (factor.checksum.algorithm !== "sha256") {
          issues.push(`${prefix}.checksum.algorithm must be sha256`);
        }
        if (!HEX_SHA256.test(String(factor.checksum.value ?? ""))) {
          issues.push(`${prefix}.checksum.value must be a sha256 hex digest`);
        }
      }

      if (!isPlainObject(factor.attestation) || !hasText(factor.attestation.path)) {
        issues.push(`${prefix}.attestation.path is required`);
      }

      if (!isPlainObject(factor.compatibility) || !hasText(factor.compatibility.evozeus_protocol)) {
        issues.push(`${prefix}.compatibility.evozeus_protocol is required`);
      }
    });
  }

  return issues;
}

async function main() {
  const file = process.argv[2];

  if (!file) {
    console.error("Usage: node scripts/validate-infra-install-plan.mjs <plan.json>");
    process.exitCode = 2;
    return;
  }

  const plan = JSON.parse(await readFile(file, "utf8"));
  const issues = validateInfraInstallPlan(plan);

  if (issues.length > 0) {
    console.error(issues.join("\n"));
    process.exitCode = 1;
    return;
  }

  console.log("infra install plan is valid");
}

if (import.meta.url === `file://${process.argv[1]}`) {
  await main();
}
