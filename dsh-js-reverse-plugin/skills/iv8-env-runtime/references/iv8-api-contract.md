# iv8 API 契约（权威·只准用这些）

> 本表是 iv8 社区版 0.1.3 实测过的**唯一权威 API 面**。写 P2/P3 代码时**照抄这里**，
> 不要臆造方法名或参数。拿不准某个能力有没有 → 它多半没有，走通用手段（requests + add_resource）。
> 版本相关的坑（btoa/MessageChannel/WASM…）见 `references/version-gotchas.md`（消费 preflight 的版本）。

---

## 1. Python 侧：`iv8.JSContext`

### 1.1 构造参数

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `mode` | str | `'prod'` | `'prod'` 零监控开销 / `'debug'` 开 API 调用链追踪 + 反射拦截 + DevTools |
| `environment` | dict | None | **画像**（JS 可观测的指纹值）。navigator/screen/location/webgl/canvas/document…**可含数组**（languages/brands） |
| `config` | dict | None | **引擎行为**（timezone/permissions.* 等）。**仅标量，不放数组/画像值** |
| `ignore_apis` | list | 内置默认 | 从 debug 监控日志排除的 API（默认已静音 Math/JSON/Array/TypedArray 降噪） |
| `time_mode` | str | `'logical'` | `'logical'` 逻辑时间 `sleep(5000)` 瞬间完成 / `'system'` 锚系统时间（POW、时间差校验用） |
| `js_api` | str | `'__iv8__'` | JS 侧工具对象挂载名 |

> environment vs config 的红线：**画像走 environment（可数组），引擎行为走 config（仅标量）**。塞反了不生效或报错。分类导航见 `references/config-defaults-cheatsheet.md`。

### 1.2 方法

| 方法 | 说明 |
|---|---|
| `eval(source, name="", line=-1, col=-1, to_py=False, devtools=True)` | 执行 JS，返回值自动转 Python。`to_py=True` 递归转嵌套对象/数组 |
| `close(gc="none")` | 释放上下文。`gc` 可选 `"low_memory"`(=`"v8"`/`True`) / `"aggressive"` 触发 GC |
| `add_resource(url, body, status=200, headers=None)` | 注入离线 HTTP 响应到 bundle（XHR/fetch/`<script src>` 从中匹配） |
| `with_devtools(port=9229, watch_apis=None, enable_console=True)` | 启用 CDP 调试，返回 ctx 便于链式 `with` |
| `expose(obj, name?)` / `expose(**kwargs)` | 把 Python 对象暴露到 JS 的 `__iv8__.data`（不污染 window） |
| `get_defaults()` | **类方法**，返回全部支持路径及默认值（实测 393 路径）；配环境导航见 config-defaults-cheatsheet |

推荐上下文管理器：`with iv8.JSContext(...) as ctx:` —— 退出自动释放，别手动漏 close。

---

## 2. JS 侧工具对象 `window.__iv8__`

设计为**不可检测**：`typeof window.__iv8__ === "undefined"`，对目标 JS 完全隐身。

### 2.1 `__iv8__.eventLoop.*`（事件循环 / 时间控制）

| 方法 | 说明 |
|---|---|
| `advance(total, step?)` | 分帧推进虚拟时间（默认步长 ~16.67ms），模拟 rAF 节奏 |
| `sleep(ms?, max?)` | 推进 ms 毫秒，按时间线顺序排空任务队列 |
| `tick(ms?)` | 推进 ms 并执行一轮事件循环 |
| `drain(max?)` | 排空所有已到期任务，**不推进时间** |
| `drainMicrotasks()` | 仅排空微任务（Promise.then/queueMicrotask/MutationObserver 回调） |
| `drainTimers()` | 仅处理已到期定时器回调 |
| `setAutoAdvanceStep(ms)` | 设 `performance.now()` 自动递增量（默认 0.001ms） |
| `setDateAdvanceStep(ms)` | 设 `Date.now()` 自动递增量（默认 1ms） |

### 2.2 其余工具

