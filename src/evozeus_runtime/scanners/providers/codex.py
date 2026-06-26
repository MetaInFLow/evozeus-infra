from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from evozeus_runtime.sessions.schema import SessionEnvelope
from evozeus_runtime.sessions.schema import SessionEvent
from evozeus_runtime.scanners.base import ScanRequest, SessionMessageRef, SessionRef, SessionScanner
from evozeus_runtime.sessions.locator import EventLocator, ResolvedEvent

TOOL_RESPONSE_ITEM_TYPES = {
    "function_call",
    "function_call_output",
    "custom_tool_call",
    "custom_tool_call_output",
    "web_search_call",
}
SCANNER_ID = "codex"
SCANNER_VERSION = "0.1.0"
SOURCE_LOCATOR_SCHEMA = "locator.codex_jsonl.v0"
ARTIFACT_LOCATOR_SCHEMA = "locator.evozeus_artifact_jsonl.v0"
SOURCE_ID_MANIFEST_NAMES = {"codex-source-ids.jsonl", ".codex-source-ids.jsonl"}
SESSION_INDEX_NAME = "session_index.jsonl"
CODEX_SESSION_ROOT_NAMES = {"sessions", "archived_sessions"}
SECRET_RE = re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*\S+")
REQUEST_MARKER_RE = re.compile(r"##\s*My request for Codex:\s*", re.I)
CONTEXT_MARKERS = (
    "# agents.md instructions",
    "<environment_context>",
    "<instructions>",
    "<goal_context>",
    "<turn_aborted>",
    "continue working toward the active thread goal",
)


