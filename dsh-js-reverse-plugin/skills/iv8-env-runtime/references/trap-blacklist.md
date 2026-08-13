# 陷阱黑名单 · API 三态 —— 补不补一个 API

> 服务于 **P3 补漏**。核心问题：debug 监控吐出一堆"疑似缺失 API"，哪些该补、哪些绝不能碰。

---

## 0. ★ 首要判据（通则，先记这一条）

> **未知的缺失 API，一律保持 `undefined`；除非去真机（js-reverse MCP）核对，确认真 Chrome 里确有值，才补。**

下面的"黑名单"只是**举例**，不是穷举清单——新站会冒出你没见过的探测名。
不要背清单，背**通则**：默认不补，补之前必须有"真机确有此值"的证据。理由同 patching-principles 原则 1.4 暗坑二（两种 undefined 长得一样、意义相反，唯一区分手段 = 真机核对）。

黑名单举例（真 Chrome 也没有，补了 = 自曝是自动化环境）：
`process` · `_phantom` · `__webdriver_script_fn` · `__nightmare` · `StyleMedia` · `Float16Array`（旧 Chrome 无）· `domAutomation` · `callPhantom` · 各种 `__driver_*` / `__selenium_*` / `__fxdriver_*`。

它们分三类来源：反爬黑名单探针（webdriver 家族）/ IE 或非 Chrome 旧接口（StyleMedia）/ 新版特性存在性探测（Float16Array）。**共同点：真 Chrome 读到 undefined，你也就该 undefined。**

---

## 1. API 三态表（决定"补不补 API"）

iv8 上的 API 不是"有/无"二元，是**三态**：

| 状态 | 例子 | 表现 | 怎么办 |
|---|---|---|---|
| **真实现** | navigator / document / crypto / XHR / canvas 2D 上下文对象 | 能用，行为对齐 Chrome | **不动** |
| **stub 空壳** | `MessageChannel`（`new().port1 === null`） | `typeof=function`、`toString=[native code]` 骗过存在性检测，但一**用**就崩 | **替换/补全**（见 §3） |
| **陷阱 / 正确缺失** | `process` / `_phantom` / `StyleMedia` / `Float16Array` | `undefined` | **绝不能补**（补了自曝） |

关键：**stub 空壳 ≠ 陷阱**。前者要补，后者绝不能补。区分靠下面两类缺口的两种找法。

---

## 2. 两类缺口、两种找法

| 缺口 | 该怎样 | 症状 | 找法 |
|---|---|---|---|
| **陷阱 / 正确缺失** | 保持 `undefined` | 目标读它只为"存在即判死"，读到 undefined 正是你要的 | 看 **debug 的"疑似缺失 API"日志**（typeof/in 探测会记进反射链）——绝大多数在这里的是陷阱，**别补** |
| **stub 空壳窟窿** | 替换真实现 | 运行时 `TypeError`（如 `Cannot set properties of null`、`x is not a function`） | **抓不到**在缺失日志里（typeof 正常、`[native code]` 齐全），只能靠**运行时报错栈**定位（`scripts/reproduce_stub_error.py` 复现最小栈） |

> 一句话：**缺失日志里的 = 大概率陷阱（别补）；报错栈里的 = stub 窟窿（要补）。** 陷阱不抛错、stub 抛错，这是最快的分流信号。

---

## 3. stub 空壳补法

典型 `MessageChannel`：iv8 给了空壳，`port1/port2 = null`，core-js 会用它降级 microtask 调度链，一用就崩。补法要点：配 `wrapNative` 伪装 + `eventLoop.advance`/`drain` 推进任务。具体见 `references/version-gotchas.md`（E2 条目，版本门控）。

任何新 stub 都按 `references/patching-principles.md` 的 iv8 原生补丁契约处理：报错坐实、真机核形、目标外注入、`wrapNative`、一次一处、补后对账。禁止引入整套通用 mock，也禁止为了“更像浏览器”批量补 API。

---

## 4. 自查口诀

1. 报错栈点名某 API → **stub 窟窿，补**（先 reproduce 最小栈）。
2. 只在"疑似缺失"日志里、没抛错 → **默认别补**，登记待真机核对。
3. 真机 js-reverse MCP 读它 = undefined → **合法保持**（顺带确认 typeof/in 一致）。
4. 真机读它有真实值、iv8 缺 → 这才是"真机有 iv8 缺"的少数派，照真机补上。
5. 任何"让它更像浏览器"的顺手补全 → **停**，违反最小原则（见 `references/patching-principles.md`）。
