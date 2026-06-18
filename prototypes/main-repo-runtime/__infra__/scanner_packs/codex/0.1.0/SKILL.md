# Codex Scanner

## When To Use

当 Agent 需要扫描本地 Codex session、查看某条 factor evidence 对应的原始对话、或排查 Codex JSONL 解析问题时，使用这个 scanner pack。

## Sources

默认来源：

```text
~/.codex/sessions
~/.codex/archived_sessions
```

支持格式：

```text
codex_jsonl
```

## SQLite Locator Fields

SQLite 的 `session_events` 只保存轻量字段：

```text
scanner_id
scanner_version
source_ref
source_fingerprint
event_locator_json
artifact_locator_json
content_hash
content_preview_redacted
tool_result_hash
tool_result_preview_redacted
```

`event_locator_json.payload` 对 Codex scanner 至少包含：

```text
source_path
line_start
line_end
record_type
payload_type
session_id
event_id
```

## Resolve Original Event

1. 从 SQLite 找到目标 `session_id` / `event_id` 的 `event_locator_json`。
2. 使用 `scanner_id=codex`、`scanner_version=0.1.0` 找到本 scanner pack。
3. 调用 `scripts/resolve_event_source.py` 或 `resolver.py`。
4. 校验输出里的 `hash_verified`。
5. 如果 `hash_verified=false`，按 `hash_mismatch` 处理。

## Commands

从 repo 根目录运行：

```bash
PYTHONPATH=__infra__/src python __infra__/scanner_packs/codex/0.1.0/scripts/resolve_event_source.py \
  --workspace . \
  --session-id session-alpha \
  --event-id u1
```

也可以直接传 locator JSON：

```bash
PYTHONPATH=__infra__/src python __infra__/scanner_packs/codex/0.1.0/scripts/resolve_event_source.py \
  --locator-json '{"schema_version":"locator.v0","scanner_id":"codex","scanner_version":"0.1.0","locator_schema":"locator.codex_jsonl.v0","kind":"source_event","payload":{"source_path":"/path/session.jsonl","line_start":1}}'
```

## Failure Modes

| Error | Meaning |
| --- | --- |
| `source_missing` | 原始 JSONL 文件不存在或已移动 |
| `unsupported_locator` | locator schema 或 scanner version 不匹配 |
| `hash_mismatch` | 原文读取成功，但 hash 和 SQLite 记录不一致 |
| `permission_denied` | 当前进程无权读取 source path |

## Privacy

SQLite 不保存完整原文。默认 UI 只展示 `content_preview_redacted`。需要查看原文时，Agent 必须通过本 scanner pack 的 resolver 显式读取本地文件，并只在本地 debug 场景使用。
