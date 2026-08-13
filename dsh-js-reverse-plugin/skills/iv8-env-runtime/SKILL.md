---
name: iv8-env-runtime
description: >-
  强制使用 iv8（Python 原生的 C++ V8 + 浏览器环境运行时）作为目标 JavaScript 的唯一受控执行底座，
  配置浏览器环境并在本地运行目标反爬 JS，拿到签名 / token，
  并用 js-reverse MCP 从真实出口倒推定位加密 / 签名"生成"入口。分两部分：Part1 找入口（js-reverse MCP），
  Part2 补环境跑通（iv8）。当任务涉及以下时使用：iv8、补环境、脱浏览器跑 JS、js-reverse 找入口、
  本地产签名 / token、JSContext、page.load、add_resource、eventLoop.drain、指纹配置、stub 窟窿、
  navigator/canvas/webgl 一致性。不得使用 Node.js vm 或外部补环境框架替代 iv8；Node.js 只可作为静态工程工具。
  本 skill 不涉及 Akamai 真实鼠标轨迹 / 行为采集式的边界或内容。
---

> **版本基线：iv8 0.1.3 / 2026-07（社区版，已实测）。动手前先跑 `scripts/preflight.py`。**
> 所有 deploy 绑定值（bdms 版本 / aid / script id / u 数组 / golden sum）一律运行时解析，勿写死。

# iv8-env-runtime — 用 iv8 补环境脱浏览器跑反爬 JS

用 iv8 在纯 Python 里跑目标站的反爬 / 签名 JS，本地产出签名 / token，全程无浏览器。
两大部分：**Part1** 用 js-reverse MCP 找到真实"生成"入口；**Part2** 用 iv8 补环境把入口跑通。

---

## §0 能做 / 不能做红线（常驻护栏，8 条铁律）

> 违反任意一条几乎必翻车。每次动手前扫一遍。

1. **断点用 `vdebugger;`，绝不用 `debugger;`**（原生 debugger 已被 iv8 禁用，目标常用无限 debugger 反调试）。
2. **console 检测站：`enable_console=False` + `vconsole.log`**（`vconsole` 对目标 JS 完全不可见）。
3. **`environment` = 画像**（JS 可观测的指纹，可含数组）/ **`config` = 引擎行为**（仅标量，**无数组**：timezone / permissions 等）。两者别混。
4. **默认值三坑**：`location.href` 默认 `about:blank`（**几乎必配**）；`canvas.fingerprint.toDataURL.png` 默认 `''`（**canvas 指纹站必配**）；`navigator` 有 200+ 合理默认（**通常只配 `userAgent`**）。
5. **社区版无真实网络栈**：真请求走 Python `requests` → `ctx.add_resource()` 注入响应 → `eventLoop.drain()` 推进，而不是指望 iv8 自己发包。
6. **API 三态**：真实现（navigator/crypto/XHR）**别动**；stub 空壳（如 `MessageChannel` port=null）**替换**；陷阱 / 正确缺失（`process`/`_phantom`/`__webdriver_script_fn`/`StyleMedia`/`Float16Array`）**绝不补**（补了自曝）。
7. **一致性红线**：UA ↔ userAgentData ↔ platform ↔ 时区 ↔ 语言 ↔ webgl **整套对齐**。说自己是 Mac 就别让 platform 还是 Win32。
8. **`time_mode`**：默认 `logical`（sleep 瞬间完成）；**POW / 时间差校验站用 `system`**（Date.now() 反映真实耗时）。
9. **唯一运行底座**：目标原始 JS 只在 iv8 中执行。真实浏览器用于定位入口、采集环境事实和提供对账样本，不替代 iv8 参考运行；Node.js vm 不进入目标执行链。

---

## §1 前置门（P0，硬门）

**必跑 `scripts/preflight.py`。不过不得继续。**

它做四件事：① 检测平台 / Python 版本 / 架构，装错平台或版本硬阻断并给替代路径；② 打印已安装 iv8 版本（本 skill 版本门控的**唯一真相源**，`references/version-gotchas.md` 消费它）；③ 校验 `import iv8` 与 `get_defaults()` 可用；④ 打印跨平台安装结论。

安装矩阵详见 `references/cross-platform-install.md`。速记：Windows x64 / Linux x64 → `pip install iv8`（PyPI，Py3.9–3.14）；macOS 仅 Apple Silicon 实验版，**不上 PyPI**，去 GitHub Releases 下 `iv8-<ver>-cpXX-cpXX-macosx_14_0_arm64.whl` → `uv pip install ./…whl`（Py3.11–3.14 / macOS14+）；Intel Mac / mac 上 Py<3.11 = 不支持。项目强制用 **uv** 管理。

> **CHECKPOINT P0**：preflight 全绿、版本已打印，才进 Part1 / Part2。**STOP** 若阻断，按它给的替代路径处理，别硬跑。

---

## §2 双轨全景

