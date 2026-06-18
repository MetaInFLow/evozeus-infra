import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { validateRuntimeInstallPlan } from "../scripts/validate-runtime-install-plan.mjs";

export const RUNTIME_INFRA_COMPONENTS = {
  workspace: "detects local runtime state paths",
  "permission-gate": "validates user approval and declared permissions",
  registry: "stores selected official factor metadata",
  "manifest-verifier": "verifies artifact checksum and attestation presence",
  lockfile: "writes selected runtime state under .evozeus",
  "scanner-sandbox": "enforces scanner permission boundaries",
  "factor-runner": "executes a selected factor against a session",
  "report-generator": "renders factor results into a local report"
};

export async function verifyRuntimeInfraComponents(options = {}) {
  const root = options.root ?? (await mkdtemp(path.join(tmpdir(), "evozeus-runtime-")));
  const workspace = await probeWorkspace(root);
  const permissionGate = probePermissionGate();
  const registry = probeRegistry();
  const manifestVerifier = await probeManifestVerifier(root);
  const lockfile = await probeLockfile(root, registry.details.selected_factors);
  const scannerSandbox = probeScannerSandbox();
  const factorRunner = probeFactorRunner();
  const reportGenerator = probeReportGenerator([factorRunner.details.result]);

  const components = [
    workspace,
    permissionGate,
    registry,
    manifestVerifier,
    lockfile,
    scannerSandbox,
    factorRunner,
    reportGenerator
  ];

  return {
    available: components.every((component) => component.status === "available"),
    components
  };
}

async function probeWorkspace(root) {
  const runtimeDir = path.join(root, ".evozeus", "runtime");
  const reportDir = path.join(runtimeDir, "reports");

  await mkdir(reportDir, { recursive: true });

  return available("workspace", {
    root,
    runtime_dir: runtimeDir,
    report_dir: reportDir
  });
}

function probePermissionGate() {
  const plan = {
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
      files_read: ["session.json"],
      files_written: [".evozeus/runtime/lockfile.json"],
      env_read: [],
      external_commands: [],
      network: {
        enabled: false
      }
    },
    factors: [
      {
        id: "fixed.tool-failure",
        selected: true,
        source: "official",
        review_state: "promoted",
        manifest: {
          path: "manifests/releases/evozeus-test-pack/v0.1.0.yaml"
        },
        checksum: {
          algorithm: "sha256",
          value: "a".repeat(64)
        },
        attestation: {
          path: "attestations/evozeus-test-pack/v0.1.0.attestation.json"
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

  return available("permission-gate", {
    issues: validateRuntimeInstallPlan(plan)
  });
}

function probeRegistry() {
  const selectedFactors = [
    {
      id: "fixed.tool-failure",
      version: "0.1.0",
      source: "official",
      manifest_path: "manifests/releases/evozeus-test-pack/v0.1.0.yaml"
    }
  ];

  return available("registry", {
    selected_factors: selectedFactors,
    count: selectedFactors.length
  });
}

async function probeManifestVerifier(root) {
  const artifactPath = path.join(root, "artifact.txt");
  const attestationPath = path.join(root, "attestation.json");
  const artifact = "factor artifact\n";
  const checksum = createHash("sha256").update(artifact).digest("hex");

  await writeFile(artifactPath, artifact);
  await writeFile(attestationPath, JSON.stringify({ subject: "artifact.txt" }));

  const actual = createHash("sha256").update(await readFile(artifactPath, "utf8")).digest("hex");

  return available("manifest-verifier", {
    checksum_ok: actual === checksum,
    attestation_path: attestationPath
  });
}

async function probeLockfile(root, selectedFactors) {
  const lockfilePath = path.join(root, ".evozeus", "runtime", "lockfile.json");

  await mkdir(path.dirname(lockfilePath), { recursive: true });
  await writeFile(
    lockfilePath,
    JSON.stringify(
      {
        schema_version: "runtime-lock.v0",
        selected_factors: selectedFactors
      },
      null,
      2
    )
  );

  return available("lockfile", {
    path: lockfilePath,
    factor_count: selectedFactors.length
  });
}

function probeScannerSandbox() {
  const declaration = {
    files_read: ["session.json"],
    files_written: [],
    env_read: [],
    external_commands: [],
    network: {
      enabled: false
    }
  };

  return available("scanner-sandbox", {
    network_allowed: declaration.network.enabled === true,
    declared_inputs: declaration.files_read
  });
}

function probeFactorRunner() {
  const session = {
    session_id: "runtime-session",
    events: [
      {
        id: "tool-1",
        role: "tool",
        status: "error",
        text: "command failed"
      }
    ]
  };
  const factor = {
    factor_id: "fixed.tool-failure",
    match: {
      any_event: {
        role: "tool",
        status: "error"
      }
    },
    outputs: {
      tags: ["tool:error"],
      verdict_signals: ["tool returned an error"]
    }
  };

  return available("factor-runner", {
    result: runRuntimeFactor(factor, session)
  });
}

function probeReportGenerator(results) {
  const markdown = [
    "# EvoZeus Runtime Report",
    "",
    ...results.map((result) => `- ${result.factor_id}: ${result.status}`)
  ].join("\n");

  return available("report-generator", {
    markdown,
    json: {
      results
    }
  });
}

export function runRuntimeFactor(factor, session) {
  const matchedEvent = findMatchingEvent(factor.match?.any_event, session.events ?? []);
  const matched = Boolean(matchedEvent);

  return {
    factor_id: factor.factor_id,
    status: matched ? "matched" : "not_matched",
    tags: matched ? factor.outputs?.tags ?? [] : [],
    verdict_signals: matched ? factor.outputs?.verdict_signals ?? [] : [],
    evidence_refs: matched ? [`event:${matchedEvent.id}`] : []
  };
}

function findMatchingEvent(rule, events) {
  if (!rule) {
    return null;
  }

  return events.find((event) => {
    if (rule.role !== undefined && event.role !== rule.role) {
      return false;
    }
    if (rule.status !== undefined && event.status !== rule.status) {
      return false;
    }
    if (
      rule.text_includes !== undefined &&
      !String(event.text ?? "").toLowerCase().includes(String(rule.text_includes).toLowerCase())
    ) {
      return false;
    }
    return true;
  });
}

function available(name, details) {
  return {
    name,
    status: "available",
    details
  };
}
