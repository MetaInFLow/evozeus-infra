from pathlib import Path

from evozeus_runtime.factors.base import FactorContext
from evozeus_runtime.factors.official_bridge import OfficialFactorPackBuilder
from evozeus_runtime.factors.packs import FactorPackRepository
from evozeus_runtime.sessions.schema import SessionEnvelope, SessionEvent


EXPECTED_OFFICIAL_FACTOR_IDS = {
    "official.key-sentence-trends",
    "official.repeated-request",
    "official.session-resource-usage",
    "official.task-completion",
    "official.tool-failure-frequency",
    "official.usage-sentence-cloud",
    "official.user-input-sentiment",
}


def test_official_factor_bridge_builds_loadable_packs_for_all_official_factors(tmp_path):
    pack_root = tmp_path / "official-packs"

    result = OfficialFactorPackBuilder(
        official_repo_root=_official_repo_root(),
        output_pack_root=pack_root,
    ).build()

    assert set(result.factor_ids) == EXPECTED_OFFICIAL_FACTOR_IDS
    packs = FactorPackRepository(pack_root).discover()
    assert {pack.manifest.id for pack in packs} == EXPECTED_OFFICIAL_FACTOR_IDS


def test_official_factor_bridge_uses_source_factor_xml_contract(tmp_path):
    pack_root = tmp_path / "official-packs"

    OfficialFactorPackBuilder(
        official_repo_root=_official_repo_root(),
        output_pack_root=pack_root,
    ).build()

    pack = FactorPackRepository(pack_root).get("official.user-input-sentiment")

    assert pack.manifest.outputs == ["user_sentiment", "frequency_distribution"]
    assert pack.manifest.run["input_channels"] == "user_input"
    assert pack.manifest.run["required_python_packages"] == "scikit-learn,jieba,rapidfuzz,snownlp"
    assert "dissatisfaction risk" in pack.introduction.summary_en.lower()
    assert "raw body" in pack.introduction.privacy_en.lower()


def test_official_factor_bridge_preserves_datasets_and_uses_compact_tags(tmp_path):
    pack_root = tmp_path / "official-packs"
    OfficialFactorPackBuilder(
        official_repo_root=_official_repo_root(),
        output_pack_root=pack_root,
    ).build()

    factor = FactorPackRepository(pack_root).load("official.usage-sentence-cloud")
    result = factor.run(
        FactorContext(
            session=SessionEnvelope(
                session_id="s1",
                provider="codex",
                source_ref="/tmp/s1.jsonl",
                events=[
                    SessionEvent(event_id="u1", role="user", content="不要改文件，只输出方案"),
                    SessionEvent(event_id="u2", role="user", content="不要改文件，只输出方案"),
                ],
            )
        )
    )

    assert result.status == "matched"
    assert result.datasets[0]["semantic_type"] == "high_frequency_phrase_set"
    assert result.presentations[0]["component_ref"] == "ui.native-static.word-cloud.v1"
    assert result.tags == [{"type": "usage_sentence", "value": "high_frequency"}]


def _official_repo_root() -> Path:
    return Path(__file__).resolve().parents[3] / "evozeus-session-signal-skill"
