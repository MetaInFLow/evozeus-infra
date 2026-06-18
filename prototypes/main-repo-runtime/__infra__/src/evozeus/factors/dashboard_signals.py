from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from evozeus.factors.defaults import FRAMEWORK_ID, TOOL_FAILURE_TERMS
from evozeus.factors.protocol import FactorResult, FactorStage
from evozeus.models import SessionEvent, Verdict

NEW_TASK_RE = re.compile(r"(顺便|另一个|换个|接下来|新任务)")
CONTINUE_RE = re.compile(r"(继续|补充|重新|改一下|不对|你理解错|还是)")
OPEN_LOOP_RE = re.compile(r"(待|还没|需要确认|后续|blocked|todo|TODO|未闭环)", re.IGNORECASE)
CORRECTION_RE = re.compile(r"(不对|失败|报错|卡住|不行|没改到|偏离预期|还是|继续|重新|你理解错)")
COMPLETE_RE = re.compile(r"(完成|已实现|通过|done|fixed|built|verified)", re.IGNORECASE)
VERIFY_RE = re.compile(r"(pytest|npm run build|npm test|pnpm test|curl|playwright|browser|截图|验证|验收|通过|passed|built)", re.IGNORECASE)
TASK_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+#.-]{1,}|[\u4e00-\u9fff]{2,}")
STOP_TERMS = {"这个", "那个", "继续", "重新", "之前", "需要", "可以", "进行", "一下", "修复"}


def task_span_extraction_result(session_id: str, events: list[SessionEvent], *, version: str = "") -> FactorResult:
    spans = _task_spans(events)
    if not spans:
        return _skipped("default.task_span_extraction", version, FactorStage.NORMALIZE, session_id)
    tags = [{"type": "task_span", "value": span["task_type"]} for span in spans]
    tags.extend({"type": "task_span_status", "value": span["status"]} for span in spans)
    evidence_refs = [
        {"ref_id": event_id, "kind": "user_turn"}
        for span in spans
        for event_id in span["user_event_ids"][:2]
    ]
    return FactorResult(
        factor_id="default.task_span_extraction",
        factor_version=version,
        framework_id=FRAMEWORK_ID,
        stage=FactorStage.NORMALIZE,
        target_type="session",
        target_id=session_id,
        session_id=session_id,
        tags=tags,
        scores={
            "task_span_count": float(len(spans)),
            "open_task_span_count": float(sum(1 for span in spans if span["status"] == "open")),
        },
        evidence_refs=evidence_refs,
        verdict_signals=[Verdict.OPEN_CASE.value],
        confidence=0.76,
    )


def open_loop_result(session_id: str, events: list[SessionEvent], *, version: str = "") -> FactorResult:
    refs = [
        {"ref_id": event.event_id, "kind": "user_turn"}
        for event in events
        if event.role == "user" and OPEN_LOOP_RE.search(event.content)
    ]
    open_span_count = sum(1 for span in _task_spans(events) if span["status"] == "open")
    count = max(len(refs), open_span_count)
    if count == 0:
        return _skipped("default.open_loop", version, FactorStage.SIGNAL_EXTRACTION, session_id)
    return FactorResult(
        factor_id="default.open_loop",
        factor_version=version,
        framework_id=FRAMEWORK_ID,
        stage=FactorStage.SIGNAL_EXTRACTION,
        target_type="session",
        target_id=session_id,
        session_id=session_id,
        tags=[{"type": "open_loop", "value": "follow_up_required"}],
        scores={"open_loop_count": float(count), "open_loop_pressure": min(1.0, count / 3)},
        evidence_refs=refs or _first_user_refs(events),
        verdict_signals=[Verdict.OPEN_CASE.value],
        confidence=0.78,
    )


def user_correction_loop_result(session_id: str, events: list[SessionEvent], *, version: str = "") -> FactorResult:
    refs = [
        {"ref_id": event.event_id, "kind": "user_turn"}
        for event in events
        if event.role == "user" and CORRECTION_RE.search(event.content)
    ]
    if len(refs) < 2:
        return _skipped("default.user_correction_loop", version, FactorStage.SIGNAL_EXTRACTION, session_id)
    return FactorResult(
        factor_id="default.user_correction_loop",
        factor_version=version,
        framework_id=FRAMEWORK_ID,
        stage=FactorStage.SIGNAL_EXTRACTION,
        target_type="session",
        target_id=session_id,
        session_id=session_id,
        tags=[{"type": "correction_loop", "value": "user_correction_loop"}],
        scores={"correction_count": float(len(refs)), "correction_intensity": min(1.0, len(refs) / 4)},
        evidence_refs=refs,
        verdict_signals=[Verdict.PROMOTE_TO_SKILL.value],
        confidence=0.8,
    )


def repeated_user_requests_result(session_id: str, events: list[SessionEvent], *, version: str = "") -> FactorResult:
    user_events = [event for event in events if event.role == "user" and event.content.strip()]
    repeated_pairs: list[tuple[SessionEvent, SessionEvent, float]] = []
    signatures = [_signature(event.content) for event in user_events]
    for left_index, left_signature in enumerate(signatures):
        for right_index in range(left_index + 1, len(signatures)):
            score = _jaccard(left_signature, signatures[right_index])
            if score >= 0.12:
                repeated_pairs.append((user_events[left_index], user_events[right_index], score))
    if not repeated_pairs:
        return _skipped("default.repeated_user_requests", version, FactorStage.SIGNAL_EXTRACTION, session_id)

    evidence_event_ids: list[str] = []
    for left, right, _score in repeated_pairs:
        evidence_event_ids.extend([left.event_id, right.event_id])
    evidence_refs = [{"ref_id": event_id, "kind": "user_turn"} for event_id in _dedupe(evidence_event_ids)]
    return FactorResult(
        factor_id="default.repeated_user_requests",
        factor_version=version,
        framework_id=FRAMEWORK_ID,
        stage=FactorStage.SIGNAL_EXTRACTION,
        target_type="session",
        target_id=session_id,
        session_id=session_id,
        tags=[{"type": "repeated_request", "value": "same_target"}],
        scores={
            "repeated_request_count": float(len(repeated_pairs)),
            "turn_similarity_density": min(1.0, len(repeated_pairs) / max(len(user_events), 1)),
        },
        evidence_refs=evidence_refs,
        verdict_signals=[Verdict.PROMOTE_TO_SKILL.value],
        confidence=0.78,
    )


