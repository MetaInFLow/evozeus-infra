import json
from pathlib import Path

from evozeus.factors.base import FactorContext
from evozeus.factors.packs import FactorPackRepository
from evozeus.factors.runner import FactorRunner
from evozeus.scanners.base import ScanRequest
from evozeus.scanners.providers.codex import CodexScanner


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACK_ROOT = PROJECT_ROOT / "__infra__" / "factor_packs"
SESSION_ROOT = PROJECT_ROOT / "__infra__" / "testdata" / "codex_sessions"


def test_factor_packs_are_independent_folders_with_manifest_and_code():
    repository = FactorPackRepository(PACK_ROOT)
    packs = repository.discover()

    assert len(packs) == 8
    assert {pack.manifest.id for pack in packs} == {
        "default.negative_feedback",
        "default.open_loop",
        "default.repeated_user_requests",
        "default.same_target_rework",
        "default.success_closure_quality",
        "default.task_span_extraction",
        "default.tool_failure",
        "default.user_correction_loop",
    }
    for pack in packs:
        assert pack.root.is_dir()
        assert (pack.root / "factor.json").is_file()
        assert (pack.root / "FACTOR.xml").is_file()
        assert (pack.root / "factor.py").is_file()


def test_factor_pack_repository_loads_factor_xml_introductions():
    packs = FactorPackRepository(PACK_ROOT).discover()

    for pack in packs:
        assert pack.introduction.id == pack.manifest.id
        assert pack.introduction.version == pack.manifest.version
        assert pack.introduction.name
        assert pack.introduction.name_zh
        assert pack.introduction.name_en
        assert pack.introduction.summary
        assert pack.introduction.summary_zh
        assert pack.introduction.summary_en
        assert pack.introduction.category
        assert pack.introduction.stage == pack.manifest.stage
        assert pack.introduction.runtime == pack.manifest.runtime.mode
        assert pack.introduction.inputs
        assert pack.introduction.outputs
        assert pack.introduction.when_to_use
        assert pack.introduction.when_to_use_zh
        assert pack.introduction.when_to_use_en
        assert pack.introduction.limitations
        assert pack.introduction.limitations_zh
        assert pack.introduction.limitations_en
        assert pack.introduction.privacy
        assert pack.introduction.privacy_zh
        assert pack.introduction.privacy_en
        assert pack.introduction.tag_labels
        for tag_label in pack.introduction.tag_labels:
            assert tag_label.type
            assert tag_label.value
            assert tag_label.label_zh
            assert tag_label.label_en
        assert not hasattr(pack.introduction, "visualization")


def test_factor_xml_does_not_define_visualization_components():
    packs = FactorPackRepository(PACK_ROOT).discover()

    for pack in packs:
        xml = (pack.root / "FACTOR.xml").read_text(encoding="utf-8")
        assert "<visualization" not in xml


def test_default_factor_packs_declare_in_process_runtime():
    for manifest_path in sorted(PACK_ROOT.glob("*/*/factor.json")):
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert data["runtime"]["mode"] == "in_process"
        assert data["runtime"]["timeout_ms"] > 0


def test_factor_pack_repository_loads_and_runs_specified_factor():
    session_ref = CodexScanner().discover(ScanRequest(provider="codex", source_dir=SESSION_ROOT))[0]
    session = CodexScanner().load(session_ref)
    repository = FactorPackRepository(PACK_ROOT)
    factor = repository.load("default.tool_failure")

    summary = FactorRunner([factor]).run(FactorContext(session=session))

    assert not summary.errors
    assert summary.results[0].factor_id == "default.tool_failure"
    assert summary.results[0].status == "matched"
