from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

from evozeus.factors.base import Factor
from evozeus.factors.manifest import FactorManifest, load_manifest


@dataclass(frozen=True)
class FactorTagLabel:
    type: str
    value: str
    label_zh: str
    label_en: str


@dataclass(frozen=True)
class FactorIntroduction:
    id: str
    version: str
    name: str
    name_zh: str
    name_en: str
    summary: str
    summary_zh: str
    summary_en: str
    category: str
    stage: str
    runtime: str
    inputs: list[str]
    outputs: list[str]
    when_to_use: str
    when_to_use_zh: str
    when_to_use_en: str
    limitations: str
    limitations_zh: str
    limitations_en: str
    privacy: str
    privacy_zh: str
    privacy_en: str
    tag_labels: list[FactorTagLabel]


@dataclass(frozen=True)
class FactorPack:
    root: Path
    manifest: FactorManifest
    introduction: FactorIntroduction


class FactorPackRepository:
    def __init__(self, pack_root: Path):
        self.pack_root = pack_root

    def discover(self) -> list[FactorPack]:
        if not self.pack_root.exists():
            return []
        packs = [load_factor_pack(path.parent) for path in sorted(self.pack_root.glob("*/*/factor.json"))]
        return packs

    def load(self, factor_id: str, version: str | None = None) -> Factor:
        return load_factor_from_pack(self.get(factor_id, version))

    def get(self, factor_id: str, version: str | None = None) -> FactorPack:
        matches = [
            pack
            for pack in self.discover()
            if pack.manifest.id == factor_id and (version is None or pack.manifest.version == version)
        ]
        if not matches:
            raise KeyError(f"unknown factor pack: {factor_id}")
        return matches[-1]


def load_factor_pack(root: Path) -> FactorPack:
    manifest = load_manifest(root / "factor.json")
    introduction = load_introduction(root / "FACTOR.xml")
    _validate_intro_matches_manifest(introduction, manifest, root)
    return FactorPack(root=root, manifest=manifest, introduction=introduction)


def load_introduction(path: Path) -> FactorIntroduction:
    if not path.is_file():
        raise FileNotFoundError(f"missing FACTOR.xml: {path}")

    root = ET.fromstring(path.read_text(encoding="utf-8"))
    if root.tag != "factor":
        raise ValueError(f"FACTOR.xml root element must be <factor>: {path}")

    name_zh, name_en = _required_bilingual_text(root, "name", path)
    summary_zh, summary_en = _required_bilingual_text(root, "summary", path)
    when_to_use_zh, when_to_use_en = _required_bilingual_text(root, "when_to_use", path)
    limitations_zh, limitations_en = _required_bilingual_text(root, "limitations", path)
    privacy_zh, privacy_en = _required_bilingual_text(root, "privacy", path)
    introduction = FactorIntroduction(
        id=(root.attrib.get("id") or "").strip(),
        version=(root.attrib.get("version") or "").strip(),
        name=_bilingual_display(name_zh, name_en),
        name_zh=name_zh,
        name_en=name_en,
        summary=_bilingual_display(summary_zh, summary_en),
        summary_zh=summary_zh,
        summary_en=summary_en,
        category=_required_text(root, "category", path),
        stage=_required_text(root, "stage", path),
        runtime=_required_text(root, "runtime", path),
        inputs=_required_list(root, "inputs", "input", path),
        outputs=_required_list(root, "outputs", "output", path),
        when_to_use=_bilingual_display(when_to_use_zh, when_to_use_en),
        when_to_use_zh=when_to_use_zh,
        when_to_use_en=when_to_use_en,
        limitations=_bilingual_display(limitations_zh, limitations_en),
        limitations_zh=limitations_zh,
        limitations_en=limitations_en,
        privacy=_bilingual_display(privacy_zh, privacy_en),
        privacy_zh=privacy_zh,
        privacy_en=privacy_en,
        tag_labels=_required_tag_labels(root, path),
    )
    if not introduction.id or not introduction.version:
        raise ValueError(f"FACTOR.xml must declare id and version attributes: {path}")
    return introduction