def success_closure_quality_result(session_id: str, events: list[SessionEvent], *, version: str = "") -> FactorResult:
    assistant_text = "\n".join(event.content for event in events if event.role == "assistant")
    open_loop_count = len([event for event in events if event.role == "user" and OPEN_LOOP_RE.search(event.content)])
    tool_failure_count = _tool_failure_count(events)
    correction_count = len([event for event in events if event.role == "user" and CORRECTION_RE.search(event.content)])
    score = 0.7
    if COMPLETE_RE.search(assistant_text):
        score += 0.2
    if VERIFY_RE.search(assistant_text):
        score += 0.1
    score -= min(open_loop_count, 5) * 0.08
    score -= min(tool_failure_count, 10) * 0.015
    score -= min(correction_count, 5) * 0.04
    score = _clamp(score)
    status = "strong" if score >= 0.7 else "watch" if score >= 0.4 else "weak"
    refs = [
        {"ref_id": event.event_id, "kind": "user_turn"}
        for event in events
        if event.role == "user" and (OPEN_LOOP_RE.search(event.content) or CORRECTION_RE.search(event.content))
    ]
    return FactorResult(
        factor_id="default.success_closure_quality",
        factor_version=version,
        framework_id=FRAMEWORK_ID,
        stage=FactorStage.VERDICT_BUILDING,
        target_type="session",
        target_id=session_id,
        session_id=session_id,
        tags=[{"type": "success_factor", "value": f"closure_quality:{status}"}],
        scores={
            "closure_quality": score,
            "open_loop_count": float(open_loop_count),
            "tool_failure_count": float(tool_failure_count),
            "correction_count": float(correction_count),
        },
        evidence_refs=refs or _first_user_refs(events),
        verdict_signals=[Verdict.PROMOTE_TO_SKILL.value if status != "strong" else Verdict.PRESERVE.value],
        confidence=0.76,
    )


def _task_spans(events: list[SessionEvent]) -> list[dict[str, object]]:
    spans: list[dict[str, object]] = []
    event_ids: list[str] = []
    user_event_ids: list[str] = []
    user_texts: list[str] = []
    for event in events:
        if event.role == "user" and event_ids and NEW_TASK_RE.search(event.content):
            spans.append(_make_span(spans, event_ids, user_event_ids, user_texts, "new_task_regex"))
            event_ids = []
            user_event_ids = []
            user_texts = []
        event_ids.append(event.event_id)
        if event.role == "user":
            user_event_ids.append(event.event_id)
            user_texts.append(event.content)
    if event_ids:
        spans.append(_make_span(spans, event_ids, user_event_ids, user_texts, "session_end"))
    return spans


def _make_span(
    spans: list[dict[str, object]],
    event_ids: list[str],
    user_event_ids: list[str],
    user_texts: list[str],
    boundary_reason: str,
) -> dict[str, object]:
    user_blob = " ".join(user_texts)
    return {
        "task_span_id": f"task_{len(spans):04d}",
        "event_ids": list(event_ids),
        "user_event_ids": list(user_event_ids),
        "task_type": _classify_task_type(user_blob),
        "status": "open" if CONTINUE_RE.search(user_blob) or OPEN_LOOP_RE.search(user_blob) else "closed",
        "boundary_reason": boundary_reason,
    }


def _classify_task_type(text: str) -> str:
    lower = text.lower()
    if "review" in lower or "复盘" in text:
        return "review"
    if "bug" in lower or "修复" in text or "debug" in lower:
        return "debug"
    if "实现" in text or "开发" in text or "代码" in text:
        return "implementation"
    if "设计" in text or "schema" in lower or "prd" in lower or "文档" in text:
        return "design_doc"
    return "analysis"


def _tool_failure_count(events: list[SessionEvent]) -> int:
    count = 0
    for event in events:
        if event.role != "tool":
            continue
        payload = f"{event.content} {event.tool_result or {}}".lower()
        if any(term in payload for term in TOOL_FAILURE_TERMS):
            count += 1
    return count


def _signature(text: str) -> set[str]:
    tokens: list[str] = []
    for token in TASK_TOKEN_RE.findall(text):
        value = token.lower()
        if value in STOP_TERMS:
            continue
        tokens.append(value)
        if re.fullmatch(r"[\u4e00-\u9fff]{3,}", value):
            tokens.extend(value[index : index + 2] for index in range(0, max(len(value) - 1, 0)))
    return set(tokens)


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _first_user_refs(events: list[SessionEvent]) -> list[dict[str, str]]:
    return [{"ref_id": event.event_id, "kind": "user_turn"} for event in events if event.role == "user"][:1]


def _skipped(factor_id: str, version: str, stage: FactorStage, session_id: str) -> FactorResult:
    return FactorResult(
        factor_id=factor_id,
        factor_version=version,
        framework_id=FRAMEWORK_ID,
        stage=stage,
        target_type="session",
        target_id=session_id,
        session_id=session_id,
        status="skipped",
        confidence=0.0,
    )


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
