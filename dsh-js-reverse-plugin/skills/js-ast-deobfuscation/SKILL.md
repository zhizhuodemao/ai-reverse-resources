---
name: js-ast-deobfuscation
description: >-
  对混淆 JavaScript 建立证据驱动、用户逐步决策的 AST 解混淆工作流。用于用户要求解混淆、提高可读性、识别混淆结构、恢复字符串或名称、分析打包器与动态载荷、为算法分析或 JSVMP/VM 分析准备宿主边界时；先保护原始输入并格式化派生副本，直接阅读源码和建立画像，再为每个候选选择静态、受控局部执行、动态、混合、阻塞或交接路线。可使用 iv8 等运行能力取得最小动态证据，但不要求先补环境，也不反编译或插桩 VM 内部。
---

# JS AST Deobfuscation

## 目的

生成方便阅读、搜索、定位、动态观测和后续算法分析的派生视图。解混淆服务于分析，不以“清理干净”、恢复作者原名或生成可独立运行的源码为目标。

分析视图可以不可执行，只要明确产物类型、保留原始运行目标，并且不妨碍当前与下一阶段分析。

## 不可跳过的边界

1. 固定原始输入和 SHA-256；不修改原始文件。
2. 使用本地 Node Prettier 格式化派生副本，再从连续源码片段直接阅读完整文件。AST、搜索和统计只用于复核，不代替阅读。
3. 从真实源码建立画像，区分观察事实、推断和未知；不根据文件名、课程主题或旧案例预判。
4. 区分真正混淆、压缩/转译、打包器、polyfill、第三方代码、环境检测、动态载荷与 VM 外围。
5. 检查字符串隐藏。真实字符串隐藏确实阻碍主要消费者时，把字符串恢复作为第一个语义推荐；普通字面量、第三方数据、压缩资源和 VM 字节数据不因此改写。
6. 首轮画像完成后再询问用户分析方向。一次批准默认只覆盖一个语义步骤。
7. 不执行未经授权的完整未知代码，不把 `node:vm` 当安全沙箱；动态执行、真实网络、会话、Hook、插桩、删除和高风险控制流必须单独说明并取得批准。
8. 不在本 Skill 中反编译、解释或插桩 VM 的 Opcode、PC、值栈、帧栈和虚拟控制流。

不使用固定 transform 流水线。字符串门之后的顺序由最新源码、用户方向、依赖、证据、收益和风险决定。

## 准备与首轮画像

1. 确定唯一输入文件；目录中有多个合理候选且无法从入口关系判断时再询问。
2. 执行 `scripts/prepare-source.mjs --help`，再用它创建隔离工作区、原始副本、格式化视图和准备报告。直接执行脚本，不需要先把脚本读入上下文。
3. 脚本找不到本地 Prettier 时，在案例工作区的隔离 `tooling/` 中安装并锁定版本；不修改项目原有 `package.json`。联网或权限策略要求批准时先申请，再把本地可执行文件路径传给脚本。
4. 先不读取任何 reference，按连续区间阅读完整的 `steps/00_formatted.js`，只记录已读范围、真实片段和原始锚点，不先套模式清单。文件很大时跨轮继续，不能用抽样或脚本摘要代替未读区间。
5. 读到 EOF 后才读取 [first-pass.md](references/first-pass.md)，用它复核阅读覆盖并建立画像。在第一次用户决策前不读取其他 reference；只有首轮无法继续的异常情况可以提前读取对应文件，并说明原因。
6. 生成 `ANALYSIS.md` 和首轮决策卡，状态进入 `READY_FOR_USER_DECISION`。

准备失败时保留原始输入和错误证据，进入 `FORMAT_BLOCKED`；不要通过删除语句、补括号或静默更换 formatter 绕过失败。

## 核心循环

每次只处理一个明确问题：

```text
读取最新分析视图
  → 更新候选问题与依赖
  → 判断 static / local-exec / dynamic / hybrid / blocked / handoff
  → 比较收益、风险和证据缺口
  → 推荐一个步骤并等待用户决定
  → 写出范围、前提、验证和停止条件
  → 执行一个 transform 或最小取证实验
  → 验证并生成新的派生视图
  → 重新直接阅读受影响区域和消费者
  → 重新画像、排序、汇报
```

不要在一步中混合字符串替换、代理内联、死代码删除、控制流重写和语义命名。样本专用 transform 必须可重放、有前提、有失败条件；按 binding 和作用域改写，不按名称文本全局替换。

## 静态与动态分流

- `static`：AST、作用域、引用、常量、def-use 和调用关系足以证明，直接静态处理。
- `local-exec`：decoder 闭合、输入可冻结、无宿主依赖，只执行最小闭合切片，不运行完整目标。
- `dynamic`：必须运行才能取得当前事实，且不需要 AST 写回才成立。
- `hybrid`：静态定位，动态取证，再把已经证明的结果映射回 AST。
- `blocked`：静态不足，也没有可信、已授权或可复现的执行条件；只阻塞当前候选。
- `handoff`：需要系统补环境、真实浏览器、纯算法阶段或 VM 内部能力。

