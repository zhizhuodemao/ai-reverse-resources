# P2 · 起手跑 + 发现缺口 —— 要配/补什么

> 阶段定位：入口已定位（P1 完成），现在最小 environment 零配跑一遍，
> 让目标 JS 自己告诉你"它读了什么、缺了什么"。
> 退出 P2 = 你手上有一张"要配的清单 + 要补的 stub 清单"，进 P3 落地。
> P1↔P2↔P3 可来回迭代，不是单向。

---

## 1. 四个发现手段（主力是 ①×②）

| 手段 | 发现什么 | 工具 |
|---|---|---|
| **① debug 监控** | 它**读/调了哪些**字段（= 要配的清单）；摸了哪些缺失 API | `mode='debug'` + `scripts/monitor_env.py` |
| **② get_defaults 体检** | 它读的字段里，iv8 默认是否占位（about:blank/空）→ 占位就配 | `scripts/defaults_audit.py`（见 `references/config-defaults-cheatsheet.md`） |
| **③ 报错栈** | 缺的 API / stub 空壳窟窿 | 跑崩看 `TypeError` 栈，`scripts/reproduce_stub_error.py` 复现最小栈 |
| **④ 对账** | token 算出但服务器不认 → 哪个指纹值没对上 | `scripts/parity_check.py`，逐字段/逐字符对比真机 |

> **主力 = ①×②交集**：监控列出"它访问了什么"，体检看"默认值对不对"，**交集 = 你要配的**。
> 例：monitor 输出里出现 `canvas.toDataURL`/`fillText`/`webgl.getParameter` → 立刻知道在用 canvas+webgl 指纹 → 这些值要配真机的。
> ③ 只在跑崩时用（stub 窟窿）；④ 是 P4 验收工具，但"算出被拒"时回头也靠它定位。

---

## 2. debug 监控读什么（monitor_env.py 输出）

`mode='debug'` 把每次访问实时打出，五类 + 缺失：
`getter`(读) / `setter`(写) / `call`(调用) / `query`(typeof/in) / `反射层`(Object.keys/getOwnPropertyDescriptor/Reflect.*) / `疑似缺失API`。

读报告重点：
- **① getter / ③ call** → 它在乎哪些字段/指纹（= 要配的清单）。
- **⑥ 疑似缺失 API** → 区分"陷阱（别补）"和极少数"真机有但 iv8 缺（对齐才补）"，判据见 `references/trap-blacklist.md`。

---

## 3. DOM 内容何时填 · 用 innerHTML 还是 page.load

先分清：DOM 的 **API**（createElement/querySelector…）iv8 自洽不用补；DOM 的**内容**（页面元素/`<meta>`/`title`）默认空骨架。读页面 DOM 的反爬 JS 在空 DOM 上读到 null/空 → 签名错。

| 方式 | 行为 | 何时用 |
|---|---|---|
| `document.documentElement.innerHTML = html` | **只建 DOM 树**，不执行脚本、不派发事件、不同步 URL（轻量） | 目标只读 DOM 结构（读 `<meta>` token、读某节点、读 title） |
| `__iv8__.page.load({baseURL, html, resources, headers})` | 流式解析 + **执行 `<script>`** + 派发 DOMContentLoaded/load + 同步 URL | 目标依赖页面内 `<script>` 执行 / 生命周期事件 |

怎么发现要不要填：debug 监控里出现 `document.querySelector`/`getElementById`/`document.title`/`<meta>` 访问，或签名跑出来不对 → 试填真实 HTML。**看站而定**：读页面 DOM 的站必填，只算指纹的站不填。

---

## 4. 起手 SOP：最小 environment → 零配跑 → 按结果分支

起手 environment（覆盖大多数案例，模板见 `assets/env_starter.py`）：
```python
environment = {
    "location": { ... 真实页面 URL 的各字段 ... },   # 必配（默认 about:blank 一定错）
    "navigator": {"userAgent": "..."},                # 常配（只指定 UA，入签名）
}
```

零配跑之后按结果分支：

| 跑出来 | 诊断 | 动作 |
|---|---|---|
| 崩 `TypeError` | 缺 API / **stub 空壳窟窿** | 看栈（reproduce_stub_error）→ 替换那一个（MessageChannel 式，见 trap-blacklist §3） |
| 跑通、签名/token **算出但服务器不认** | 指纹值没配对/不一致 | monitor 看读了啥 → 体检对照 → 配 `canvas`/`webgl`/`screen`/DOM 内容，并过 `consistency_lint`；回 P3 迭代 |
| 跑通、**翻 0 / 200 / code=0** | 够用 | 收工（P4 已过），别画蛇添足 |
| 本地算对但请求被拒（403 等） | **多半非环境**（cookie/IP/参数过期）；或真机指纹偏差 | 先排除非环境因素，别在 env 上死磕 |

> ⚠️ "算出被拒"和"403"是两回事：前者回 P3 配指纹对齐，后者往往根本不是环境问题。判决权在 P4——**服务器 200/code=0 是唯一真相，本地自洽不算**。

---

## 5. CHECKPOINT（退出 P2 前自查）

- [ ] 最小 environment 已零配跑过一遍，看过 debug 监控输出。
- [ ] ①×② 交集已列出"要配的字段清单"。
- [ ] 报错栈里的 stub 窟窿已单独登记（区别于陷阱）。
- [ ] "疑似缺失 API"已按 trap-blacklist 判据分流（陷阱别补 / 真机有才补）。
- [ ] DOM 内容是否要填已判定（monitor 有无页面 DOM 访问）。

清单齐 → 进 P3 配环境 + 补漏 + 跑通（见 `references/patching-principles.md`）。
