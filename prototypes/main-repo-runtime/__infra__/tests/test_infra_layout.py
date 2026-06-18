from pathlib import Path


def project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "README.md").exists() and (parent / "SKILL.md").exists():
            return parent
    raise AssertionError("project root not found")


def test_python_business_logic_lives_under_infra_folder():
    root = project_root()

    assert (root / "__infra__" / "src" / "evozeus").is_dir()
    assert (root / "__infra__" / "tests").is_dir()
    assert not (root / "src" / "evozeus").exists()
