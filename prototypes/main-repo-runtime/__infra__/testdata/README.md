# Testdata

这里放 EvoZeus runtime 测试集。数据必须是脱敏、最小、可复现的样例，不能包含真实 raw private session。

## Codex Sessions

`codex_sessions/` 用于验证 Codex scanner 可以发现多个 session，并且每个 session 可以还原出足够的事件信息。

测试集覆盖两类 Codex 输入形状：

- flat JSONL：直接出现 `role/content/tool_result`。
- archived wrapper JSONL：外层是 `type/payload`，包含 `session_meta`、`event_msg`、`response_item.message`、`function_call` 和 `function_call_output`。
