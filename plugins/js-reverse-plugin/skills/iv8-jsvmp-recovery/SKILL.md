---
name: iv8-jsvmp-recovery
description: >-
  以受控 iv8 中的原始 JavaScript/JSVMP 作为参考实现，结合静态解释器、Bytecode、Handler、Opcode、Record、CFG 分析和动态 Trace，恢复从声明的原始输入到最终签名、Token 或密文的独立可执行映射，并以精确等价验收。用于 JSVMP/VMP 语义恢复、字节码反汇编或反编译、Handler 准确语义、Record/虚拟函数边界、调用图或控制流、字符串恢复、静态结果与 Trace 对账、受控输入试验、以及 Python/JavaScript 独立实现的端到端复现。不负责通用外层 AST 解混淆、iv8 安装与通用补环境，也不把服务器接受当作 VM 语义等价的唯一证明。
---

# iv8 JSVMP Recovery

## 主线

始终围绕同一个目标展开分析：

> 以受控 iv8 中的原始程序作为参考实现，结合静态分析和动态 Trace，恢复从声明的原始输入到最终输出的独立可执行映射，并以精确等价作为验收标准。

把 Handler 命名、Record 拆分、CFG、字符串解密、Trace 和中间值对账都视为恢复这个映射的证据或手段，不把它们自身当作最终目标。

## 正确性定义

先声明原始输入合同：

```text
RawInput =
    request
  + environment
  + behavior
  + time
  + randomness
  + configuration
  + initialState

OracleOutput = OriginalVMP_in_Controlled_iv8(RawInput)
RecoveredOutput = IndependentImplementation(RawInput)

验收：RecoveredOutput === OracleOutput
```

把 `===` 解释为声明编码下的长度相同且逐字节或逐字符完全一致。不用“结构差不多”、“可以解密”、“服务器接受”或“某个中间值相同”代替这个命题。

区分结论范围：

- 固定基线精确相等，证明该受控执行实例已被复现。
- 受控变体和静态全分支证据，用于扩大可声明的语义范围。
- 不要把一个固定实例的成功推广为所有环境、状态和未执行路径的函数等价。

## 原始输入边界

从宿主可观测事实开始建模。允许输入请求、环境属性、原始行为事件或初始队列状态、时间源、随机源、SDK 配置、存储/网络响应和共享初始状态。

不把下列 VM 派生值伪装为原始输入：

- 已计算的摘要、风险位、特征向量或行为编码；
- 已组装的 core、header、prefix、checksum 或 material；
- 预计算的密钥流、密文、随机打包结果或最终签名。

要求独立实现自己从 `RawInput` 计算这些派生值。

## 领域判断

保持以下区分：

- Handler 是解释器操作实现，Opcode 是程序数据中的编码，两者不必然一一对应。
- Record 是样本定义的 VM 程序单元，不天然等于源码函数、调用帧或基本块。
- 机械语义描述操作数、栈/寄存器、PC、Frame、Scope 和副作用；业务语义还需要连接真实输入、消费者和最终输出。
- 静态分析描述可能的分支和数据依赖；动态 Trace 证明某一受控输入下真实执行的路径和值。
- 使用 Trace 对账、反驳和定位首个分歧；不把一次 Trace 当作全路径证明。
- 只在字符串是加密/编码常量且恢复后能连接当前映射时解密；不把字节码数据、字符串索引或普通字面量统一视为“待解密字符串”。

## 分析自由度

根据证据自行选择正向、反向或交替分析；根据问题选择局部切片、主线 CFG 或全库 CFG；根据现有条件调整静态与动态的比例。

不强制：

- 先恢复所有 Handler；
- 先反编译全部 Bytecode；
- 先建立完整 CFG 或调用图；
- 必须从入口正向或从输出反向；
- 把某个案例的分析顺序复制到其他 VM。

根据当前声明的输出和证据缺口收束范围。如果局部主线已经足以从原始输入精确复现最终输出，不要为了形式完整继续扩展不影响该命题的全库细节。

## 不可接受的伪正确

不要作出以下完成声明：

- 写死最终输出或只复现一个常量字符串；
- 公开入口仍然接收 VM 预计算中间字段；
- 只因服务器接受请求就声称本地计算与原 VM 等价；
- 只因 Trace 中数值相同就填入未证明的业务名称；
- 把 Handler、Opcode、Record 或 Trace 覆盖数量直接当作源码函数数量；
- 修改原始程序或执行环境后，仍把结果冒充为原始 Oracle；
- 没有声明时间、随机、存储、网络、初始化顺序和共享状态。

## 与相邻 Skill 的边界

- 使用 `js-ast-deobfuscation` 处理外层 JavaScript、打包器、字符串隐藏、解释器宿主边界和 JSVMP 识别。
- 使用 `iv8-env-runtime` 完成 iv8 安装、通用补环境、网络/事件循环接续和原始程序的稳定执行。
- 在本 Skill 中消费已确认的 VM 边界和受控 Oracle，恢复 VM 内部映射并构建独立实现。

原始程序尚不能受控复现时，先建立 Oracle 条件；尚未确认 VM 闭环时，先完成外层识别。不在本 Skill 中重写相邻 Skill 的工具和环境知识。

## 证据与产物

记录并持续区分：

- 原始程序、Bytecode、配置和 `RawInput` 的版本与 Hash；
- 已证明的机械语义、有证据的业务解释、推断和未知；
- Oracle 运行条件、原始输出、Trace 覆盖和观测扰动；
- 独立实现的输入合同、中间对账点和最终等价报告；
- 完成声明的适用输入范围和未覆盖边界。

不要强制统一产物文件名；优先沿用项目已有证据目录、坐标和格式。

## Reference 路由

只由本文件路由 reference；reference 不再继续路由其他 reference。

- 需要判断 Handler、Opcode、Record、Frame、Scope、VM 函数、基本块、CFG 或 VM 字符串时，读取 [vmp-domain-model.md](references/vmp-domain-model.md)。
- 需要建立受控 iv8 基线、定义 `RawInput`、区分派生字段、设计变体或声明精确等价时，读取 [controlled-oracle-and-equivalence.md](references/controlled-oracle-and-equivalence.md)。
- 需要结合静态与 Trace、确定证据范围、评估 Handler 语义或定位首个分歧时，读取 [static-trace-evidence.md](references/static-trace-evidence.md)。
- 当前对象是课程中的抖音 `a_bogus` 样本，或需要查看完整成功案例的证据结构时，读取 [case-study-douyin-a-bogus.md](references/case-study-douyin-a-bogus.md)。

只读取当前问题需要的 reference。案例可用于提出假设，不能覆盖当前样本证据。

## 精确等价脚本

在声明固定输入精确等价时，执行 `scripts/verify-equivalence.py --help`，再用它对 `RawInput`、Oracle 输出和独立实现输出生成机器可读报告。

该脚本只证明给定字节是否精确相等，不判断输入是否真正原始、实现是否独立，也不把单样本相等推广为全输入空间等价。