```
Part1 找入口（js-reverse MCP，真浏览器）          Part2 补环境跑通（iv8，纯 Python）
  真实出口 → 倒推 → 定位"生成"入口 → 分类入口类型  →  最小 environment 起跑 → 发现缺口 → 配/补 → 收割 token → 验收
```

**运行阶段模型（P0–P4，带门）：**

| 阶段 | 做什么 | 退出闸 |
|---|---|---|
| **P0** 环境就绪 | 跑 preflight | 全绿 + 版本打印 |
| **P1** 找入口 | 从真实出口倒推，定位 + 分类入口 | entry-report 填满 & 结论"已定位" |
| **P2** 起跑 + 发现缺口 | 最小 environment 零配跑，列缺口清单 | 缺口清单成形（monitor∩defaults + TypeError 栈） |
| **P3** 配 / 补 / 跑通 | 喂指纹、替 stub、网络桥接、drain、收割 | 本地算出 token |
| **P4** 验收 | parity 对账 + **服务器判决** | 服务器 200 / code=0 |

> **P1 ↔ P2 ↔ P3 可来回迭代**，不是单向瀑布。入口分类错了回 P1；缺口没配全回 P2；服务器拒了回 P3。

---

## §3 Part1 — 找入口（5 步骨架）

方法论：**不是先读懂混淆代码，而是让真实代码自己跑，在出口附近观察参数从无到有的边界。**
完整流程见 `references/part1-entry-location.md`，MCP 工具映射见 `references/part1-mcp-tool-map.md`。

1. **明确目标字段**：字段名、所在请求 / 存储位置、真实样例（`list_network_requests` 找真实出口）。
2. **在真实出口下断点**：XHR/fetch（`break_on_xhr`）、cookie/storage setter、或目标函数返回点（`set_breakpoint_on_text`）。
3. **从断点向上看调用栈，只给每层定角色**：加载 / 初始化 / 触发 / **生成** / 读取 / 搬运 / 发送。别硬读混淆。
4. **定位铁证 =「上一层没有，下一层有」**（`select_frame` + `evaluate_script(mainWorld=true)` 对比改写前输入 / 改写后输出）。**不是**"出现在调用栈里"就算。
5. **判来源 + 最小复现**：本地生成 / 已有状态搬运 / 服务端下发 / 未确认；按入口类型（函数式 / 拦截式 / 事件式 / 状态机式 / 采集式 / 下发式）做最小复现。

**产出**：填满 `assets/entry-report-template.txt`。参考案例：拦截式见 `references/case-intercept-douyin.md`，函数式见 `references/case-function-iwencai.md`。

> **CHECKPOINT P1**：entry-report 每格有动态边界证据、结论写"已定位"。**STOP** 禁止用"可能是 / 和某 SDK 有关 / 调用栈里出现过"当结论——那些一律记"未定位"。

---

## §4 Part2 — 补环境 SOP（P2 → P3 → P4）

核心认知：**补环境 = 造环境（iv8 全包）+ 配环境（你喂指纹值）+ 偶尔补漏（替 stub 窟窿）。** 手写 window/DOM 的体力活没了。

### P2 起跑 + 发现缺口

从 `assets/env_starter.py` 起手：最小 environment（只 `location` + `navigator.userAgent`）零配跑。

- **发现清单 = monitor ∩ defaults 交集**：`scripts/monitor_env.py`（debug 模式）列出"它读 / 调了哪些字段"，`scripts/defaults_audit.py` 查这些字段的 iv8 默认是不是占位（about:blank / 空）→ **交集就是要配的**。
- **stub 窟窿 = TypeError 栈**（typeof 正常、抓不到缺失日志，一用就崩）：`scripts/reproduce_stub_error.py` 复现异常栈定位。
- 判 API 三态见 `references/part2-discovery.md`；配值 / 三态原则见 `references/patching-principles.md`。

> **CHECKPOINT P2**：缺口清单成形（要配的指纹 + 要替的 stub）。**STOP** 别 grep 源码枚举字段一次补一堆——靠监控 + 报错发现，一次一处。

### P3 配环境 + 补漏 + 跑通

1. **喂指纹值**：`location` 全字段填真实 URL、看站配 `canvas`/`webgl`/`window.origin`、读页面 DOM 的站用 `innerHTML` 或 `page.load` 填真实 HTML。配值前先 `scripts/consistency_lint.py` 静态拒错（UA↔platform↔时区 不一致直接拦）。
2. **替换 stub**：MessageChannel/Worker null port 等，配 `wrapNative` + `eventLoop.advance`+`drain`（core-js microtask 降级链，见 `references/version-gotchas.md` E2）。
3. **网络桥接**：`scripts/network_bridge.py` 固化 "JS 发请求 → 暂停 → Python requests → `add_resource` 注入 → drain 推进" 握手。细节见 `references/network-and-eventloop.md`。
4. **drain-before-read**：`scripts/run_target.py` 内联 drain 断言——**收割 token 前必须先 drain**（异步产物没排空就读会拿到 undefined/半成品）。

