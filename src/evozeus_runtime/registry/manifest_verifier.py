from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pydantic import BaseModel, Field


SHA256_RE = re.compile(r"^[a-f0-9]{64}$", re.IGNORECASE)


class FactorReleaseMetadata(BaseModel):
    factor_id: str
    source: str
    review_state: str
    artifact_path: Path
    checksum_sha256: str
    attestation_path: Path
    compatibility: dict[str, str] = Field(default_factory=dict)


class ManifestVerificationDecision(BaseModel):
    ok: bool
    issues: list[str] = Field(default_factory=list)


class ManifestVerifier:
    def verify(self, metadata: FactorReleaseMetadata) -> ManifestVerificationDecision:
        issues: list[str] = []
        if metadata.source != "official":
            issues.append("factor release metadata must come from official source")
        if metadata.review_state != "promoted":
            issues.append("factor review_state must be promoted")
        if not metadata.artifact_path.is_file():
            issues.append("artifact_path is required")
        if not metadata.attestation_path.is_file():
            issues.append("attestation_path is required")
        if not SHA256_RE.match(metadata.checksum_sha256):
            issues.append("checksum_sha256 must be a sha256 hex digest")
        elif metadata.artifact_path.is_file():
            actual = hashlib.sha256(metadata.artifact_path.read_bytes()).hexdigest()
            if actual != metadata.checksum_sha256.lower():
                issues.append("artifact checksum does not match metadata")
        if not metadata.compatibility.get("evozeus_protocol"):
            issues.append("compatibility.evozeus_protocol is required")
        return ManifestVerificationDecision(ok=not issues, issues=issues)