class CodexScanner(SessionScanner):
    provider = "codex"
    scanner_id = SCANNER_ID
    scanner_version = SCANNER_VERSION

    def source_dirs(self, request: ScanRequest) -> list[Path]:
        return _source_dirs(request)

    def can_discover(self, request: ScanRequest) -> bool:
        return any(
            source_dir.exists()
            and any(_is_direct_session_source(path) or _is_source_id_manifest(path) for path in source_dir.rglob("*.jsonl"))
            for source_dir in _source_dirs(request)
        )

    def discover(self, request: ScanRequest) -> list[SessionRef]:
        discovered = _discover_source_paths(request)
        refs = [_session_ref_from_source(self.provider, path, extra_metadata) for path, extra_metadata in discovered]
        refs = _sort_session_refs(refs)
        if request.limit is not None:
            refs = refs[: request.limit]
        return refs

    def discover_message_refs(self, ref: SessionRef) -> list[SessionMessageRef]:
        message_refs: list[SessionMessageRef] = []
        source_fingerprint = str(ref.metadata.get("source_fingerprint") or _source_fingerprint(ref.source_path))
        session_id = ref.session_id
        message_index = 0
        for raw_line_index, record in _iter_jsonl_records(ref.source_path):
            embedded_session_id = _session_id_from_record(record)
            if embedded_session_id is not None:
                if session_id == ref.source_path.stem:
                    session_id = embedded_session_id
                continue

            message_id = _message_id_from_record(message_index + 1, raw_line_index, record)
            if message_id is None:
                continue
            message_index += 1
            message_metadata = _message_ref_metadata_from_record(record)
            if not _should_index_message_ref(message_metadata):
                continue
            message_refs.append(
                SessionMessageRef(
                    provider=self.provider,
                    session_id=session_id,
                    message_id=message_id,
                    source_path=ref.source_path,
                    message_index=message_index,
                    metadata={
                        "scanner_id": SCANNER_ID,
                        "scanner_version": SCANNER_VERSION,
                        "source_ref": str(ref.source_path),
                        "source_fingerprint": source_fingerprint,
                        **message_metadata,
                        "event_locator_json": json.dumps(
                            _event_locator(
                                record,
                                source_path=ref.source_path,
                                raw_line_index=raw_line_index,
                                session_id=session_id,
                                event_id=message_id,
                            ),
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    },
                )
            )
        return message_refs

    def iter_events(self, ref: SessionRef) -> Iterator[SessionEvent]:
        session_id = ref.session_id
        source_fingerprint = str(ref.metadata.get("source_fingerprint") or _source_fingerprint(ref.source_path))
        event_index = 0
        previous_event: SessionEvent | None = None
        for index, record in _iter_jsonl_records(ref.source_path):
            embedded_session_id = _session_id_from_record(record)
            if embedded_session_id is not None:
                if session_id == ref.source_path.stem:
                    session_id = embedded_session_id
                continue

            event = _event_from_payload(index, record)
            if event is not None:
                event_index += 1
                event = _with_locator(
                    event,
                    record=record,
                    source_path=ref.source_path,
                    source_fingerprint=source_fingerprint,
                    raw_line_index=index,
                    event_index=event_index,
                    session_id=session_id,
                )
                if previous_event is not None and _is_mirrored_message_event(previous_event, event):
                    event_index -= 1
                    continue
                previous_event = event
                yield event

    def load(self, ref: SessionRef) -> SessionEnvelope:
        events = list(self.iter_events(ref))
        source_fingerprint = str(ref.metadata.get("source_fingerprint") or _source_fingerprint(ref.source_path))
        return SessionEnvelope(
            session_id=_loaded_session_id(ref, events),
            provider=self.provider,
            source_ref=str(ref.source_path),
            events=events,
            metadata={
                "scanner_id": SCANNER_ID,
                "scanner_version": SCANNER_VERSION,
                "source_fingerprint": source_fingerprint,
                "session_title": str(ref.metadata.get("session_title") or ""),
                "session_cwd": str(ref.metadata.get("session_cwd") or ""),
                "session_group_key": str(ref.metadata.get("session_group_key") or ""),
                "session_group_label": str(ref.metadata.get("session_group_label") or ""),
                "session_updated_at": str(ref.metadata.get("session_updated_at") or ""),
                "malformed_jsonl_line_count": str(_malformed_jsonl_line_count(ref.source_path)),
            },
        )


def _session_id_from_record(record: dict[str, Any]) -> str | None:
    payload = record.get("payload")
    if record.get("type") != "session_meta":
        return None
    if isinstance(payload, dict):
        for key in ("id", "session_id", "sessionId"):
            if payload.get(key):
                return str(payload[key])
    for key in ("id", "session_id", "sessionId"):
        if record.get(key):
            return str(record[key])
    return None


def _discover_session_id(path: Path) -> str:
    inspected = 0
    for _, record in _iter_jsonl_records(path):
        inspected += 1
        if inspected > 100:
            break
        session_id = _session_id_from_record(record)
        if session_id is not None:
            return session_id
    return path.stem


def _event_from_payload(index: int, record: dict[str, Any]) -> SessionEvent | None:
    payload = record.get("payload")
    if isinstance(payload, dict):
        return _event_from_wrapped_payload(index, record, payload)
    return _event_from_flat_payload(index, record)


def _event_from_flat_payload(index: int, payload: dict[str, Any]) -> SessionEvent:
    event_id = str(payload.get("event_id") or payload.get("id") or f"event_{index:04d}")
    role = str(payload.get("role") or payload.get("type") or "unknown")
    content = _string_content(payload.get("content") or payload.get("text") or "")
    tool_result = payload.get("tool_result")
    return SessionEvent(
        event_id=event_id,
        role=role,
        content=content,
        tool_name=payload.get("tool_name"),
        tool_result=tool_result if isinstance(tool_result, dict) else None,
        metadata={"provider": "codex"},
    )


def _event_from_wrapped_payload(index: int, record: dict[str, Any], payload: dict[str, Any]) -> SessionEvent | None:
    wrapper_type = str(record.get("type") or "unknown")
    if wrapper_type == "session_meta":
        return None

    event_type = str(payload.get("type") or wrapper_type)
    event_id = _wrapped_event_id(index, record, payload)

    if wrapper_type == "response_item":
        if event_type in TOOL_RESPONSE_ITEM_TYPES:
            return _tool_response_item_event(event_id, wrapper_type, event_type, payload)
        return SessionEvent(
            event_id=event_id,
            role=str(payload.get("role") or event_type),
            content=_response_content(payload),
            metadata={"provider": "codex", "codex_record_type": wrapper_type, "codex_event_type": event_type},
        )

    if wrapper_type == "event_msg":
        if event_type == "task_complete":
            return SessionEvent(
                event_id=event_id,
                role="task_complete",
                content="Task complete",
                metadata={
                    "provider": "codex",
                    "codex_record_type": wrapper_type,
                    "codex_event_type": event_type,
                    "task_completed_at": str(payload.get("completed_at") or ""),
                    "task_duration_ms": str(payload.get("duration_ms") or ""),
                },
            )
        message = payload.get("message") or payload.get("last_agent_message") or payload.get("content") or payload.get("text")
        role = _event_msg_role(event_type, payload)
        tool_result = {"message": _string_content(message)} if role == "tool" and message is not None else None
        return SessionEvent(
            event_id=event_id,
            role=role,
            content=_string_content(message),
            tool_name=event_type if role == "tool" else None,
            tool_result=tool_result,
            metadata={"provider": "codex", "codex_record_type": wrapper_type, "codex_event_type": event_type},
        )

    return SessionEvent(
        event_id=event_id,
        role=str(payload.get("role") or event_type),
        content=_response_content(payload),
        metadata={"provider": "codex", "codex_record_type": wrapper_type, "codex_event_type": event_type},
    )


def _wrapped_event_id(index: int, record: dict[str, Any], payload: dict[str, Any]) -> str:
    explicit_id = payload.get("id") or record.get("id")
    if explicit_id:
        return str(explicit_id)
    timestamp = record.get("timestamp")
    if timestamp:
        return f"{timestamp}#L{index}"
    return f"event_{index:04d}"


def _message_id_from_record(message_index: int, raw_line_index: int, record: dict[str, Any]) -> str | None:
    if record.get("type") == "session_meta":
        return None
    payload = record.get("payload")
    if isinstance(payload, dict):
        return _wrapped_event_id(raw_line_index, record, payload)
    return str(record.get("event_id") or record.get("id") or f"event_{raw_line_index:04d}")


def _message_ref_metadata_from_record(record: dict[str, Any]) -> dict[str, str]:
    wrapper_type = str(record.get("type") or "flat")
    payload = record.get("payload")
    if isinstance(payload, dict):
        event_type = str(payload.get("type") or wrapper_type)
        role = _message_ref_role(wrapper_type, event_type, payload)
        tool_name = _message_ref_tool_name(role, event_type, payload)
        metadata = {
            "role": role,
            "tool_name": tool_name,
            "record_type": wrapper_type,
            "payload_type": event_type,
        }
        event = _event_from_payload(0, record)
        if event is not None:
            metadata.update(_channel_metadata(event))
        return metadata
    role = str(record.get("role") or record.get("type") or "unknown")
    metadata = {
        "role": role,
        "tool_name": str(record.get("tool_name") or ""),
        "record_type": "flat",
        "payload_type": role,
    }
    metadata.update(_channel_metadata(_event_from_flat_payload(0, record)))
    return metadata


INDEXED_MESSAGE_CHANNELS = {"user_input", "assistant_result", "tool_usage"}


def _should_index_message_ref(metadata: dict[str, str]) -> bool:
    return str(metadata.get("factor_channel") or "") in INDEXED_MESSAGE_CHANNELS


def _message_ref_role(wrapper_type: str, event_type: str, payload: dict[str, Any]) -> str:
    if wrapper_type == "response_item" and event_type in TOOL_RESPONSE_ITEM_TYPES:
        return "tool"
    if wrapper_type == "event_msg" and event_type == "task_complete":
        return "task_complete"
    if wrapper_type == "event_msg":
        return _event_msg_role(event_type, payload)
    return str(payload.get("role") or event_type)


def _message_ref_tool_name(role: str, event_type: str, payload: dict[str, Any]) -> str:
    if role != "tool":
        return ""
    return str(payload.get("name") or event_type)


def _tool_response_item_event(
    event_id: str,
    wrapper_type: str,
    event_type: str,
    payload: dict[str, Any],
) -> SessionEvent:
    tool_result = _tool_result_payload(payload)
    return SessionEvent(
        event_id=event_id,
        role="tool",
        content=_tool_content(payload),
        tool_name=str(payload.get("name") or event_type),
        tool_result=tool_result,
        metadata={"provider": "codex", "codex_record_type": wrapper_type, "codex_event_type": event_type},
    )


def _event_msg_role(event_type: str, payload: dict[str, Any]) -> str:
    if payload.get("role"):
        return str(payload["role"])
    if event_type in {"agent_message", "assistant_message"} or payload.get("last_agent_message") is not None:
        return "assistant"
    if event_type in {"user_message", "user"}:
        return "user"
    if event_type in {"exec_command", "tool_call", "tool_result", "function_call", "function_call_output"}:
        return "tool"
    if payload.get("message") is not None and event_type.endswith("_command"):
        return "tool"
    return "event"


def _tool_result_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ("arguments", "input", "output", "status", "call_id"):
        if key in payload:
            result[key] = payload[key]
    return result


def _tool_content(payload: dict[str, Any]) -> str:
    for key in ("output", "arguments", "input", "status"):
        if key in payload:
            return _string_content(payload[key])
    return ""


def _response_content(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or item.get("message")
                if text is not None:
                    parts.append(_string_content(text))
        if parts:
            return "\n".join(parts)
    return _string_content(content or payload.get("text") or payload.get("message") or "")


def _string_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class CodexSourceResolver:
    scanner_id = SCANNER_ID
    scanner_version = SCANNER_VERSION

    def resolve_event(self, locator: EventLocator) -> ResolvedEvent:
        if locator.scanner_id != SCANNER_ID or locator.scanner_version != SCANNER_VERSION:
            raise ValueError("unsupported codex locator version")
        if locator.locator_schema != SOURCE_LOCATOR_SCHEMA:
            raise ValueError("unsupported codex locator schema")
        source_path = Path(str(locator.payload.get("source_path") or ""))
        line_start = int(locator.payload.get("line_start") or 0)
        if line_start < 1:
            raise ValueError("locator line_start must be >= 1")
        record = _read_jsonl_record(source_path, line_start)
        event = _event_from_payload(line_start, record)
        if event is None:
            raise ValueError("locator does not point to a codex event")
        content_hash = _content_hash(event.content)
        return ResolvedEvent(
            scanner_id=SCANNER_ID,
            scanner_version=SCANNER_VERSION,
            session_id=str(locator.payload.get("session_id") or ""),
            event_id=str(locator.payload.get("event_id") or event.event_id),
            source_ref=str(source_path),
            content=event.content,
            content_hash=content_hash,
            metadata={"locator_schema": locator.locator_schema},
        )

    def verify_hash(self, resolved: ResolvedEvent, expected_hash: str) -> bool:
        return resolved.content_hash == expected_hash


def _with_locator(
    event: SessionEvent,
    *,
    record: dict[str, Any],
    source_path: Path,
    source_fingerprint: str,
    raw_line_index: int,
    event_index: int,
    session_id: str,
) -> SessionEvent:
    metadata = dict(event.metadata)
    content_hash = _content_hash(event.content)
    channel_metadata = _channel_metadata(event)
    metadata.update(
        {
            "provider": "codex",
            "scanner_id": SCANNER_ID,
            "scanner_version": SCANNER_VERSION,
            **channel_metadata,
            "source_ref": str(source_path),
            "source_fingerprint": source_fingerprint,
            "content_hash": content_hash,
            "content_preview_redacted": _preview(event.content),
            "tool_result_hash": _content_hash(_string_content(event.tool_result or {})) if event.tool_result else "",
            "tool_result_preview_redacted": _preview(_string_content(event.tool_result or {})) if event.tool_result else "",
            "event_locator_json": _event_locator(
                record,
                source_path=source_path,
                raw_line_index=raw_line_index,
                session_id=session_id,
                event_id=event.event_id,
            ),
            "artifact_locator_json": _artifact_locator(
                session_id=session_id,
                event_id=event.event_id,
                event_index=event_index,
            ),
        }
    )
    return event.model_copy(update={"metadata": metadata})


def _channel_metadata(event: SessionEvent) -> dict[str, str]:
    raw_role = event.role
    content_kind = _content_kind(event)
    factor_channel = _factor_channel(event, content_kind)
    chat_role = _chat_role(event, factor_channel)
    factor_preview = _preview(_factor_text_for_preview(event, content_kind))
    return {
        "raw_role": raw_role,
        "chat_role": chat_role,
        "content_kind": content_kind,
        "factor_channel": factor_channel,
        "factor_text_preview": factor_preview,
    }


def _content_kind(event: SessionEvent) -> str:
    role = event.role
    if role == "user":
        return _user_content_kind(event.content)
    if role == "assistant":
        return "assistant_message"
    if role == "task_complete":
        return "task_complete"
    if role == "tool":
        event_type = str(event.metadata.get("codex_event_type") or "")
        if event_type in {"function_call", "custom_tool_call", "web_search_call"}:
            return "tool_call"
        if event_type in {"function_call_output", "custom_tool_call_output"}:
            return "tool_output"
        return "tool_output" if event.tool_result is not None else "tool_call"
    if role in {"system", "developer"}:
        return "system_context"
    return "codex_event"


def _user_content_kind(content: str) -> str:
    text = content.strip()
    lowered = text.lower()
    if REQUEST_MARKER_RE.search(text) is not None:
        return "real_user_message"
    if not text:
        return "empty"
    if "<image" in lowered:
        return "image_payload"
    if any(marker in lowered for marker in CONTEXT_MARKERS):
        return "codex_context"
    return "real_user_message"


def _factor_channel(event: SessionEvent, content_kind: str) -> str:
    if content_kind == "real_user_message":
        return "user_input"
    if content_kind in {"codex_context", "image_payload", "system_context", "empty", "codex_event"}:
        return "context"
    if content_kind == "assistant_message" or content_kind == "task_complete":
        return "assistant_result"
    if content_kind == "tool_call":
        return "tool_usage"
    if content_kind == "tool_output":
        return "tool_result"
    if event.role == "tool":
        return "tool_result"
    return "context"


def _chat_role(event: SessionEvent, factor_channel: str) -> str:
    if factor_channel == "user_input":
        return "user"
    if factor_channel == "assistant_result":
        return "assistant"
    if factor_channel in {"tool_usage", "tool_result"}:
        return "tool"
    return "context"


def _factor_text_for_preview(event: SessionEvent, content_kind: str) -> str:
    if content_kind == "real_user_message":
        return _extract_user_request(event.content)
    return event.content


def _extract_user_request(content: str) -> str:
    marker = REQUEST_MARKER_RE.search(content)
    if marker is None:
        return content.strip()
    return content[marker.end() :].strip()


def _event_locator(
    record: dict[str, Any],
    *,
    source_path: Path,
    raw_line_index: int,
    session_id: str,
    event_id: str,
) -> dict[str, Any]:
    payload = record.get("payload")
    payload_type = payload.get("type") if isinstance(payload, dict) else record.get("type")
    return {
        "schema_version": "locator.v0",
        "scanner_id": SCANNER_ID,
        "scanner_version": SCANNER_VERSION,
        "locator_schema": SOURCE_LOCATOR_SCHEMA,
        "kind": "source_event",
        "payload": {
            "source_path": str(source_path),
            "line_start": raw_line_index,
            "line_end": raw_line_index,
            "record_type": str(record.get("type") or "flat"),
            "payload_type": str(payload_type or ""),
            "session_id": session_id,
            "event_id": event_id,
        },
    }


def _artifact_locator(*, session_id: str, event_id: str, event_index: int) -> dict[str, Any]:
    return {
        "schema_version": "locator.v0",
        "scanner_id": SCANNER_ID,
        "scanner_version": SCANNER_VERSION,
        "locator_schema": ARTIFACT_LOCATOR_SCHEMA,
        "kind": "normalized_artifact_event",
        "payload": {
            "artifact_path": f".evozeus/sessions/{session_id}/events.jsonl",
            "line_start": event_index,
            "line_end": event_index,
            "session_id": session_id,
            "event_id": event_id,
        },
    }


def _is_mirrored_message_event(previous: SessionEvent, current: SessionEvent) -> bool:
    if previous.role != current.role or previous.role not in {"user", "assistant"}:
        return False
    if _message_body_for_dedupe(previous.content) != _message_body_for_dedupe(current.content):
        return False

    previous_payload = _locator_payload(previous)
    current_payload = _locator_payload(current)
    if previous_payload.get("source_path") != current_payload.get("source_path"):
        return False
    if _line_start(current_payload) != _line_start(previous_payload) + 1:
        return False

    return (
        _is_response_message_record(previous_payload) and _is_event_message_record(current_payload)
    ) or (
        _is_event_message_record(previous_payload) and _is_response_message_record(current_payload)
    )


def _locator_payload(event: SessionEvent) -> dict[str, Any]:
    locator = event.metadata.get("event_locator_json")
    if isinstance(locator, dict):
        payload = locator.get("payload")
        return payload if isinstance(payload, dict) else {}
    return {}


def _line_start(locator_payload: dict[str, Any]) -> int:
    try:
        return int(locator_payload.get("line_start") or 0)
    except (TypeError, ValueError):
        return 0


def _is_response_message_record(locator_payload: dict[str, Any]) -> bool:
    return locator_payload.get("record_type") == "response_item" and locator_payload.get("payload_type") == "message"


def _is_event_message_record(locator_payload: dict[str, Any]) -> bool:
    return locator_payload.get("record_type") == "event_msg" and locator_payload.get("payload_type") in {
        "agent_message",
        "assistant_message",
        "user_message",
        "user",
    }


def _message_body_for_dedupe(content: str) -> str:
    return content.strip()


def _source_metadata(path: Path) -> dict[str, str]:
    stat = path.stat()
    return {
        "scanner_id": SCANNER_ID,
        "scanner_version": SCANNER_VERSION,
        "source_ref": str(path),
        "source_size": str(stat.st_size),
        "source_mtime": str(stat.st_mtime_ns),
        "source_fingerprint": _source_fingerprint(path),
    }


def _session_ref_from_source(provider: str, path: Path, extra_metadata: dict[str, str]) -> SessionRef:
    metadata = {**_source_metadata(path), **_codex_session_metadata(path), **extra_metadata}
    return SessionRef(
        provider=provider,
        session_id=str(metadata.get("codex_session_id") or _discover_session_id(path)),
        source_path=path,
        metadata=metadata,
    )


def _codex_session_metadata(path: Path) -> dict[str, str]:
    session_meta = _read_first_session_meta(path)
    session_id = _session_id_from_record(session_meta) if session_meta is not None else _discover_session_id(path)
    codex_root = _codex_source_root(path)
    index_entry = _session_index_entry(codex_root, session_id)
    cwd = _session_cwd(session_meta) or _session_index_value(index_entry, ("cwd", "working_directory", "workingDirectory"))
    title = _session_index_value(index_entry, ("thread_name", "threadName", "title", "name")) or session_id
    updated_at = (
        _session_index_updated_at_seconds(index_entry)
        or _rollout_file_activity_seconds(path)
        or int(path.stat().st_mtime)
    )
    group_key = cwd or _source_group_key(path)
    return {
        "codex_session_id": session_id,
        "codex_source_root": str(codex_root) if codex_root is not None else "",
        "session_title": title,
        "session_cwd": cwd,
        "session_group_key": group_key,
        "session_group_label": _group_label(group_key),
        "session_updated_at": str(updated_at),
    }


def _read_first_session_meta(path: Path) -> dict[str, Any] | None:
    inspected = 0
    for _, record in _iter_jsonl_records(path):
        inspected += 1
        if inspected > 100:
            break
        if record.get("type") == "session_meta":
            return record
    return None


def _session_cwd(session_meta: dict[str, Any] | None) -> str:
    if session_meta is None:
        return ""
    payload = session_meta.get("payload")
    candidates = [payload] if isinstance(payload, dict) else []
    candidates.append(session_meta)
    for item in candidates:
        for key in ("cwd", "working_directory", "workingDirectory"):
            if item.get(key):
                return str(item[key])
    return ""


def _codex_source_root(path: Path) -> Path | None:
    current = path.resolve().parent
    while True:
        if current.name in CODEX_SESSION_ROOT_NAMES:
            return current.parent
        if current == current.parent:
            return None
        current = current.parent


def _source_group_key(path: Path) -> str:
    codex_root = _codex_source_root(path)
    if codex_root is None:
        return str(path.parent)
    try:
        relative_parent = path.parent.relative_to(codex_root)
    except ValueError:
        return str(path.parent)
    return str(relative_parent.parent if relative_parent.name in CODEX_SESSION_ROOT_NAMES else relative_parent)


def _group_label(group_key: str) -> str:
    cleaned = group_key.rstrip("/").rstrip("\\")
    if not cleaned:
        return "Unknown"
    return cleaned.replace("\\", "/").split("/")[-1] or cleaned


def _session_index_entry(codex_root: Path | None, session_id: str) -> dict[str, Any]:
    if codex_root is None or not session_id:
        return {}
    return _read_session_index_map(codex_root).get(session_id, {})


@lru_cache(maxsize=16)
def _read_session_index_map(codex_root: Path) -> dict[str, dict[str, Any]]:
    index_path = codex_root / SESSION_INDEX_NAME
    if not index_path.exists():
        return {}
    entries: dict[str, dict[str, Any]] = {}
    with index_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            session_id = _session_index_value(record, ("id", "session_id", "sessionId", "thread_id", "threadId"))
            if session_id:
                entries[session_id] = record
    return entries


def _session_index_value(entry: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = entry.get(key)
        if value:
            return str(value)
    payload = entry.get("payload")
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if value:
                return str(value)
    return ""


def _session_index_updated_at_seconds(entry: dict[str, Any]) -> int:
    for key in ("updated_at", "updatedAt", "last_updated_at", "lastUpdatedAt", "last_activity_at", "lastActivityAt"):
        timestamp = _timestamp_seconds(entry.get(key))
        if timestamp:
            return timestamp
    payload = entry.get("payload")
    if isinstance(payload, dict):
        for key in ("updated_at", "updatedAt", "last_updated_at", "lastUpdatedAt", "last_activity_at", "lastActivityAt"):
            timestamp = _timestamp_seconds(payload.get(key))
            if timestamp:
                return timestamp
    return 0


def _rollout_file_activity_seconds(path: Path) -> int:
    latest = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            latest = max(latest, _record_timestamp_seconds(record))
    return latest


def _record_timestamp_seconds(record: dict[str, Any]) -> int:
    for key in ("timestamp", "created_at", "createdAt", "updated_at", "updatedAt", "time"):
        timestamp = _timestamp_seconds(record.get(key))
        if timestamp:
            return timestamp
    payload = record.get("payload")
    if isinstance(payload, dict):
        for key in ("timestamp", "created_at", "createdAt", "updated_at", "updatedAt", "time"):
            timestamp = _timestamp_seconds(payload.get(key))
            if timestamp:
                return timestamp
    return 0


def _timestamp_seconds(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        number = float(value)
        return int(number / 1000) if number > 10_000_000_000 else int(number)
    if not isinstance(value, str):
        return 0
    text = value.strip()
    if not text:
        return 0
    try:
        number = float(text)
    except ValueError:
        number = 0
    if number:
        return int(number / 1000) if number > 10_000_000_000 else int(number)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return 0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp())


def _sort_session_refs(refs: list[SessionRef]) -> list[SessionRef]:
    latest_by_group: dict[str, int] = {}
    for ref in refs:
        group_key = str(ref.metadata.get("session_group_key") or "")
        latest_by_group[group_key] = max(latest_by_group.get(group_key, 0), _metadata_timestamp(ref))
    return sorted(
        refs,
        key=lambda ref: (
            -latest_by_group.get(str(ref.metadata.get("session_group_key") or ""), 0),
            str(ref.metadata.get("session_group_label") or "").casefold(),
            -_metadata_timestamp(ref),
            str(ref.metadata.get("session_title") or ref.session_id).casefold(),
            ref.session_id,
        ),
    )


def _metadata_timestamp(ref: SessionRef) -> int:
    try:
        return int(str(ref.metadata.get("session_updated_at") or "0"))
    except ValueError:
        return 0


def _source_fingerprint(path: Path) -> str:
    stat = path.stat()
    digest = hashlib.sha256()
    digest.update(str(path).encode("utf-8"))
    digest.update(str(stat.st_size).encode("utf-8"))
    digest.update(str(stat.st_mtime_ns).encode("utf-8"))
    with path.open("rb") as handle:
        digest.update(handle.read(64 * 1024))
        if stat.st_size > 64 * 1024:
            handle.seek(max(stat.st_size - 64 * 1024, 0))
            digest.update(handle.read(64 * 1024))
    return f"sha256:{digest.hexdigest()}"


def _content_hash(content: str) -> str:
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _preview(content: str, *, limit: int = 160) -> str:
    chunk = content[: max(limit * 8, 1024)]
    lowered = chunk.lower()
    if not any(token in lowered for token in ("api", "key", "token", "secret", "password")):
        return chunk[:limit]
    redacted = SECRET_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", chunk)
    return redacted[:limit]


def _read_jsonl_record(source_path: Path, line_number: int) -> dict[str, Any]:
    with source_path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            if index == line_number:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("codex source line is not a JSON object")
                return record
    raise ValueError("codex source line not found")


def _iter_jsonl_records(source_path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    with source_path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                yield index, record


def _malformed_jsonl_line_count(source_path: Path) -> int:
    count = 0
    with source_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError:
                count += 1
    return count


def _loaded_session_id(ref: SessionRef, events: list[SessionEvent]) -> str:
    for event in events:
        locator = event.metadata.get("event_locator_json")
        if isinstance(locator, dict):
            payload = locator.get("payload")
            if isinstance(payload, dict) and payload.get("session_id"):
                return str(payload["session_id"])
    return ref.session_id


def _source_dirs(request: ScanRequest) -> list[Path]:
    if request.source_dir is not None:
        return [request.source_dir]
    return _default_codex_source_dirs()


def _default_codex_source_dirs() -> list[Path]:
    return [
        Path.home() / ".codex" / "sessions",
        Path.home() / ".codex" / "archived_sessions",
    ]


def _discover_source_paths(request: ScanRequest) -> list[tuple[Path, dict[str, str]]]:
    direct_paths: list[tuple[Path, dict[str, str]]] = []
    bridged_paths: list[tuple[Path, dict[str, str]]] = []
    for source_dir in _source_dirs(request):
        if not source_dir.exists():
            continue
        direct_paths.extend((path, {}) for path in sorted(source_dir.rglob("*.jsonl")) if _is_direct_session_source(path))
        bridged_paths.extend(_resolve_source_id_manifests(source_dir))
    return _dedupe_source_paths(direct_paths + bridged_paths)


def _is_direct_session_source(path: Path) -> bool:
    return path.name not in SOURCE_ID_MANIFEST_NAMES and path.name != SESSION_INDEX_NAME


def _is_source_id_manifest(path: Path) -> bool:
    return path.name in SOURCE_ID_MANIFEST_NAMES


def _resolve_source_id_manifests(source_dir: Path) -> list[tuple[Path, dict[str, str]]]:
    resolved: list[tuple[Path, dict[str, str]]] = []
    for manifest_path in sorted(path for path in source_dir.rglob("*.jsonl") if _is_source_id_manifest(path)):
        for source_id in _read_source_ids(manifest_path):
            source_path = _resolve_codex_source_id(source_id)
            if source_path is None:
                continue
            resolved.append(
                (
                    source_path,
                    {
                        "bridge_source_id": source_id,
                        "bridge_manifest": str(manifest_path),
                    },
                )
            )
    return resolved


def _read_source_ids(manifest_path: Path) -> list[str]:
    source_ids: list[str] = []
    for line_number, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid codex source id manifest at {manifest_path}:{line_number}") from exc
        source_id = record if isinstance(record, str) else record.get("source_id") if isinstance(record, dict) else ""
        if source_id:
            source_ids.append(str(source_id))
    return source_ids


def _resolve_codex_source_id(source_id: str) -> Path | None:
    source_id = source_id.strip()
    if not source_id:
        return None

    all_candidates: list[Path] = []
    for source_dir in _default_codex_source_dirs():
        if not source_dir.exists():
            continue
        candidates = sorted(path for path in source_dir.rglob("*.jsonl") if path.name not in SOURCE_ID_MANIFEST_NAMES)
        for path in candidates:
            if path.stem == source_id:
                return path
        all_candidates.extend(candidates)

    for path in all_candidates:
        if _discover_session_id(path) == source_id:
            return path
    return None


def _dedupe_source_paths(items: list[tuple[Path, dict[str, str]]]) -> list[tuple[Path, dict[str, str]]]:
    seen: set[str] = set()
    deduped: list[tuple[Path, dict[str, str]]] = []
    for path, metadata in items:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((path, metadata))
    return deduped
