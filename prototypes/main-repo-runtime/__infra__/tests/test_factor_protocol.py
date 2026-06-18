import json

from evozeus.factors.manifest import load_manifest
from evozeus.factors.protocol import FactorResult


def test_load_manifest_binds_factor_to_framework_stage(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "id": "community.github_network_debug",
                "name": "github-network-debug",
                "framework_id": "agent_session_review.v0",
                "stage": "verdict_building",
                "runtime_profile": "community",
                "default_enabled": False,
                "version": "0.1.0",
                "status": "candidate",
                "description": "Classifies GitHub network failures.",
                "inputs": ["command_output", "tool_event", "environment_signal"],
                "outputs": ["tag", "evidence_ref", "verdict_signal"],
                "permissions": ["read local report"],
                "risks": ["misclassifies auth as network"],
                "rollback": "disable factor in local config",
            }
        ),
        encoding="utf-8",
    )

    manifest = load_manifest(path)

    assert manifest.id == "community.github_network_debug"
    assert manifest.framework_id == "agent_session_review.v0"
    assert manifest.stage == "verdict_building"
    assert manifest.runtime_profile == "community"
    assert manifest.rollback == "disable factor in local config"


def test_factor_result_requires_target_and_confidence():
    result = FactorResult(
        factor_id="default.same_target_rework",
        framework_id="agent_session_review.v0",
        stage="signal_extraction",
        target_type="session",
        target_id="ezs_001",
        tags=[{"type": "rework", "value": "same_target_rework"}],
        scores={"same_target_rework": 0.82},
        evidence_refs=[{"ref_id": "event_0004", "kind": "user_turn"}],
        verdict_signals=["Promote to Skill"],
        confidence=0.78,
    )

    assert result.target_id == "ezs_001"
    assert result.confidence == 0.78
