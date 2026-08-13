# 静态分析与动态 Trace 证据

本文说明不同证据能够证明什么，以及如何让它们共同服务于唯一主线：从声明的原始输入恢复独立可执行映射，并与受控 iv8 Oracle 的最终输出精确一致。

## 目录

1. 三类证据
2. 静态分析能力
3. Trace 能力
4. 受控实验能力
5. Handler 语义证明
6. Trace 事件坐标
7. 数据流与切片
8. 控制流与函数边界
9. 首个分歧
10. 同值歧义
11. 观测扰动
12. 证据等级与声明

## 1. 三类证据

区分：

```text
静态证据
  来自解释器、字节码、元数据、CFG、Scope 和数据流

动态 Trace
  来自某个声明输入下的 PC、Opcode、Operand、栈、Frame、Record 和值变化

受控实验
  在只改变一个原始事实时，观察 Oracle 路径、中间值和最终输出的变化
```

三者回答不同问题：

| 问题 | 主要证据 |
|---|---|
| 这条指令可能读取哪个操作数 | 解释器和静态解码 |
| 这组输入实际走了哪条路 | Trace |
| 某个宿主属性是否决定了某个 bit | 静态依赖 + 单变量实验 |
| 未执行分支的公式是什么 | 静态 CFG/Scope |
| 独立实现在哪一步偏离 Oracle | 共同中间坐标和 Trace diff |
| 最终是否复现 | 同 RawInput 下的精确输出比较 |

不用任一类证据取代其他类型才能回答的问题。

## 2. 静态分析能力

静态分析可以恢复：

- Opcode 解码、操作数宽度和符号/字节序；
- Handler 对栈、PC、Scope、Frame 和宿主状态的全部显式分支；
- Record 元数据、异常表和创建/调用关系；
- 基本块、普通跳转边、异常边和不可达区域；
- def-use、数据消费者、中间字段布局和算法公式；
- 当前 Trace 未覆盖的分支和边界条件。

静态结论仍受以下因素限制：

- 间接索引、动态属性名和宿主回调；
- `eval`/动态载荷/WASM/运行时解密的新程序数据；
- 宿主 API 的 descriptor、prototype、异常、异步和运行时特殊语义；
- 别名、共享 Scope 和对象可变性导致的依赖扩散；
- 用途和作者意图，它们不能仅从公式中恢复。

对不确定间接边保留候选集，不为生成一张“完整”图而随意选一条边。

## 3. Trace 能力

一份良好的 Handler Trace 可以证明：

- 某个 `recordId + PC + opcode` 实际被执行；
- 本次执行使用的操作数和下一 PC；
- 执行前后栈、Scope、Frame 或关键值的变化；
- 实际的 Record/Frame 进出和调用顺序；
- 某个原始输入实例最终影响了哪些中间值和输出字节。

单次 Trace 不能自动证明：

- 未执行分支的存在条件和全部返回值；
- Handler 在不同操作数或类型下的所有语义；
- 一个数值的唯一业务来源；
- 所有可能的 Record、Frame 和源码函数数量；
- 观测 Hook 完全没有改变目标行为；
- 对未测输入的普遍等价。

把 Trace 覆盖写成明确数字：

```text
events captured / dropped / malformed
unique records reached
unique opcode IDs reached
unique (recordId, PC, opcode) coordinates
frame entries/exits
baseline input and output hash
```

## 4. 受控实验能力

受控实验用于在竞争解释中做区分。例如，基线中一个字节为 `1`，可能来自固定基础位、某个环境布尔值或某个计数器。仅看基线无法区分，但改变相应原始事实后可以观察路径和字节是否变化。

设计实验时：

1. 从已稳定基线复制输入。
2. 只修改一个原始事实，记录精确 diff。
3. 保持时间、随机和初始状态的消费顺序一致，或明确记录分支使顺序发生变化。
4. 同时检查 Record 返回值、下游写入位置和最终输出。
5. 保留不支持预期的负结果，不只保留成功样本。

实验结果可以验证静态公式，但不会自动恢复未触发分支的公式。

## 5. Handler 语义证明

为每个 Handler 建立机械合同：

```text
opcode ids and variants
operand decoding
preconditions and consumed VM state
stack/register/scope reads
stack/register/scope writes
pc transition
frame/call/return transition
host side effects
exception/completion behavior
observed trace instances
untested variants
```

确定 Handler 语义的强证据组合是：

```text
解释器分支公式
→ Bytecode 实例的操作数解码
→ Trace 前后状态转移
→ 下游消费者或受控变体
```

