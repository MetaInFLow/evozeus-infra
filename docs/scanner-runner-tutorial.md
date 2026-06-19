# Scanner / Runner 入门教程

这份文档给第一次看 EvoZeus runtime 的人读。它不要求你先懂 Python、SQLite 或设计模式。

你只需要先记住一句话：

```text
scanner 负责找到聊天记录和每条消息的编号；
runner 负责拿某条聊天记录去跑一个检查规则；
ledger 负责把找到的编号和检查结果存在本地。
```

## 先用一个现实例子理解

假设你的电脑里有一个项目：

```text
/Users/anthonyf/Documents/EvoZeus-community
```

这个项目下面发生过两次 Codex chat：

```text
Chat 1: 优化 Agent 唯一注册机制
Chat 2: 打开 EvoZeus 官网仓库
```

每个 chat 里面有很多条 message。比如：

```text
Chat 1 有 680 条 message
Chat 2 有 2865 条 message
```

EvoZeus runtime 要做的第一件事不是分析内容，而是先整理出一个本地索引：

```text
这个项目有哪些 chat？
每个 chat 的 id 是什么？
每个 chat 里面有哪些 message id？
每条 message 在原始文件的哪一行？
```

这一步就是 scanner。

## scanner 是什么

scanner 可以理解成“整理聊天记录的人”。

它会去本地找 Codex 的聊天记录，然后登记：

```text
项目名
聊天记录 id
消息 id
消息顺序
消息角色
原始文件位置
```

它不会在 scan 阶段把聊天正文抄进数据库。

举例：

```text
project_label:
  EvoZeus-community

session_id:
  019ecc42-5ef3-7e82-8f05-ec83b90b9c3a

message/event:
  event_id=2026-06-15T17:10:38.553Z#L4
  role=user
  line_start=4
```

这表示：

```text
在 EvoZeus-community 这个项目里，
有一条聊天记录叫 019ecc42-...，
里面有一条消息，
这条消息在原始 Codex 记录文件的第 4 行。
```

scanner 只记“在哪里”和“叫什么”，不把 message 原文复制出来。

## runner 是什么

runner 可以理解成“拿一条聊天记录去做检查的人”。

scanner 先告诉系统：

```text
有这个 session_id
```

runner 再根据这个 `session_id` 找到原始聊天记录，加载完整内容，然后运行一个 Factor。

举例：

```text
run_runner.py --session-id 019ecc42-... --factor default.tool_failure
```

意思是：

```text
请拿 019ecc42-... 这条聊天记录，
检查里面有没有 tool failure 相关问题。
```

## Factor 是什么

Factor 可以理解成“一个检查规则”。

不同 Factor 检查不同问题：

```text
default.tool_failure
  检查工具调用失败相关信号

default.open_loop
  检查有没有没有收尾的问题

default.repeated_user_requests
  检查用户是否反复要求同一件事
```

Factor 不负责找聊天记录。它只负责在 runner 给它的那条聊天记录里做判断。

## ledger 是什么

ledger 可以理解成“本地登记本”。

它是一个本地 SQLite 文件，通常在：

```text
<workspace>/.evozeus/runtime/index/results.sqlite3
```

scanner 会往 ledger 里写：

```text
有哪些项目
每个项目有哪些 chat
每个 chat 有哪些 message id
每条 message 在哪里
```

runner 会往 ledger 里写：

```text
这次跑了哪个 Factor
跑的是哪个 session
结果是什么
证据引用了哪些 message id
```

## project 是什么

project 是 chat 所属的项目。

比如：

```text
project_key=/Users/anthonyf/Documents/EvoZeus-community
project_label=EvoZeus-community
```

你可以把它理解成：

```text
project_key 是完整地址
project_label 是显示给人看的名字
```

为什么要存 project？

因为以后你会想这样看：

```text
列出 EvoZeus-community 下面所有 chat
列出某个 project 下还没跑过 Factor 的 chat
按 project 看哪些 session 已经分析过
```

所以 project 不能只藏在一段 metadata 里，它必须是 ledger 里的正式字段。

## session 是什么

session 就是一条完整 chat record。

例如：

