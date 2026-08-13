# 用户交互、步骤报告与停止契约

本文规定 Agent 在解混淆过程中怎样向用户汇报、请求决策、升级动态、停止和交接。

用户只需要提供源码并说“解混淆”。用户不需要提前知道混淆类型、优先级、静态或动态路线、产物类型或 VM 边界；这些应由 Agent 阅读源码后判断并用普通语言解释。

## 目录

1. [核心交互原则](#1-核心交互原则)
2. [用户授权边界](#2-用户授权边界)
3. [稳定状态](#3-稳定状态)
4. [启动记录模板](#4-启动记录模板)
5. [准备阻塞模板](#5-准备阻塞模板)
6. [首轮画像摘要模板](#6-首轮画像摘要模板)
7. [用户方向反馈模板](#7-用户方向反馈模板)
8. [下一步决策卡](#8-下一步决策卡)
9. [静态转动态升级卡](#9-静态转动态升级卡)
10. [单步契约模板](#10-单步契约模板)
11. [单步报告模板](#11-单步报告模板)
12. [失败与阻塞模板](#12-失败与阻塞模板)
13. [关闭建议模板](#13-关闭建议模板)
14. [交接包模板](#14-交接包模板)
15. [PROGRESS.md 模板](#15-progressmd-模板)
16. [表达方式](#16-表达方式)
17. [反例](#17-反例)

## 1. 核心交互原则

1. “解混淆”已经是明确任务，不在启动前追问技术目标。
2. Agent 自动完成冻结、Prettier 格式化、完整直读和首轮画像。
3. 首轮画像前，用户不负责猜有哪些混淆或哪个优先。
4. Agent 先说明发现，再询问用户更关注的分析方向。
5. Agent 必须给出推荐及理由，不能只把技术选项甩给用户。
6. 每次默认只批准一个语义步骤。
7. 从静态升级为动态、联网、补环境、主动 Hook 或插桩时单独询问。
8. 每次报告区分观察事实、模型推断和待验证假设。
9. 停止依据是分析目的和边际收益，不是“是否还看得到难看代码”。
10. Agent 提议关闭，用户确认后才标记 `COMPLETE`。

以下情况才在首轮画像前询问：

- 没有提供目标文件或无法确定分析对象。
- 两条用户硬约束互相冲突。
- Prettier 安装或解析失败，且已穷尽安全的本地准备步骤。
- 继续会产生用户尚未授权的外部副作用。

不要在首轮画像前询问：

```text
你想分析什么算法？
你觉得它有什么混淆？
要静态还是动态？
要不要处理 VM？
你想要 executable-js 还是 analysis-js？
```

## 2. 用户授权边界

默认模式为 `interactive`。

Agent 可以自动完成：

- 只读查看目录和文档。
- 冻结原始输入并计算 hash。
- 在案例工作区本地准备 Node Prettier。
- 生成格式化派生副本。
- 连续区间阅读完整格式化源码。
- 运行只读搜索、AST 统计和语法检查。
- 建立当前可见模式清单、依赖和优先级。
- 为下一步提出 static、dynamic、hybrid 或 blocked 判断。
- 验证用户已经批准的步骤。

Agent 不得自动进入下一个语义 transform。

用户回复：

```text
按推荐做
继续
你来判断
```

默认只批准当前推荐的一个低风险步骤，不表示切换为全自动。

`batch` 需要明确边界，例如：

```text
允许连续完成字符串恢复和确定性常量折叠；
遇到动态、删除、控制流或重命名时停止。
```

`autonomous` 只有用户明确要求时启用。即使启用，遇到以下情况仍须停止：

- 执行不可信完整目标。
- 真实网络、账号、Cookie、凭据或浏览器状态。
- 主动 Hook、环境修改或插桩。
- 高风险删除或控制流重写。
- VM 内部分析。
- 新外部权限。
- 证据冲突或验证失败。

## 3. 稳定状态

对外检查点只使用以下状态：

| 状态 | 含义 |
| --- | --- |
| `FORMAT_BLOCKED` | Prettier 准备或解析失败，尚未完成源码画像 |
| `READY_FOR_USER_DECISION` | 画像或一步已验收，或者风险/证据路线需要用户重新选择 |
| `STEP_STOPPED` | 当前步骤失败或前提不成立，保留上一个通过版本 |
| `BLOCKED_CURRENT` | 当前候选缺证据或运行条件，仍可考虑其他候选 |
| `READY_FOR_HANDOFF` | 剩余问题超出 AST 边界，等待用户决定交接 |
| `READY_FOR_USER_CLOSURE` | 当前深度已有有用成果，等待用户确认结束 |
| `COMPLETE` | 用户已经确认结束 |

进行中的准备、画像和 transform 写入 `current_phase`，不要为它们另造对外完成状态。

## 4. 启动记录模板

启动记录用于 `PROGRESS.md`，通常不需要先发问题给用户。

```markdown
# Start

## User Request

用户原话：

## Analysis Object

- original path:
- original size:
- original sha256:
- workspace:

## Safe Defaults

- mode: interactive
- default output: analysis-js
- original file: read-only
- runtime execution: not authorized
- network: not authorized
- VM internal analysis: out of scope

## Automatic Preparation

- [ ] freeze original input
- [ ] prepare local Node Prettier
- [ ] generate formatted copy
- [ ] parse formatted copy
- [ ] read complete formatted source
- [ ] build current-visible profile

## Questions Deferred Until Profile

- downstream analysis direction
- desired depth
- first semantic step
```

如果缺少目标文件，只问一个能解除阻塞的问题：

```text
我还缺少要解混淆的 JavaScript 文件路径。请给出文件或目录；拿到后我会先格式化、完整阅读并汇报当前可见混淆，不要求你先判断技术路线。
```

## 5. 准备阻塞模板

只在进入 `FORMAT_BLOCKED` 时使用：

```markdown
## 准备阶段阻塞

- 状态：`FORMAT_BLOCKED`
- 原始文件：
- 原始 sha256：
- 已完成：
- 失败位置：Node | package manager | Prettier install | Prettier parse
- 实际命令：
- 工具版本：
- 退出状态：
- 精确错误摘要：
- 已尝试的安全修复：
- 原始文件是否保持不变：是
- 当前不能继续的原因：
- 建议选择：
  1. 提供可解析的目标或 parser 线索；
  2. 允许按明确方案修复准备环境；
  3. 暂停。
```

不要静默改用其他 formatter，也不要跳过格式化假装完成画像。

## 6. 首轮画像摘要模板

画像完成后先给结论，再给技术证据。

```markdown
## 当前源码画像

我已经完成原始文件冻结、格式化和完整阅读。

### 一句话结论

<用普通语言说明主要阅读障碍、核心依赖和推荐起点。>

### 当前可见模式

- 模式家族数：
- 候选出现总数：
- 高收益区域：
- 低收益或无关区域：
- 当前未证明的依赖：

| ID | 当前可见结构 | 出现次数与范围 | 它阻碍什么 | 证据 | 依赖 | 证据路线 | 初步优先级 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `P-01` |  |  |  |  |  | static/dynamic/hybrid/blocked |  |

### 分类说明

| 类别 | 当前识别 |
| --- | --- |
| 真正混淆 |  |
| 压缩或编译产物 |  |
| 打包器结构 |  |
| 第三方或 polyfill |  |
| VM 外围 |  |
| VM 内部，暂不处理 |  |

### 模式依赖

```text
P-01 → 解锁 P-03、P-04
P-02 → 独立
P-05 → 需要运行事实
```

### 推荐

推荐先做：`<候选>`

原因：

- 解锁范围：
- 当前证据：
- 预期收益：
- 风险：
- 本步不处理：

### 当前画像边界

这是一份“当前可见模式”清单。完成字符串恢复或其他步骤后，可能出现新结构，我会重新阅读和排序。
```

“出现次数”必须说明计数口径；模式家族数量与语法命中数量不能混为一谈。

## 7. 用户方向反馈模板

用户看到画像后，再询问分析方向。使用普通语言：

```markdown
## 你现在可以决定分析方向

根据当前源码，我建议 `<推荐方向>`。

你可以直接回复：

1. **按推荐继续**：先完成当前收益最高的一步；
2. **重点看输入、输出和外部调用**：优先建立入口与数据流；
3. **为后续算法或 VM 分析做准备**：优先清理外围并建立稳定坐标；
4. **先停在画像报告**：暂不修改分析视图。

如果你不确定，回复“按推荐继续”即可。这只批准下一步，不会自动执行完整流水线。
```

选项应根据真实源码删减为 2～3 个真正不同的方向，不机械展示全部四项。

## 8. 下一步决策卡

每次只展示少量高价值选择：

```markdown
## 当前状态

- 状态：`READY_FOR_USER_DECISION`
- 已完成：
- 最新分析视图：
- 当前主要残留：

## 下一候选

### A. `<推荐项>`

- 当前要回答的问题：
- 已知事实：
- 证据缺口：
- 证据模式：static | dynamic | hybrid
- 最小方法：
- 执行范围：
- 预期收益：
- 风险：
- 本步不处理：
- 预计产物：
- 推荐理由：

### B. `<替代项>`

- 当前要回答的问题：
- 证据模式：
- 最小方法：
- 预期收益：
- 风险：
- 与 A 的差别：

### C. 暂停、关闭或交接

- 当前已足够支持：
- 继续的额外收益：
- 可交接方向：

## 请你决定

回复 A、B、C 或“按推荐做”。
```

不要只问“是否继续”。不要展示五六个技术名词相近的选项。

## 9. 静态转动态升级卡

用户批准静态步骤后，如果中途发现必须动态，立即暂停静态 transform。

```markdown
## 动态取证申请

- 状态：`READY_FOR_USER_DECISION`

### 当前静态步骤

- 用户已批准：
- 已完成到：
- 上一个通过验收的视图：
- 当前视图是否已覆盖：否
- 步骤账本：暂停，等待动态证据

### 为什么静态不足

- 静态已经证明：
- 唯一或有限的运行事实缺口：
- 该事实为什么决定当前 transform：

### 最小动态实验

- 要回答的问题：
- 执行目标：
- original sha256：
- 入口与前置条件：
- 固定输入：
- trigger：
- 观察点：
- 观测等级：L0 | L1 | L2 | L3 | L4
- iv8 / 受控 Node / 真浏览器：
- environment / config：
- time mode：
- event loop 策略：
- 是否联网：
- 是否使用账号、Cookie 或凭据：
- 是否安装 probe：
- 是否运行插桩副本：
- `runtime patched`：true | false
- A/B 基线：
- 原始日志路径：
- 源码映射方法：

### 风险和边界

- 可能的运行时影响：
- 覆盖的输入和路径：
- 本次明确不能证明：
- 成功条件：
- 失败后分流：

### 请你决定

1. 批准本次有限动态实验；
2. 不执行，改做其他静态候选；
3. 暂停或交接。
```

用户选择第 2 项时，把原暂停候选记为 `BLOCKED_CURRENT`，再返回其他候选；不要把“不批准动态”记成 transform 验证失败。

不要说：

```text
静态解不了，要不要动态？
```

要说清楚缺哪个事实、为什么需要、只执行什么。

## 10. 单步契约模板

用户批准后，回到入口文件进入对应验收阶段。不要在交互文件重复保存 hash、binding、副作用、动态证据和验收字段。

对用户只需确认：

```markdown
## 已批准步骤

- 当前问题：
- 本步会修改：
- 本步不处理：
- 证据模式与最小方法：
- 主要风险：
- 停止条件：
```

单步只处理一种明确结构，不把字符串、代理、死代码、控制流和重命名混在一起。

## 11. 单步报告模板

完整验收事实写入 validation report；对话只交付用户做下一次决策需要的摘要：

```markdown
## 本步结果

- 结果：完成 | 部分完成 | 失败
- 最新分析视图：
- 已证明：
- 修改 / 跳过 / 残留：
- 验收：PASS | FAIL | BLOCKED
- 本步现在改善了什么：
- 仍未证明：
- 下一推荐：
- 真正不同的替代项：
- 当前状态：
```

必要时链接完整报告并给一个短小的 before/after 片段。不要把内部验证账本复制进对话。

## 12. 失败与阻塞模板

### 当前步骤停止

```markdown
## 当前步骤已停止

- 状态：`STEP_STOPPED`
- 原因：
- 失败的前提或验证：
- 上一个通过版本：
- 原始文件是否不变：是
- 是否产生未通过输出：
- 未通过输出如何标记：
- 已证明：
- 未证明：
- 可选下一步：
```

不得把失败输出覆盖成最新通过视图。

### 当前候选阻塞

```markdown
## 当前候选暂时阻塞

- 状态：`BLOCKED_CURRENT`
- 候选：
- 相关性：
- 已有证据：
- 缺少：
- 解除阻塞需要：
- 是否需要用户新授权：
- 其他仍可进行的静态候选：
- 推荐：
```

一个候选 blocked 不等于整个 Skill blocked。先继续评估其他静态候选。

## 13. 关闭建议模板

Agent 只能建议关闭：

```markdown
## AST 解混淆关闭建议

- 状态：`READY_FOR_USER_CLOSURE`

### 用户请求与当前深度

- 用户原始请求：
- 画像后选择的方向：
- 当前约定深度：

### 已经完成

- 已证明：
- 已处理的主要隐藏层：
- 最新分析视图：
- 可稳定定位的入口、数据流或边界：

### 仍然存在

| 残留 | 分类 | 为什么未处理 | 影响 |
| --- | --- | --- | --- |
|  | low-value / blocked / handoff / unrelated |  |  |

### 为什么现在建议停止

- 当前成果已经支持：
- 下一步边际收益：
- 下一步成本或风险：

### 你可以选择

1. 确认结束 AST 阶段；
2. 继续一个明确的可选步骤；
3. 交接算法、动态运行、补环境、真实浏览器或 VM 分析。
```

只有用户确认第 1 项，才写：

```text
status: COMPLETE
```

如果用户没有确认，保持 `READY_FOR_USER_CLOSURE`。

## 14. 交接包模板

进入 `READY_FOR_HANDOFF` 时：

```markdown
# AST Deobfuscation Handoff

## Handoff Direction

algorithm | iv8 runtime | environment completion | real browser/CDP | VM

## Why Handoff

- AST 已经完成到：
- 继续需要的能力：
- 为什么不属于当前 Skill：

## Source Artifacts

| Role | Path | SHA-256 | Notes |
| --- | --- | --- | --- |
| original |  |  | read-only runtime target |
| formatted |  |  | reading view |
| latest analysis |  |  |  |
| annotated/pseudocode |  |  | optional |

## Proven Facts

## Inference

## Open Questions

## Stable Coordinates

| ID | Role | Original Location | Analysis Location | Evidence |
| --- | --- | --- | --- | --- |
|  | entry/binding/slot/host boundary/output |  |  |  |

## Runtime Material

- environment/config:
- input:
- init order:
- trigger:
- probe:
- instrumented copy:
- raw logs:
- netLog:
- runtime patched:
- A/B result:
- covered paths:

## VM Boundary, If Applicable

- loader:
- interpreter entry:
- public init:
- host bindings:
- data/bytecode region:
- explicitly not analyzed:

## Recommended First Question for Next Stage

## Risks and Non-Conclusions

## User Decision
```

交接不是失败。它表示剩余问题需要另一种能力。

## 15. PROGRESS.md 模板

`PROGRESS.md` 是项目账本，必须让新 Agent 不依赖聊天记录即可继续。

```markdown
# Deobfuscation Progress

## Current Checkpoint

- status:
- current_phase:
- updated_at:
- user mode: interactive | batch | autonomous
- approved scope:
- waiting for:

## User Intent

- original request:
- constraints:
- direction chosen after profile:
- current working objective:

## Input Freeze

- original path:
- size:
- sha256:
- read-only confirmed:

## Preparation

- Node version:
- package manager:
- Prettier version:
- lockfile:
- formatter command:
- parser/config:
- formatted path:
- formatted sha256:
- parse result:
- complete-reading coverage:

## Current Profile

- current-visible family count:
- counting rule:
- high-value candidates:
- dependencies:
- blocked candidates:
- skipped regions:

| ID | Pattern | Count/Scope | Evidence | Priority | Classification | Status |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |

## Artifact Ledger

| Role | Path | SHA-256 | Type | Passed | Notes |
| --- | --- | --- | --- | --- | --- |
| original |  |  | original | yes | read-only |
| formatted |  |  | analysis-js |  |  |
| current |  |  | analysis-js |  |  |

## Step Ledger

| Step | User Approval | Question | Evidence Mode | Input | Output | Validation | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |

## Runtime Evidence Ledger

| ID | Question | Level | Target SHA | Trigger/Probe | Patched | A/B | Coverage | Mapping |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |

## Validation Facts

## Proven Facts

## Inference

## Open Hypotheses

## Residual and Classification

## Last User Decision

## Next Recommended Action

## Handoff or Closure Readiness
```

每一步后更新：

- 当前状态和阶段。
- 新增产物及 hash。
- 用户批准范围。
- 画像、计数、依赖和优先级。
- 验证事实。
- 动态证据和覆盖范围。
- 下一推荐动作。

## 16. 表达方式

面向用户时：

- 先说结果，再说证据。
- 使用“它阻碍了什么”解释技术结构。
- 明确推荐，不要求用户理解 AST 术语后才能选择。
- 每个选项说明收益、风险和不处理范围。
- 把事实、推断和假设分开。
- 大报告写入文件，对话只给摘要和下一决策。

推荐表达：

```text
我看到 4 类当前可见结构，其中字符串索引同时阻碍入口和调用关系，且静态证据足够，因此建议先恢复它。本步不执行目标代码，也不处理 VM。
```

避免表达：

```text
发现字符串池、代理函数、控制流平坦化和 JSVMP，你想先搞哪个？
```

## 17. 反例

### 启动反例

- 还没看源码就让用户描述混淆类型。
- 把“解混淆”当成目标不明确。
- 首轮画像前让用户选择 static 或 dynamic。

### 决策反例

- 只问“继续吗”。
- 不给推荐，让用户从十个 AST 名词中选择。
- 用户批准一步后自动执行整条流水线。
- 把“你来判断”解释成永久自动授权。

### 动态反例

- 静态处理中静默执行完整目标。
- 不写事实缺口，只说“静态解不了”。
- 不记录 target hash、trigger、probe、环境和覆盖路径。
- 把 wrapper 称为零侵入。
- 用一次运行证明全部输入。

### 报告反例

- 只给修改行数，不解释分析收益。
- 混合事实、推断和假设。
- 失败输出覆盖上一个通过版本。
- 省略 skipped、residual 和验证失败。

### 停止反例

- 因仍有短变量而拒绝停止。
- 因分析视图不可运行而拒绝交接。
- 自动将 `READY_FOR_USER_CLOSURE` 改为 `COMPLETE`。
- 把 VM 交接写成 AST 解混淆失败。
