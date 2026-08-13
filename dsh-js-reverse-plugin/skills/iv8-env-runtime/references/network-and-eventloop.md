# 网络桥接与事件循环（network-and-eventloop）

> **一句话**：iv8 社区版**不内置真实网络传输栈**，也**不自动推进时间**。真请求要你自己发、
> 结果要你自己 drain。这两件事缺一不可，是 P3"跑通"阶段最常见的两个断点。
> 固化实现见 scripts/network_bridge.py 与 scripts/run_target.py（内联 drain-before-read 断言）。

---

## 一、网络：社区版无真实网络栈

README 白纸黑字：社区版不直接发 HTTP/HTTPS，也不带 Chromium net 栈。XHR / fetch / 外联 `<script src>` /
`<link href>` / CSS `@import` **默认从离线 bundle 匹配响应**。TLS 指纹、cookie 池、代理全归你的 Python HTTP 客户端。
`netLog.entries` 只**记录** JS 侧发起的请求，不真发。

这不是缺陷，是分工：与 curl_cffi 工作流同构——**iv8 只算签名/token，真包由 Python（requests/curl_cffi）发**。

---

## 二、桥接四步握手（缺一不可）

真实请求必须走这条闭环。任何一步漏做，JS 侧回调拿不到响应、Promise 永挂：

```
① JS 发起 XHR/fetch  →  ② 事件循环暂停（回调挂起，等资源）
                                    ↓
④ eventLoop.drain() 推进 ← ③ Python 侧真发请求 + ctx.add_resource() 注入响应到离线 bundle
（XHR 回调命中刚注入的资源，responseText 就位）
```

**骨架（异步 XHR，先发起→再注入→再 drain）**：
```python
import requests, iv8
with iv8.JSContext() as ctx:
    ctx.eval("window.__iv8__.page.load({baseURL:'https://example.com', html:'<html><body></body></html>'})")
    # ① JS 发起异步请求
    ctx.eval("""var x=new XMLHttpRequest(); x.open('GET','https://api.example.com/data');
                x.onload=function(){window._r=x.responseText;}; x.send();""")
    # ③ Python 真发 + 注入（这一步决定 TLS/cookie/代理）
    resp = requests.get("https://api.example.com/data")
    ctx.add_resource(url="https://api.example.com/data", body=resp.text,
                     status=resp.status_code, headers=dict(resp.headers))
    # ④ 推进事件循环，回调才会执行
    ctx.eval("window.__iv8__.eventLoop.drain()")
    print(ctx.eval("window._r"))   # 读结果前必已 drain
```

**注入语义**：`add_resource(url, body, status=200, headers=None)` 与 `page.load` 的 `resources` 参数写入**同一个**离线 bundle。
HTML 解析期的外联资源、运行期的 XHR/fetch 都从中按 URL 匹配。`resources` 简写=直接给内容串；完整格式=`{body, status, headers}`。

**拦截式 SDK 的变体（不真发、只在 URL 上加签）**：某些 SDK（如字节 bdms）`init()` 装的是 XHR 拦截器，
在请求 URL 上加 `a_bogus=...` 等签名却不真发包。此时**不 drain 等响应**，而是从 `netLog.entries` 把"被签名后的最终 URL"捞回 Python，再用 requests 发。判来源与入口类型见 references/part1-entry-location.md。

---

## 三、expose 桥接的 GIL 阻塞警告

另一种桥法：`ctx.expose(py_get, "pyGet")` 把 Python 函数挂到 JS 的 `__iv8__.data` 命名空间（不污染 window），
JS 里 `__iv8__.data.pyGet(url)` 直接调。

**GIL 硬约束**：JS 调用 expose 出去的 Python 函数时会**自动获取 GIL**——
```
Python eval() → 释放 GIL → V8 执行 → (JS 调 Python → 获取 GIL → 执行 → 释放) → V8 返回 → 获取 GIL
```
期间 V8 单线程暂停、其他 Python 线程全阻塞。所以：

- **expose 的函数要尽量轻量**，别在里面塞重活/长阻塞 IO——否则多线程并行优势被这一下抹平。
- 通过 expose 桥接的 HTTP 请求是**完全同步阻塞**的。高并发场景优先用 `add_resource()`/`netLog` 路线（四步握手），或把并发放在 Python 层。
- expose 三态：`expose(obj, "name")` 命名 / `expose(fn)` 用 `fn.__name__` 自动命名 / `expose(get=..., post=...)` 批量。数据（dict/list）也能 expose。

---

## 四、事件循环：读结果前必 drain

iv8 不自动推进时间。JS 里 `setTimeout`/Promise/XHR 回调**排进队列后不会自己跑**，你得手动排空。
**"算出 token 却读到 null/undefined"十有八九是漏 drain。**

| 方法 | 语义 | 何时用 |
|---|---|---|
| `advance(total, step?)` | 分帧推进虚拟时间（默认步 ~16.67ms，模拟 rAF 节奏） | 有 rAF/setInterval/分帧动画的采集链 |
| `sleep(ms?, max?)` | 推进虚拟时间 ms 毫秒，按时间线顺序排空 | 目标里有明确 setTimeout 延时 |
| `tick(ms?)` | 推进 ms 并执行一轮事件循环 | 逐步调试、看一轮跑出什么 |
| `drain(max?)` | 排空所有**已到期**任务，**不推进时间** | 最常用：注入响应后收尾、同步触发后收割 |
| `drainMicrotasks()` | 仅排空微任务（Promise.then/queueMicrotask/MutationObserver） | async/await 卡在 await 微任务边界 |
| `drainTimers()` | 仅处理已到期定时器回调 | 只想触发定时器不碰其他 |

执行顺序对齐 HTML spec：**微任务先于宏任务**。例：`sync → promise → microtask → timeout-0`。

**async 采集常见组合**：`drainMicrotasks()` 先把 await 链推到第一个真延时 → `advance(150)` 越过 setTimeout → 再读结果。
core-js microtask 降级链（MessageChannel 坑，见 references/version-gotchas.md E2）配 `advance(50)+drain()` 驱动。

**drain-before-read 断言（run_target.py 内联固化）**：任何"读 token/读 window.\_result"之前，必须已调过对应的 drain/advance。
把它写成脚本层硬断言，而不是靠记性——这是"保证模型按预期"的脚本层一环。

---

## 五、time_mode：logical vs system

| 模式 | 行为 | 适用 |
|---|---|---|
| `logical`（默认） | 纯逻辑虚拟时钟，`sleep(5000)` 瞬间完成，`Date.now()` 读虚拟时钟 | 绝大多数自动化、快速执行 |
| `system` | 系统时间锚定，JS 执行期 `Date.now()` 反映真实耗时 | **POW（工作量证明）、时间差/耗时校验**类 |

对齐细节：`setAutoAdvanceStep(ms)` 调 `performance.now()` 自增量（默认 0.001ms）；`setDateAdvanceStep(ms)` 调 `Date.now()` 自增量（默认 1ms）。
**踩坑**：目标若校验"两个时间戳之差 ≈ 真实执行耗时"或算 POW，logical 模式下时间不流逝会露馅——换 `time_mode="system"`。反之纯签名场景用 logical 最快。

---

## 相关文件

- scripts/network_bridge.py — 固化四步握手（真发+注入+drain），别每次手搓。
- scripts/run_target.py — 跑目标、内联 drain-before-read 断言、收割 token。
- references/part1-entry-location.md — 判"本地生成/搬运/下发"与拦截式识别。
- references/version-gotchas.md — MessageChannel（E2）等 async 推进不动的引擎坑。