```text
session_id=019ecc42-5ef3-7e82-8f05-ec83b90b9c3a
title=优化 Agent 唯一注册机制
event_count=680
```

你可以把它理解成：

```text
这是 EvoZeus-community 项目里的一次完整对话，
这次对话有 680 条 message/event。
```

runner 运行时必须指定一个 `session_id`，因为它一次只分析一条 chat record。

## message / event 是什么

message 是聊天记录里的一条内容。

event 是更宽泛的说法。除了用户消息和助手消息，工具调用、任务开始、任务完成也可以算 event。

当前 ledger 里统一用字段名：

```text
event_id
```

你可以把它理解成 message id。

例子：

```text
event_id=event_0003
event_index=2
role=tool
tool_name=exec_command
```

意思是：

```text
这是这个 session 里的第 2 条记录，
它是一个 tool 事件，
工具名是 exec_command。
```

## source locator 是什么

source locator 可以理解成“书签”。

scanner 不复制 message 原文，但它会保存一个书签，告诉系统以后去哪里找原文。

例子：

```text
source_path=/Users/anthonyf/.codex/sessions/2026/06/16/rollout-...jsonl
line_start=4
line_end=4
```

意思是：

```text
如果以后需要看这条 message 的原文，
去这个 JSONL 文件的第 4 行找。
```

这就是为什么 scanner 可以不保存正文，但后面 runner 仍然能找到正文。

## source fingerprint 是什么

source fingerprint 可以理解成“文件指纹”。

如果原始聊天记录文件改了，fingerprint 通常也会变。

它的作用是判断：

```text
这个 Factor 结果是不是基于旧版本聊天记录跑出来的？
原始 session 变了以后，之前的结果要不要标记为 stale？
```

## analysis run 是什么

analysis run 是一次 runner 执行。

例子：

```text
analysis_run_id=arun_5191021c20604f80b511315f3a0f3197
```

意思是：

```text
系统在某个时间点，
对某个 session，
跑了一次或多次 Factor。
```

它记录这次运行：

```text
跑了哪些 Factor
成功几个结果
有没有错误
什么时候跑的
```

## factor result 是什么

factor result 是 Factor 跑出来的结果。

它会记录：

```text
哪个 Factor
判断结果
分数或信号
证据引用了哪些 message id
```

举例：

```text
factor_id=default.tool_failure
evidence_ref=event_0003
```

意思是：

```text
default.tool_failure 这个检查规则认为 event_0003 和结果有关。
```

注意：Factor result 引用的是 message id，不需要复制 message 原文。

## abstract class 是什么

abstract class 可以理解成“所有 scanner 必须遵守的工作清单”。

不同应用的聊天记录格式不同：

```text
Codex 有 Codex 的文件格式
以后 Claude Code 可能有 Claude Code 的格式
Cursor 可能有 Cursor 的格式
```

但是 EvoZeus 不希望 runner 和 Factor 到处写不同应用的特殊逻辑。

所以定义一个统一要求：

```text
每个 scanner 都必须会：
1. 告诉系统它要读哪些目录
2. 发现有哪些 session
3. 发现每个 session 里有哪些 message id
4. 在 runner 需要时一条一条读出完整 event
5. 把这些 event 组合成完整 session
```

这份统一要求就是 `SessionScanner` abstract class。

普通理解：

```text
abstract class 不是某一个具体 scanner，
它是所有 scanner 的共同工作标准。
```

`CodexScanner` 就是一个具体实现：

```text
SessionScanner 是工作标准
CodexScanner 是按这个标准做 Codex 扫描的人
```

这里有一个重要细节：加载完整 session 不能一次性把整个聊天文件读进内存。正确方式是像翻书一样一行一行读，也就是用 generator 渐进式加载。

## 一次完整流程

第一步，扫描：

```bash
python scripts/run_scanner.py --provider codex --workspace /tmp/evozeus-workspace
```

你可以理解成：

```text
请去本地找 Codex chat，
按 project/session/message 建一个本地索引。
```

输出类似：

```text
scanned_sessions=1253
ledger=/tmp/evozeus-workspace/.evozeus/runtime/index/results.sqlite3
```

## run_scanner.py 每个参数怎么用

