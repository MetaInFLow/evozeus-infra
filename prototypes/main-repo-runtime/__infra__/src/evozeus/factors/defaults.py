from __future__ import annotations

import re
from collections import Counter

from evozeus.factors.protocol import FactorResult, FactorStage
from evozeus.models import SessionEvent, Verdict

FRAMEWORK_ID = "agent_session_review.v0"
NEGATIVE_TERMS = ("不对", "失败", "报错", "卡住", "不行", "没改到", "偏离预期", "还是")
REWORK_TERMS = NEGATIVE_TERMS + ("继续", "重新", "重做", "改一下", "调整", "推翻", "重写")
TOOL_FAILURE_TERMS = ("error", "failed", "traceback", "exception", "timeout", "permission denied")
STOP_TERMS = {"这个", "那个", "继续", "重新", "之前", "需要", "可以", "进行", "一下", "修复"}
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+#.-]{1,}|[\u4e00-\u9fff]{2,}")


def run_default_factors(session_id: str, events: list[SessionEvent]) -> list[FactorResult]:
    results: list[FactorResult] = []
    negative = _negative_feedback_result(session_id, events)
    if negative:
        results.append(negative)
    rework = _same_target_rework_result(session_id, events)
    if rework:
        results.append(rework)
    tool_failure = _tool_failure_result(session_id, events)
    if tool_failure:
        results.append(tool_failure)
    return results


def _negative_feedback_result(session_id: str, events: list[SessionEvent]) -> FactorResult | None:
    refs = [
        {"ref_id": event.event_id, "kind": "user_turn"}
        for event in events
        if event.role == "user" and any(term in event.content for term in NEGATIVE_TERMS)
    ]
    if not refs:
        return None
    return FactorResult(
        factor_id="default.negative_feedback",
        framework_id=FRAMEWORK_ID,
        stage=FactorStage.SIGNAL_EXTRACTION,
        target_type="session",
        target_id=session_id,
        session_id=session_id,
        tags=[{"type": "negative_feedback", "value": "correction"}],
        scores={"negative_feedback": min(1.0, len(refs) / 3)},
        evidence_refs=refs,
        verdict_signals=[Verdict.PROMOTE_TO_SKILL.value],
        confidence=0.72,
    )


def _same_target_rework_result(session_id: str, events: list[SessionEvent]) -> FactorResult | None:
    user_events = [event for event in events if event.role == "user" and event.content.strip()]
    if len(user_events) < 2:
        return None

    token_sets = [_signature(event.content) for event in user_events]
    pair_refs: list[dict[str, str]] = []
    for left_index, left_tokens in enumerate(token_sets):
        for right_index in range(left_index + 1, len(token_sets)):
            if user_events[left_index].content.strip() == user_events[right_index].content.strip():
                continue
            if not any(term in user_events[right_index].content for term in REWORK_TERMS):
                continue
            overlap = left_tokens & token_sets[right_index]
            if overlap:
                pair_refs = [
                    {"ref_id": user_events[left_index].event_id, "kind": "user_turn"},
                    {"ref_id": user_events[right_index].event_id, "kind": "user_turn"},
                ]
                break
        if pair_refs:
            break

    if not pair_refs:
        return None
    return FactorResult(
        factor_id="default.same_target_rework",
        framework_id=FRAMEWORK_ID,
        stage=FactorStage.SIGNAL_EXTRACTION,
        target_type="session",
        target_id=session_id,
        session_id=session_id,
        tags=[{"type": "rework", "value": "same_target_rework"}],
        scores={"same_target_rework": 0.82},
        evidence_refs=pair_refs,
        verdict_signals=[Verdict.PROMOTE_TO_SKILL.value],
        confidence=0.78,
    )


def _tool_failure_result(session_id: str, events: list[SessionEvent]) -> FactorResult | None:
    failing_tools: Counter[str] = Counter()
    refs: list[dict[str, str]] = []
    for event in events:
        if event.role != "tool":
            continue
        payload = f"{event.content} {event.tool_result or {}}".lower()
        if any(term in payload for term in TOOL_FAILURE_TERMS):
            name = event.tool_name or "unknown_tool"
            failing_tools[name] += 1
            refs.append({"ref_id": event.event_id, "kind": "tool_event"})
    if not refs:
        return None
    tool_name = failing_tools.most_common(1)[0][0]
    return FactorResult(
        factor_id="default.tool_failure",
        framework_id=FRAMEWORK_ID,
        stage=FactorStage.SIGNAL_EXTRACTION,
        target_type="session",
        target_id=session_id,
        session_id=session_id,
        tags=[{"type": "tool_failure", "value": tool_name}],
        scores={"tool_failure": min(1.0, len(refs) / 3)},
        evidence_refs=refs,
        verdict_signals=[Verdict.FIX_ENVIRONMENT.value],
        confidence=0.8,
    )


def _signature(text: str) -> set[str]:
    tokens = {token.lower() for token in TOKEN_RE.findall(text)}
    return {token for token in tokens if token not in STOP_TERMS}
