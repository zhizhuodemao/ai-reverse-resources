# Part1 · 方法步骤 → js-reverse MCP 工具映射

> 配合 `references/part1-entry-location.md` 用：那篇讲「怎么想」，本篇讲「点哪个工具」。
> 只用 js-reverse MCP 提供的工具名，别臆造。所有 `scriptId` 随 reload/navigate/切帧过期，
> 优先用**脚本 URL** 定位。

---

## 1. 步骤 → 工具映射表

| 七步流程 / 动作 | 首选工具 | 备选 / 配合 |
|---|---|---|
| 明确目标字段·抓包看请求 | `list_network_requests` | `get_request_initiator`(拿到 reqid 后查发起 JS) |
| 找真实出口·定位发起 JS | `get_request_initiator` | `list_scripts`、`list_network_requests` |
| 出口处下断点(网络) | `break_on_xhr`(URL 子串) | `set_breakpoint_on_text`(按源码文本断) |
| 招①搜参数名/内部命名 | `search_in_sources` | `list_scripts`(不知道搜什么时) |
| 招②堵网络出口·验 native | `evaluate_script`(mainWorld=true) | 求值 `XMLHttpRequest.prototype.open.toString()` |
| 招③搜 hook 明文胎记 | `search_in_sources` | 命中后 `get_script_source` 读上下文 |
| 命中断点·看调用栈定角色 | `get_paused_info` | `select_frame`(切到疑似生成帧) |
| 帧内主动 evaluate 取边界证据 | `evaluate_script`(带 frame) | 见 §3 箭头函数取 arguments |
| 读某段源码 | `get_script_source` | `search_in_sources`(先定位行) |
| 单步跟进生成点 | `step` | `pause_or_resume` |
| 解除断点(防重入死锁) | `remove_breakpoint` | `list_breakpoints`(先查有哪些) |
| 切 iframe/帧做帧内工作 | `select_frame` | `select_page`(多页时先选页) |
| 触发采集/事件后看流量 | `list_network_requests` | `get_websocket_messages`(WS 流) |

> 网络与 cookie 证据是 page 级；源码/调试/帧内 evaluate 是 frame 级 → 做帧内工作前先
> `select_frame`。抓 cookie 诞生点用 `list_network_requests` 带 cookieName。

---

## 2. 入口类型 → 定位打法

| 入口类型 | 定位主线（工具序列） |
|---|---|
| 函数式 | `search_in_sources`(字段名/算法名) → `set_breakpoint_on_text` 在生成点 → `get_paused_info` 看栈 → 帧内 `evaluate_script` 证纯函数 |
| 拦截式 | 搜不到字段名(常态) → `evaluate_script` 验 `open/send/fetch` 是否 `[native code]` → `search_in_sources` 搜 hook 内部命名 → `break_on_xhr` 看栈一步到 SDK |
| 事件式 | `click_element`/`evaluate_script` 触发事件 → `break_on_xhr` 或 setter 断点 → `get_paused_info` 看栈 |
| 状态机式 | `break_on_xhr` 命中后 `remove_breakpoint` → 帧内 evaluate 观察队列/timer 状态 → 触发+推进后 `list_network_requests` |
| 采集式 | `list_network_requests`(cookieName 查 cookie 诞生) → `get_request_initiator` → 断点看栈 |
| 下发式 | `list_network_requests` 看前序响应 header/body → 比对后续出口值 == 前序响应值 |

---

## 3. 卡点急救

**A. `search_in_sources` 无匹配 = 反爬常态，不是你错**
反爬几乎都把关键参数名动态拼接/编码，源码里没有明文。搜不到恰恰说明「对方在藏」。
立即换招：不再搜字段名，改**查网络出口 hook**——用 `evaluate_script`(mainWorld=true) 求值
`XMLHttpRequest.prototype.open.toString()` / `window.fetch.toString()`，不是 `[native code]`
就是被接管了，签名十有八九在这条 hook 链里注入。再 `search_in_sources` 搜 hook 内部属性名
（如 `secureOpenArgs`、`nativeXMLHttpRequestOpen` 这类 hook 自用、没被混淆的胎记）。

**B. 断点重入死锁 = 命中后立刻 `remove_breakpoint`**
webpack 转发壳 / `u[16]++` 这类点会被反复命中，尤其后续嵌套调用会再次暂停造成死锁。
两个手段：
- 下断点时加 `condition`，只在目标特征成立时停（如 `arguments[0]&&arguments[0].paths&&arguments[0].aid` 只在真 init 时命中）。
- 命中一次拿到帧引用后，马上 `remove_breakpoint`，再在帧内做 evaluate/复现，避免二次进入。

**C. 帧内 eval 读 `arguments` 用箭头函数**
普通 `function(){...}` 有自己的 `arguments`，取不到暂停帧的实参。用箭头函数——它不绑定
自己的 `arguments`，会取到暂停帧的：`evaluate_script(frame, "() => arguments[0]")` 拿到的
就是传给当前帧函数的第一个实参（如传给 init 的 config）。同理 `() => u[16]` 读帧内局部。

**D. 命中无数次 / 不知道断哪**：先 `list_scripts` + `get_request_initiator` 找发起 JS，
再对具体脚本 URL 下 `set_breakpoint_on_text`，比全局断点精准。

**E. `scriptId` 失效**：reload/navigate/切帧后旧 id 作废 → 用脚本 URL 重新 `get_script_source`。

---

## 4. 与后续阶段的衔接

P1 用上述工具把 `assets/entry-report-template.txt` 填满、结论=已定位后：
- 拦截式实例落地 → `references/case-intercept-douyin.md`
- 函数式实例落地 → `references/case-function-iwencai.md`
- 进入 iv8 起手跑 → `references/part2-discovery.md`
