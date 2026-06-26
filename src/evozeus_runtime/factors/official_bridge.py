from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import inspect
import json
import sys
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

from evozeus_runtime.factors.base import Factor, FactorContext
from evozeus_runtime.factors.manifest import load_manifest
from evozeus_runtime.factors.protocol import FactorResult, FactorStage


FRAMEWORK_ID = "evozeus.official"
DEFAULT_TIMEOUT_MS = 10000

COMPONENT_REF_MAP = {
    "builtin.word_cloud.v1": "ui.native-static.word-cloud.v1",
    "builtin.bar_chart.v1": "ui.native-static.bar-chart.v1",
    "builtin.line_chart.v1": "ui.native-static.line-chart.v1",
    "builtin.heatmap.v1": "ui.native-static.heatmap.v1",
    "builtin.table.v1": "ui.native-static.table.v1",
    "builtin.json.v1": "ui.native-static.json.v1",
}

ROUTE_MAP = {
    "dashboard": "canvas.global.insights",
    "drawer": "session.detail.factor_drawer",
}
MAX_EVIDENCE_REFS_PER_RESULT = 200


@dataclass(frozen=True)
class OfficialFactorPackBuildResult:
    pack_root: Path
    factor_ids: list[str]


@dataclass(frozen=True)
class OfficialFactorInfo:
    slug: str
    class_name: str
    factor_id: str
    version: str
    title: str
    title_zh: str
    title_en: str
    summary: str
    summary_zh: str
    summary_en: str
    stage: str
    outputs: list[str]
    verdict_signals: list[str]
    owner: str
    input_channels: list[str]
    required_python_packages: list[str]
    source_factor_xml: str


class OfficialFactorPackBuilder:
    def __init__(self, *, official_repo_root: Path, output_pack_root: Path):
        self.official_repo_root = official_repo_root.resolve()
        self.output_pack_root = output_pack_root.resolve()

    def build(self) -> OfficialFactorPackBuildResult:
        factor_root = self.official_repo_root / "factors"
        if not factor_root.is_dir():
            raise FileNotFoundError(f"official factor root not found: {factor_root}")

        factor_ids: list[str] = []
        self.output_pack_root.mkdir(parents=True, exist_ok=True)
        for factor_dir in sorted(path for path in factor_root.iterdir() if path.is_dir()):
            info = _load_official_factor_info(self.official_repo_root, factor_dir)
            pack_dir = self.output_pack_root / info.factor_id / info.version
            pack_dir.mkdir(parents=True, exist_ok=True)
            _write_pack_files(pack_dir, self.official_repo_root, info)
            factor_ids.append(info.factor_id)
        return OfficialFactorPackBuildResult(pack_root=self.output_pack_root, factor_ids=factor_ids)


class OfficialRuntimeAdapter(Factor):
    def __init__(self) -> None:
        pack_root = Path(getattr(self.__class__, "PACK_ROOT")).resolve()
        self.manifest = load_manifest(pack_root / "factor.json")
        self._official_factor = _load_official_factor(
            Path(str(self.manifest.run["official_repo_root"])),
            str(self.manifest.run["factor_slug"]),
            str(self.manifest.run["factor_class"]),
        )

    def run(self, context: FactorContext) -> FactorResult:
        official_result = self._official_factor.evaluate(_official_context(context))
        return _to_runtime_result(official_result, context.session.session_id, self.manifest.framework_id)