如果静态语义已经由解释器代码完整确定，未执行的分支可标记为“静态已确定，未专项动态覆盖”，不必降级为猜测。如果依赖未知宿主语义或间接索引，保留不确定性。

业务名称要求额外证据。`BITWISE_OR` 可以由 Handler 本身证明，`runtimeRiskBits` 还需要连接具体环境探针和最终材料消费者。

## 6. Trace 事件坐标

使用稳定坐标使静态与动态可对账：

```text
sourceHash
traceTargetHash
runId
recordId
frameId and parentFrameId
pcBefore
opcodeId
decodedOperands
pcAfter
stackBefore / stackAfter or declared slices
scope/register changes
host call or side effect
exception/completion
```

不要只用事件序号作为跨运行坐标，因为分支、异步和观测可使序号整体偏移。优先对齐 `recordId + PC + opcode + frame/call context`。

序列化对象时区分：

- 原始值；
- 安全摘要或类型标签；
- 为避免 getter/proxy 副作用而省略的字段。

不让 Trace 序列化本身额外读取目标 getter、展开 Proxy 或调用目标 `toJSON`。

## 7. 数据流与切片

使用正向数据流回答：

```text
某个原始输入被读取后，经过哪些 Record/Handler，最终写到哪些材料和输出？
```

使用反向切片回答：

```text
某个最终字节、摘要、header 或密文在当前执行中依赖哪些原始值和共享状态？
```

两者都是方法，不是固定顺序。入口少且输入边界清晰时，正向通常简单；最终输出已知但中间路径庞大时，反向切片可以快速收束主线。

静态切片包含可能依赖，动态切片只包含当前执行实例的实际依赖。报告时标明切片类型。

## 8. 控制流与函数边界

静态 CFG 与动态路径不同：

```text
static CFG edge   该边在程序语义上可能发生
dynamic edge      该边在当前运行中实际发生
```

使用 Trace 为静态边加覆盖标记，不删除未覆盖边。只在静态证据证明边不可达时标记不可达。

函数边界使用创建、捕获 Scope、调用、Frame 进入和 Return/Completion 共同确定。不要用 Trace 中一次 Record 切换自动推出源码级函数边界。

## 9. 首个分歧

当独立实现最终输出不同时，不从最终密文随机猜测。按共同坐标比较：

1. 原始输入读取顺序与值。
2. 最早的探针、计数器、摘要或状态变化。
3. 材料组装中的首个字节差异。
4. 时间/随机源的首个调用次数或值差异。
5. 打包、加密和编码的首个不同状态。

首个分歧是当前证据中最早可观测的偏差，不必然是根因所在的源码行。继续检查它的输入和前置状态。

## 10. 同值歧义

基线中多个来源可能有相同数值，例如：

```text
fixed bit = 1
boolean probe = true → 1
queue length = 1
invocation bucket = 1
version byte = 1
```

不要通过数值相同为字节赋予来源。使用：

- 静态 def-use；
- 中间写入的 PC/Record 坐标；
- 受控变体；
- 值类型、字节序和宽度；
- 下游多个消费位置。

如果多个解释在所有现有证据中不可区分，保留竞争假设，设计能分离它们的变体，或在完成声明中限定范围。

## 11. 观测扰动

Trace 代码可以影响：

- 时间和性能差；
- 随机调用顺序；
- getter、Proxy、descriptor 和对象枚举；
- 函数 `toString`、调用栈和 Error stack；
- event loop、Promise 和微任务时序；
- 反调试、完整性和自检分支。

优先选择能回答当前问题的最小观测面。保存：

```text
original source hash
derived trace target hash
instrumentation manifest
no-trace output
trace output
first output difference, if any
```

如果只有插桩目标可以运行，可用它提出假设和定位，但不要把其输出自动当作未修改原程序的 Oracle。

## 12. 证据等级与声明

使用以下标签保持表达准确：

```text
proven-static
  公式、分支或边由解释器/Bytecode/CFG/Scope 确定

observed-dynamic
  在声明输入和运行条件下被 Trace 观测

validated-variant
  静态预期经受控变体验证

exact-end-to-end
  同 RawInput 下独立实现与 Oracle 最终输出精确相等

inferred
  现有证据支持但存在未排除的竞争解释

unknown
  证据不足以确定
```

同一结论可以同时具有多个标签，例如一个公式既是 `proven-static` 又是 `validated-variant`。

最终完成仍回到主线：当前声明的原始输入范围内，独立实现是否能生成与受控 iv8 原程序精确相同的最终输出。Trace 和静态证据用来建立、解释和定位这个命题，不是另一个竞争性完成标准。