动态不等于补环境。环境已经存在不是选择动态的理由；环境未完成也不阻塞证据已经充分的静态步骤。

已批准的静态步骤发现必须动态时立即停止，说明静态证明到哪里、只缺哪个运行事实、最小实验及风险，等待新的批准。不得把静态授权扩大为完整执行、联网、Hook 或插桩。

动态观测选择能回答问题的最低侵入层：

```text
L0 运行时旁路日志
L1 外部调试器、watch、scope 和表达式求值
L2 独立 harness / trigger
L3 独立 probe 或 Hook，保存无 probe / 有 probe A/B
L4 派生插桩副本，降低证据等级并保留位置映射
```

不在原始 JavaScript 中插入 `console.log`、`debugger` 或日志代码。任何 debug、wrapper、Hook 和环境补丁都记录为运行条件。

## 用户决策

默认采用 `interactive`：

- 自动完成准备、完整阅读、首轮画像、字符串门和候选排序。
- 用结果语言说明候选，例如“恢复隐藏文本和属性名”或“建立 VM 宿主边界”，不让用户选择 AST 术语或工具。
- 提供推荐项、真正不同的替代项和暂停/交接，共 2～3 个互斥选项。
- 用户回复“继续”“按推荐做”或“你来判断”，只批准当前一个低风险推荐步骤。
- 用户不回应时停止，不自行执行后续语义步骤。

只有用户明确给出范围才进入批量模式；遇到动态升级、删除、高风险控制流、语义命名、验证失败或阶段切换时退出批次。

## 验证、产物与停止

每一步至少记录输入与输出 hash、匹配/修改/跳过/残留数量、parse 结果、binding/reference/shadow/alias 检查、确定性重跑和原始到派生映射。动态步骤再记录环境、输入、补丁、观测层级、日志、覆盖范围和 A/B。

声明产物类型：

- `analysis-js`：默认分析视图，可以不可执行。
- `annotated-view`：带证据注释的阅读视图。
- `executable-js`：只有明确要求并完成行为验收时使用。
- `pseudocode`：必须明确不是 JavaScript。

主要隐藏层已经处理、阻塞或交接，没有未经评审的高收益 AST 候选，而且最新视图足以支持当前或下一阶段时，提出关闭。第三方短名、分析视图不可执行或 VM 未还原都不是拒绝停止的理由。

整体只有在用户确认后进入 `COMPLETE`；否则使用：

```text
FORMAT_BLOCKED
READY_FOR_USER_DECISION
STEP_STOPPED
BLOCKED_CURRENT
READY_FOR_HANDOFF
READY_FOR_USER_CLOSURE
```

## VM 边界

允许整理 VM 加载器、解释器外围和宿主 JavaScript，恢复外层字符串与确定性载荷，标记入口、数据区、宿主 binding、slot 和公开 API，并建立原始位置、派生位置和下一阶段问题清单。

大数组、数字 ID、`while` 或 dispatcher 单独出现都不足以确认 JSVMP。只有“程序作为数据 → 重复取指分派 → 持续虚拟状态 → 抽象指令语义”在同一数据流闭环中成立，才确认解释器结构；再连到目标公开或业务路径，才确认目标业务使用 JSVMP。

使用 `entry_12`、`slot_7`、`opcode_38` 等中性坐标。证据不足时不填入业务语义；需要 Opcode、字节码、虚拟栈或虚拟控制流时交接 VM Skill。

## Reference 路由

只有本文件决定何时读取 reference；reference 不再继续路由其他 reference。

- 普通首轮准备、完整阅读、画像、字符串门、排序和第一次决策：只读 [first-pass.md](references/first-pass.md)。
- 首轮后遇到难以分类的模式、误判风险或需要重新排序：读 [patterns-and-priority.md](references/patterns-and-priority.md)。
- 首轮后或用户明确询问时，需要判断候选是否真的构成 JSVMP、区分数字模块或确定 AST/VM 边界：读 [jsvmp-identification.md](references/jsvmp-identification.md)。
- 用户选择候选后，需要设计静态、局部执行、动态或 hybrid 方法：读 [methods-and-evidence.md](references/methods-and-evidence.md)。
- 执行 transform 或接受动态结论前：读 [validation-contract.md](references/validation-contract.md)。
- 用户批准动态取证且选择 iv8 后：读 [iv8-runtime-observation.md](references/iv8-runtime-observation.md)。
- 风险升级、失败、批量模式、停止或交接需要详细模板：读 [interaction-and-stopping.md](references/interaction-and-stopping.md)。
- 发现流程异常或专门审计设计时：读 [anti-patterns.md](references/anti-patterns.md)。

只读取当前阶段需要的一份 reference。案例只能帮助提出假设，不能覆盖当前源码证据。