`run_scanner.py` 的作用是建立本地索引。

基本格式：

```bash
python scripts/run_scanner.py \
  --provider codex \
  --workspace /tmp/evozeus-workspace
```

每个参数的意思：

| 参数 | 是否必填 | 普通解释 | 例子 |
| --- | --- | --- | --- |
| `--provider` | 否 | 告诉 scanner 要扫哪种聊天记录。现在默认是 `codex`。 | `--provider codex` |
| `--source` | 否 | 指定只扫某个目录。不填时，Codex 会扫默认本地目录。 | `--source tests/fixtures/codex_sessions` |
| `--workspace` | 否 | scanner 把本地 ledger 写到哪个 workspace 下。默认是当前目录。 | `--workspace /tmp/evozeus-workspace` |

不传 `--source`：

```bash
python scripts/run_scanner.py --provider codex --workspace /tmp/evozeus-workspace
```

你可以理解成：

```text
去我电脑默认 Codex 记录目录里找所有 chat。
```

Codex 当前默认目录是：

```text
~/.codex/sessions
~/.codex/archived_sessions
```

传 `--source`：

```bash
python scripts/run_scanner.py \
  --provider codex \
  --source tests/fixtures/codex_sessions \
  --workspace /tmp/evozeus-workspace
```

你可以理解成：

```text
不要扫全量本地 Codex，只扫我指定的这个目录。
```

scanner 输出：

```text
scanned_sessions=1
ledger=/tmp/evozeus-workspace/.evozeus/runtime/index/results.sqlite3
```

输出怎么看：

| 输出 | 意思 |
| --- | --- |
| `scanned_sessions` | 这次发现了多少条 chat record。 |
| `ledger` | 本地 SQLite 登记本的位置。 |

scanner 跑完后，ledger 里应该已经有：

```text
project
session_id
message/event id
message 顺序
role/tool_name
source locator
```

但不应该有 message 原文。

第二步，选择一条 session 跑 Factor：

```bash
python scripts/run_runner.py \
  --session-id 019ecc42-5ef3-7e82-8f05-ec83b90b9c3a \
  --factor default.tool_failure \
  --pack-root tests/fixtures/factor_packs \
  --workspace /tmp/evozeus-workspace
```

你可以理解成：

```text
请拿这条 chat，
跑 default.tool_failure 这个检查规则，
把结果写回本地 ledger。
```

输出类似：

```text
results=1
errors=0
analysis_run_id=arun_...
ledger=/tmp/evozeus-workspace/.evozeus/runtime/index/results.sqlite3
```

## run_runner.py 每个参数怎么用

`run_runner.py` 的作用是对一条已扫描的 chat 跑 Factor。

基本格式：

```bash
python scripts/run_runner.py \
  --session-id session-minimal \
  --factor default.tool_failure \
  --pack-root tests/fixtures/factor_packs \
  --workspace /tmp/evozeus-workspace
```

每个参数的意思：

| 参数 | 是否必填 | 普通解释 | 例子 |
| --- | --- | --- | --- |
| `--session-id` | 是 | 要分析哪一条 chat。这个 id 必须已经被 scanner 扫进 ledger。 | `--session-id session-minimal` |
| `--factor` | 是 | 要跑哪个检查规则。可以传多次，表示一次跑多个 Factor。 | `--factor default.tool_failure` |
| `--pack-root` | 是 | Factor pack 放在哪里。当前测试用 `tests/fixtures/factor_packs`。 | `--pack-root tests/fixtures/factor_packs` |
| `--workspace` | 否 | 去哪个 workspace 的 ledger 里找 session，并把结果写回那里。必须和 scanner 使用同一个 workspace。 | `--workspace /tmp/evozeus-workspace` |

一次跑一个 Factor：

```bash
python scripts/run_runner.py \
  --session-id session-minimal \
  --factor default.tool_failure \
  --pack-root tests/fixtures/factor_packs \
  --workspace /tmp/evozeus-workspace
```

一次跑多个 Factor：

```bash
python scripts/run_runner.py \
  --session-id session-minimal \
  --factor default.tool_failure \
  --factor default.open_loop \
  --pack-root tests/fixtures/factor_packs \
  --workspace /tmp/evozeus-workspace
```