> **CHECKPOINT P3**：本地稳定算出 token。**STOP** 遇 iv8 专坑先版本门控查 `references/version-gotchas.md`（E1 btoa 在 0.1.3 已修**别照抄**旧版注入 / E2 MessageChannel / E4 WASM instanceof+OOM 炸弹 / E5 audio 金标准 buffer / E6 jsvmp null-safe patch / E7 字体渲染物理量→真机采集后注回 iv8）。

### P4 验收（服务器判决是唯一真相）

- **本地 parity**：`scripts/parity_check.py` 把本地产物与真机样本**逐字符**对账（din 顺序等强校验）。
- **服务器判决**：拿本地产的 token 真发一次，**只认服务器 200 / code=0**。本地自洽不算成功。

> **CHECKPOINT P4**：服务器 200 / code=0 → 收工，别画蛇添足。
> **STOP 分流**：算出但被拒 → 回 P3 查哪个指纹没对上（parity 第一处分叉常指向自检点）；403 等请求层拒 → **多半非环境**（cookie/IP/参数过期），先排除非环境因素别乱补。

---

## §5 references / scripts 索引表

| 文件 | 何时开 / 何时跑 |
|---|---|
| `references/iv8-api-contract.md` | 要用 iv8 任何 API 前——只准用契约里列的，别臆造 |
| `references/cross-platform-install.md` | P0，装 iv8 / 换机器 / 平台不支持时 |
| `references/version-gotchas.md` | P3 遇专坑（E1–E7）；消费 preflight 打印的版本做门控 |
| `references/config-defaults-cheatsheet.md` | P2/P3 查某字段默认是否占位、environment vs config 归属 |
| `references/part1-entry-location.md` | P1 找入口的完整 8 步流程 + 来源判定 + 禁止结论 |
| `references/part1-mcp-tool-map.md` | P1 每步该调哪个 js-reverse MCP 工具 |
| `references/part2-discovery.md` | P2 判 API 三态、四手段发现要配 / 补什么 |
| `references/patching-principles.md` | P3 配值 / 替 stub 的一致性 / 最小 / 一次一处原则 |
| `references/network-and-eventloop.md` | P3 网络桥接 + eventLoop drain/advance 时序 |
| `references/trap-blacklist.md` | P2/P3 判断某缺失 API 是陷阱（别补）还是真漏补 |
| `references/case-intercept-douyin.md` | 参考拦截式入口 + 抖音 bdms 补环境实录 |
| `references/case-function-iwencai.md` | 参考函数式入口 + 爱问财补环境实录 |
| `scripts/preflight.py` | **P0 必跑**，硬门 |
| `scripts/monitor_env.py` | P2 debug 监控，列"它访问了啥"（要配的清单一半） |
| `scripts/defaults_audit.py` | P2 查字段默认占位（要配的清单另一半） |
| `scripts/consistency_lint.py` | P3 配值前静态拒错，一致性红线 |
| `scripts/run_target.py` | P2/P3 起跑目标 JS，内联 drain-before-read 断言 |
| `scripts/network_bridge.py` | P3 固化真请求 → add_resource → drain 握手 |
| `scripts/reproduce_stub_error.py` | P2 复现 stub 窟窿的 TypeError 栈 |
| `scripts/parity_check.py` | P4 本地产物 vs 真机逐字符对账 |
| `assets/env_starter.py` | P2 起跑模板（最小 environment） |
| `assets/entry-report-template.txt` | P1 产出，填满即退出 P1 |

---

## §6 iv8 唯一运行底座

不要另造浏览器环境。iv8 已提供 `window`、DOM、BOM、XHR、Canvas、WebGL、Crypto、Timer 和事件循环；本 skill 只处理三类差异：

1. **画像值不符**：通过 `JSContext(environment=..., config=...)` 配置，并用 `consistency_lint.py` 拦截自相矛盾。
2. **已证实的 stub 空壳**：把补丁作为目标外部的 `stub_setup_js` 在原始 JS 之前注入；只实现目标实际调用的行为，函数或构造器用 `__iv8__.wrapNative` 保持原生表面，异步行为交给 `eventLoop.advance/drain`。
3. **iv8 不具备的物理量**：在真实浏览器采集原始测量值，把它声明为环境输入后注入 iv8；最终目标 JS、生成入口和产物仍在 iv8 中运行。

未知 API 默认保持 `undefined`。只有同时具备“真实 Chrome 确实存在、目标确实读取、iv8 当前实现不满足”三项证据时才补。不要导入通用 mock 框架，不要批量构造 window/DOM，不要把真实浏览器或其他 JavaScript 运行时当成 iv8 的替代执行链。具体判据与最小补丁结构见 `references/patching-principles.md` 和 `references/trap-blacklist.md`。