| 工具 | 说明 |
|---|---|
| `__iv8__.page.load({baseURL, html, resources?, headers?})` | 流式加载 HTML：解析→暂停执行 `<script>`→处理样式表→派发 DOMContentLoaded/load→同步 URL |
| `__iv8__.input.dispatchMouseEvent(init)` | 派发可信鼠标事件（`isTrusted=true`），init 含 type/target/clientX/clientY/button/buttons |
| `__iv8__.input.dispatchPointerEvent(init)` | 派发可信指针事件 |
| `__iv8__.netLog.entries` | JS 侧发起的 XHR/fetch/导航请求日志数组（配 `to_py=True` 读） |
| `__iv8__.wrapNative(fn, name)` | 把 JS 函数伪装为 `[native code]`，降低临时补丁可观测差异 |
| `__iv8__.help()` | 打印所有可用工具 |
| `__iv8__.data.*` | Python `expose()` 暴露对象的落点 |

`page.load` 的 `resources` 简写 `url: '内容串'`，完整格式 `url: {body, status, headers}`。
`page.load` vs `innerHTML` 何时用哪个见 `references/part2-discovery.md`（是否需执行页面 `<script>`）。

---

## 3. ★ 误用 → 正确 对照表（新人最爱踩）

| 误用 | 为什么错 | 正确做法 |
|---|---|---|
| 在 JS 里直接 `fetch()`/在 Python 里指望 iv8 自动发真请求 | 社区版**无真实网络栈**，请求只从离线 bundle 匹配 | **network_bridge 模式**：Python `requests` 发真请求 → `ctx.add_resource(url,body,...)` 注入 → `eventLoop.drain()` 推进（见 `references/network-and-eventloop.md` / `scripts/network_bridge.py`） |
| `ctx.eval("debugger;")` 想断点 | iv8 禁用原生 `debugger;`（防目标无限 debugger 反调试），不触发 | 用 `ctx.eval("vdebugger;")` |
| `config={"navigator": {...}}` / `config` 里塞数组 | config 只吃标量引擎行为，画像/数组不认 | 画像走 `environment`；数组（languages/brands）也放 environment |
| 发完 XHR 立刻读结果 | 回调还在任务队列里没跑，读到 undefined | **先 `advance`/`drain` 再读**；run_target 内联 drain-before-read 断言兜底 |
| 补 `process`/`_phantom`/`StyleMedia` 让它"更像浏览器" | 这些真 Chrome 没有，补了 = 自曝陷阱 | **保持 undefined**（见 `references/trap-blacklist.md`） |
| 改目标 JS 源码插 `console.log` 看中间值 | 触发自校验（toString/校验和/文件 hash）走惩罚分支 | 原始 JS 零修改，**hook 靠外部**（包 prototype 方法 / defineProperty / expose 截获） |
| 用标准 `console.log` 上报被检测 | 反爬 JS 靠 console 行为差异识别调试环境 | `with_devtools(enable_console=False)` + JS 侧 `vconsole.log()`（仅 DevTools 可见） |
| 手动 `ctx = JSContext(); ... ` 忘 close | 泄漏 Isolate | 用 `with iv8.JSContext(...) as ctx:` 上下文管理器 |

---

## 4. debug 能力（定位环境探测用）

`mode='debug'` + `with_devtools(port=..., watch_apis=[...], enable_console=False)`：

- **API 调用链追踪**：记录受监控浏览器 API 的属性读/写、方法调用、构造调用（Math/JSON/Array/TypedArray 默认静音，可 `ignore_apis` 调）。
- **反射拦截**：拦 `Object.keys` / `getOwnPropertyDescriptor` / `defineProperty` / `Reflect.ownKeys/get/has` / `Function.prototype.toString` / `JSON.parse/stringify`，把目标的**环境探测链路**打出来。
- **API 访问断点**：`watch_apis=["navigator.userAgent","document.cookie","canvas.toDataURL"]` 命中即在 DevTools 暂停。
- **面板**：Elements 看 DOM 树、Application 看 Cookie/Storage、单步 + 变量查看/修改。

debug 监控是 P2 发现"要配什么"的主力手段，配合脚本 `scripts/monitor_env.py`；用法见 `references/part2-discovery.md`。