def _write_pack_files(pack_dir: Path, official_repo_root: Path, info: OfficialFactorInfo) -> None:
    manifest = {
        "schema_version": "factor.v0",
        "id": info.factor_id,
        "name": f"{info.title_zh} / {info.title_en}",
        "framework_id": FRAMEWORK_ID,
        "stage": info.stage,
        "runtime_profile": "default",
        "default_enabled": False,
        "inputs": ["SessionEnvelope"],
        "outputs": info.outputs,
        "evidence_policy": {
            "required": True,
            "min_refs": 1,
            "raw_content_allowed": False,
        },
        "verdict_signals": info.verdict_signals,
        "version": info.version,
        "status": "available",
        "description": f"Runtime bridge for {info.factor_id}.",
        "entrypoint": "factor:OfficialFactorPackAdapter",
        "permissions": ["read_session_events"],
        "risks": ["aggregate_session_metadata"],
        "rollback": "Remove this generated official factor pack.",
        "runtime": {"mode": "in_process", "timeout_ms": DEFAULT_TIMEOUT_MS},
        "compatibility": {"evozeus_protocol": ">=0.1.0"},
        "network": False,
        "run": {
            "official_repo_root": str(official_repo_root),
            "factor_slug": info.slug,
            "factor_class": info.class_name,
            "input_channels": ",".join(info.input_channels),
            "required_python_packages": ",".join(info.required_python_packages),
        },
    }
    (pack_dir / "factor.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (pack_dir / "FACTOR.xml").write_text(info.source_factor_xml, encoding="utf-8")
    (pack_dir / "factor.py").write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "",
                "from evozeus_runtime.factors.official_bridge import OfficialRuntimeAdapter",
                "",
                "",
                "class OfficialFactorPackAdapter(OfficialRuntimeAdapter):",
                "    PACK_ROOT = Path(__file__).resolve().parent",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _factor_xml(info: OfficialFactorInfo) -> str:
    outputs_xml = "".join(f"    <output>{xml_escape(output)}</output>\n" for output in info.outputs)
    return f"""<factor id="{xml_escape(info.factor_id)}" version="{xml_escape(info.version)}">
  <name>
    <zh>{xml_escape(info.title_zh)}</zh>
    <en>{xml_escape(info.title_en)}</en>
  </name>
  <summary>
    <zh>{xml_escape(info.summary_zh)}</zh>
    <en>{xml_escape(info.summary_en)}</en>
  </summary>
  <category>official</category>
  <stage>{xml_escape(info.stage)}</stage>
  <runtime>in_process</runtime>
  <inputs>
    <input>SessionEnvelope</input>
  </inputs>
  <outputs>
{outputs_xml}
  </outputs>
  <when_to_use>
    <zh>{xml_escape(info.summary_zh)}</zh>
    <en>{xml_escape(info.summary_en)}</en>
  </when_to_use>
  <limitations>
    <zh>使用 redacted session event 和聚合结果，不保存 raw session 正文。</zh>
    <en>Uses redacted session events and aggregate outputs; raw session content is not stored.</en>
  </limitations>
  <privacy>
    <zh>只落结构化标签、分数、dataset、presentation 和 evidence ref。</zh>
    <en>Stores structured tags, scores, datasets, presentations, and evidence refs only.</en>
  </privacy>
  <tag_labels>
    <tag type="official_factor" value="matched">
      <zh>Official factor 命中</zh>
      <en>Official factor matched</en>
    </tag>
  </tag_labels>
</factor>
"""


def _load_official_factor_info(official_repo_root: Path, factor_dir: Path) -> OfficialFactorInfo:
    source_contract = _load_source_factor_contract(factor_dir / "FACTOR.xml")
    official_factor = _load_official_factor(official_repo_root, factor_dir.name)
    spec = dict(official_factor.spec)
    output_contract = spec.get("output_contract") if isinstance(spec.get("output_contract"), dict) else {}
    title_i18n = spec.get("title_i18n") if isinstance(spec.get("title_i18n"), dict) else {}
    summary_i18n = spec.get("summary_i18n") if isinstance(spec.get("summary_i18n"), dict) else {}
    if source_contract["factor_id"] != str(spec["factor_id"]):
        raise ValueError(f"FACTOR.xml id does not match factor.py spec in {factor_dir}")
    if source_contract["version"] != str(spec["version"]):
        raise ValueError(f"FACTOR.xml version does not match factor.py spec in {factor_dir}")
    return OfficialFactorInfo(
        slug=factor_dir.name,
        class_name=official_factor.__class__.__name__,
        factor_id=source_contract["factor_id"],
        version=source_contract["version"],
        title=str(spec.get("title") or spec["factor_id"]),
        title_zh=str(title_i18n.get("zh-CN") or spec.get("title") or spec["factor_id"]),
        title_en=str(title_i18n.get("en-US") or spec.get("title") or spec["factor_id"]),
        summary=source_contract["summary_en"],
        summary_zh=source_contract["summary_zh"],
        summary_en=source_contract["summary_en"],
        stage=source_contract["stage"],
        outputs=source_contract["outputs"]
        or [str(item) for item in output_contract.get("dataset_semantic_types", [])]
        or ["official_factor_result"],
        verdict_signals=[str(item) for item in spec.get("verdict_signals", [])] or [str(spec["factor_id"])],
        owner=source_contract["owner"],
        input_channels=source_contract["input_channels"],
        required_python_packages=source_contract["required_python_packages"],
        source_factor_xml=source_contract["source_factor_xml"],
    )


def _load_source_factor_contract(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"official source factor missing FACTOR.xml: {path}")
    text = path.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    if root.tag != "factor":
        raise ValueError(f"FACTOR.xml root element must be <factor>: {path}")
    factor_id = str(root.attrib.get("id") or "").strip()
    version = str(root.attrib.get("version") or "").strip()
    outputs = [
        str(dataset.attrib.get("semantic_type") or "").strip()
        for dataset in root.findall("output_datasets/dataset")
        if str(dataset.attrib.get("semantic_type") or "").strip()
    ]
    return {
        "factor_id": factor_id,
        "version": version,
        "owner": _text(root, "owner"),
        "stage": _text(root, "stage") or "signal_extraction",
        "summary_zh": _child_text(root.find("summary"), "zh"),
        "summary_en": _child_text(root.find("summary"), "en"),
        "outputs": outputs,
        "input_channels": [
            str(child.text or "").strip()
            for child in root.findall("input_channels/channel")
            if str(child.text or "").strip()
        ],
        "required_python_packages": [
            str(child.attrib.get("name") or child.text or "").strip()
            for child in root.findall("dependencies/package")
            if str(child.attrib.get("required") or "true").lower() != "false"
            and str(child.attrib.get("name") or child.text or "").strip()
        ],
        "source_factor_xml": text if text.endswith("\n") else text + "\n",
    }


def _text(root: ET.Element, name: str) -> str:
    child = root.find(name)
    return str(child.text or "").strip() if child is not None else ""


def _child_text(root: ET.Element | None, name: str) -> str:
    if root is None:
        return ""
    child = root.find(name)
    return str(child.text or "").strip() if child is not None else ""


def _load_official_factor(official_repo_root: Path, slug: str, class_name: str = "") -> Any:
    official_src = official_repo_root / "src"
    if str(official_src) not in sys.path:
        sys.path.insert(0, str(official_src))

    module_path = official_repo_root / "factors" / slug / "factor.py"
    spec = importlib.util.spec_from_file_location(f"evozeus_official_{slug.replace('-', '_')}", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load official factor: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if class_name:
        return getattr(module, class_name)()

    candidates = []
    for value in module.__dict__.values():
        if not inspect.isclass(value) or value.__module__ != module.__name__:
            continue
        if not hasattr(value, "evaluate"):
            continue
        try:
            instance = value()
        except TypeError:
            continue
        if hasattr(instance, "spec") and isinstance(instance.spec, dict) and instance.spec.get("factor_id"):
            candidates.append(instance)
    if not candidates:
        raise ImportError(f"cannot find official factor class in {module_path}")
    return candidates[0]


def _official_context(context: FactorContext) -> dict[str, Any]:
    events = []
    for event in context.session.events:
        payload = {
            **event.metadata,
            "id": event.event_id,
            "role": event.role,
            "text": event.content,
            "tool_name": event.tool_name or "",
            "tool_result": event.tool_result or {},
            "timestamp": str(event.metadata.get("timestamp") or event.metadata.get("created_at") or ""),
        }
        events.append(payload)
    return {
        "session_id": context.session.session_id,
        "events": events,
        "metadata": dict(context.session.metadata),
    }


def _to_runtime_result(official_result: Any, session_id: str, framework_id: str) -> FactorResult:
    datasets = [_compact_dataset(dataset.as_dict() if hasattr(dataset, "as_dict") else dict(dataset)) for dataset in official_result.datasets]
    presentations = [
        _normalize_presentation(presentation.as_dict() if hasattr(presentation, "as_dict") else dict(presentation))
        for presentation in official_result.presentations
    ]
    return FactorResult(
        factor_id=str(official_result.factor_id),
        factor_version=str(official_result.version),
        framework_id=framework_id,
        stage=FactorStage(str(official_result.stage)),
        target_type=str(official_result.target_type),
        target_id=str(official_result.target_id or session_id),
        session_id=session_id,
        status=str(official_result.status),
        tags=_compact_tags([dict(tag) for tag in official_result.tags]),
        scores={str(key): float(value) for key, value in dict(official_result.scores).items()},
        statistics=dict(official_result.statistics),
        datasets=datasets,
        presentations=presentations,
        evidence_refs=_compact_evidence_refs(
            [{str(key): str(value) for key, value in dict(ref).items()} for ref in official_result.evidence_refs]
        ),
        verdict_signals=[str(item) for item in official_result.verdict_signals],
        notes=[str(item) for item in official_result.notes],
        confidence=float(official_result.confidence),
    )


def _compact_tags(tags: list[dict[str, str]]) -> list[dict[str, str]]:
    compact: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for tag in tags:
        tag_type = str(tag.get("type") or "")
        tag_value = str(tag.get("value") or "")
        if not tag_type or not tag_value:
            continue
        if len(tag_value) > 80:
            continue
        key = (tag_type, tag_value)
        if key in seen:
            continue
        seen.add(key)
        compact.append({"type": tag_type, "value": tag_value})
    return compact[:12]


def _compact_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    records = dataset.get("records")
    if isinstance(records, list):
        dataset = {**dataset, "records": [_compact_record(record) for record in records[:50] if isinstance(record, dict)]}
    return dataset


def _compact_evidence_refs(evidence_refs: list[dict[str, str]]) -> list[dict[str, str]]:
    compact: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for ref in evidence_refs:
        ref_id = str(ref.get("ref_id") or ref.get("event_id") or "")
        kind = str(ref.get("kind") or ref.get("source") or "")
        if not ref_id:
            continue
        key = (ref_id, kind)
        if key in seen:
            continue
        seen.add(key)
        compact.append(ref)
        if len(compact) >= MAX_EVIDENCE_REFS_PER_RESULT:
            break
    return compact


def _compact_record(record: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(value, str):
            compact[key] = value[:240]
        elif isinstance(value, list):
            compact[key] = value[:10]
        else:
            compact[key] = value
    return compact


def _normalize_presentation(presentation: dict[str, Any]) -> dict[str, Any]:
    component_ref = str(presentation.get("component_ref") or "")
    fallback = presentation.get("fallback")
    routes = presentation.get("routes")
    return {
        **presentation,
        "component_ref": COMPONENT_REF_MAP.get(component_ref, component_ref),
        "fallback": [COMPONENT_REF_MAP.get(str(item), str(item)) for item in fallback] if isinstance(fallback, list) else [],
        "routes": [ROUTE_MAP.get(str(item), str(item)) for item in routes] if isinstance(routes, list) else [],
    }