runner 输出：

```text
results=1
errors=0
analysis_run_id=arun_...
ledger=/tmp/evozeus-workspace/.evozeus/runtime/index/results.sqlite3
```

输出怎么看：

| 输出 | 意思 |
| --- | --- |
| `results` | Factor 跑出了多少条结果。 |
| `errors` | 跑 Factor 时有多少个错误。 |
| `analysis_run_id` | 这次 runner 执行的 id。 |
| `ledger` | 结果写回的本地 SQLite 登记本。 |

最容易出错的地方：

```text
run_scanner.py 和 run_runner.py 必须用同一个 --workspace。
```

如果 scanner 写到 `/tmp/a`，runner 却去 `/tmp/b` 找 session，就会找不到 `session_id`。

第三步，看 SQLite 可视化页面：

```bash
python scripts/render_sqlite_html.py --workspace /tmp/evozeus-workspace
```

你可以理解成：

```text
请把这个 workspace 里的 SQLite ledger，
变成一个可以用浏览器打开的 HTML 页面。
```

输出类似：

```text
html=/tmp/evozeus-workspace/.evozeus/runtime/reports/evozeus-sqlite.html
ledger=/tmp/evozeus-workspace/.evozeus/runtime/index/results.sqlite3
providers=1
projects=1
sessions=2
messages=3545
```

## render_sqlite_html.py 每个参数怎么用

`render_sqlite_html.py` 的作用是把本地 SQLite ledger 做成一个静态 HTML 页面，用来看 provider、project、session、chat/message。

基本格式：

```bash
python scripts/render_sqlite_html.py --workspace /tmp/evozeus-workspace
```

每个参数的意思：

| 参数 | 是否必填 | 普通解释 | 例子 |
| --- | --- | --- | --- |
| `--workspace` | 否 | 去哪个 workspace 下面找 `.evozeus/runtime/index/results.sqlite3`。必须和 scanner/runner 用同一个 workspace。 | `--workspace /tmp/evozeus-workspace` |
| `--output` | 否 | HTML 要写到哪里。不传时写到该 workspace 的 `.evozeus/runtime/reports/evozeus-sqlite.html`。 | `--output /tmp/evozeus-sqlite.html` |

默认输出：

```bash
python scripts/render_sqlite_html.py --workspace /tmp/evozeus-workspace
```

指定输出位置：

```bash
python scripts/render_sqlite_html.py \
  --workspace /tmp/evozeus-workspace \
  --output /tmp/evozeus-sqlite.html
```

输出怎么看：

| 输出 | 意思 |
| --- | --- |
| `html` | 生成的静态 HTML 文件位置。用浏览器打开它就能看可视化。 |
| `ledger` | HTML 读取的 SQLite 文件位置。 |
| `providers` | SQLite 里有多少种 session provider。 |
| `projects` | SQLite 里有多少个 project。 |
| `sessions` | SQLite 里有多少条 chat record。 |
| `messages` | SQLite 里有多少条 message/event id。 |

这个脚本不会重新扫描 Codex 原始记录，也不会跑 Factor。它只读取已经存在的 SQLite ledger。

HTML 页面里的 chat/message 有一个重要边界：

```text
如果只跑过 scanner，页面会看到 message id、role、source locator，
但不会看到 message 原文。

如果之后对某个 session 跑过 runner，
ledger 里才会出现这个 session 的 redacted preview 和 factor tag。
```

## 用一句话串起来

```text
Project 下面有很多 Session；
Session 里面有很多 Message/Event；
Scanner 先把这些 id 和位置登记到 Ledger；
Runner 再选择一个 Session，加载完整内容，跑 Factor；
Factor Result 最后通过 session_id + event_id 挂回具体 Message/Event。
```

## 这个设计为什么要这样

这样做是为了同时满足三件事：

1. 能按项目和聊天记录管理大量 session。
2. 能把 Factor 结果准确挂回具体 message。
3. scan 阶段不复制聊天正文，降低隐私和存储风险。

所以 scanner 的目标不是“读懂聊天内容”，而是“建立可靠索引”。

真正读内容、分析内容，是 runner 和 selected Factor 的工作。
