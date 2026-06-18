from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODEX_PACK = PROJECT_ROOT / "__infra__" / "scanner_packs" / "codex" / "0.1.0"


def test_codex_scanner_pack_contains_agent_resolver_contract_files():
    expected_paths = [
        CODEX_PACK / "scanner.json",
        CODEX_PACK / "SCANNER.xml",
        CODEX_PACK / "SKILL.md",
        CODEX_PACK / "resolver.py",
        CODEX_PACK / "scripts" / "resolve_event_source.py",
    ]

    for path in expected_paths:
        assert path.is_file(), path


def test_codex_scanner_pack_skill_documents_source_resolution():
    skill_text = (CODEX_PACK / "SKILL.md").read_text(encoding="utf-8")

    assert "SQLite Locator Fields" in skill_text
    assert "Resolve Original Event" in skill_text
    assert "resolve_event_source.py" in skill_text
    assert "hash_mismatch" in skill_text