def load_factor_from_pack(pack: FactorPack) -> Factor:
    module_name, class_name = _parse_entrypoint(pack.manifest.entrypoint)
    module_path = pack.root / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"evozeus_factor_pack_{pack.manifest.id.replace('.', '_')}_{pack.manifest.version.replace('.', '_')}",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load factor module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    factor_class = getattr(module, class_name)
    factor = factor_class()
    if not isinstance(factor, Factor):
        raise TypeError(f"factor entrypoint does not implement Factor: {pack.manifest.entrypoint}")
    return factor


def _parse_entrypoint(entrypoint: str) -> tuple[str, str]:
    if ":" not in entrypoint:
        raise ValueError("factor entrypoint must use module:ClassName")
    module_name, class_name = entrypoint.split(":", 1)
    return module_name, class_name


def _validate_intro_matches_manifest(introduction: FactorIntroduction, manifest: FactorManifest, root: Path) -> None:
    mismatches = []
    if introduction.id != manifest.id:
        mismatches.append(f"id={introduction.id!r} expected {manifest.id!r}")
    if introduction.version != manifest.version:
        mismatches.append(f"version={introduction.version!r} expected {manifest.version!r}")
    if introduction.stage != manifest.stage.value:
        mismatches.append(f"stage={introduction.stage!r} expected {manifest.stage.value!r}")
    if introduction.runtime != manifest.runtime.mode.value:
        mismatches.append(f"runtime={introduction.runtime!r} expected {manifest.runtime.mode.value!r}")
    if mismatches:
        raise ValueError(f"FACTOR.xml does not match factor.json in {root}: {', '.join(mismatches)}")


def _required_text(root: ET.Element, name: str, path: Path) -> str:
    child = root.find(name)
    text = child.text.strip() if child is not None and child.text else ""
    if not text:
        raise ValueError(f"FACTOR.xml missing required <{name}> text: {path}")
    return text


def _required_bilingual_text(root: ET.Element, name: str, path: Path) -> tuple[str, str]:
    child = root.find(name)
    if child is None:
        raise ValueError(f"FACTOR.xml missing required <{name}> element: {path}")
    zh = _child_text(child, "zh")
    en = _child_text(child, "en")
    if not zh or not en:
        raise ValueError(f"FACTOR.xml <{name}> must include non-empty <zh> and <en>: {path}")
    return zh, en


def _required_tag_labels(root: ET.Element, path: Path) -> list[FactorTagLabel]:
    parent = root.find("tag_labels")
    if parent is None:
        raise ValueError(f"FACTOR.xml missing required <tag_labels>: {path}")
    labels = []
    for child in list(parent):
        if child.tag != "tag":
            continue
        tag_type = (child.attrib.get("type") or "").strip()
        tag_value = (child.attrib.get("value") or "").strip()
        label_zh = _child_text(child, "zh")
        label_en = _child_text(child, "en")
        if not tag_type or not tag_value or not label_zh or not label_en:
            raise ValueError(f"FACTOR.xml invalid <tag> label; type, value, zh and en are required: {path}")
        labels.append(FactorTagLabel(type=tag_type, value=tag_value, label_zh=label_zh, label_en=label_en))
    if not labels:
        raise ValueError(f"FACTOR.xml <tag_labels> must include at least one <tag>: {path}")
    return labels


def _child_text(root: ET.Element, name: str) -> str:
    child = root.find(name)
    return child.text.strip() if child is not None and child.text else ""


def _bilingual_display(zh: str, en: str) -> str:
    return f"{zh} / {en}"


def _required_list(root: ET.Element, parent_name: str, item_name: str, path: Path) -> list[str]:
    parent = root.find(parent_name)
    values = [
        (child.text or "").strip()
        for child in list(parent) if child.tag == item_name
    ] if parent is not None else []
    values = [value for value in values if value]
    if not values:
        raise ValueError(f"FACTOR.xml missing required <{parent_name}><{item_name}> items: {path}")
    return values
