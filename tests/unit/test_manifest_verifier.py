from pathlib import Path

from evozeus_runtime.registry.manifest_verifier import FactorReleaseMetadata, ManifestVerifier


def test_manifest_verifier_accepts_official_promoted_artifact(tmp_path):
    artifact = tmp_path / "factor.py"
    artifact.write_text("print('ok')\n", encoding="utf-8")
    attestation = tmp_path / "attestation.json"
    attestation.write_text('{"subject":"factor.py"}\n', encoding="utf-8")

    metadata = FactorReleaseMetadata(
        factor_id="default.tool_failure",
        source="official",
        review_state="promoted",
        artifact_path=artifact,
        checksum_sha256="ad64355106bb158b020ecf9702be48f7730fc091dd4bb6a2f092b40393495b3d",
        attestation_path=attestation,
        compatibility={"evozeus_protocol": ">=0.1.0"},
    )

    decision = ManifestVerifier().verify(metadata)

    assert decision.ok is True


def test_manifest_verifier_rejects_lab_artifact_without_attestation(tmp_path):
    artifact = tmp_path / "factor.py"
    artifact.write_text("print('ok')\n", encoding="utf-8")

    metadata = FactorReleaseMetadata(
        factor_id="default.tool_failure",
        source="lab",
        review_state="draft",
        artifact_path=artifact,
        checksum_sha256="bad",
        attestation_path=tmp_path / "missing.json",
        compatibility={},
    )

    decision = ManifestVerifier().verify(metadata)

    assert decision.ok is False
    assert "official" in "\n".join(decision.issues)
    assert "attestation" in "\n".join(decision.issues)
