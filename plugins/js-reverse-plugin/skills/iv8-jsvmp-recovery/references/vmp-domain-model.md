# VMP 领域对象与语义边界

本文用于避免把 Handler、Opcode、Record、VM 函数、基本块和源码函数混为同一层。所有对象都服务于同一主线：恢复受控 iv8 原程序从声明的原始输入到最终输出的独立可执行映射。

## 目录

1. 分析层次
2. Handler 与 Opcode
3. Record、Frame 与 VM 函数
4. 基本块、CFG 与调用图
5. 机械语义与业务语义
6. 字符串与数据恢复
7. 数量口径
8. 适度恢复

## 1. 分析层次

把常见 JSVMP 分成以下层次：

```text
宿主 JavaScript 与公开入口
  → 解释器和加载器
  → VM 程序数据 / Record 容器
  → Bytecode / Opcode / Operand
  → Handler 对 VM 状态的转移
  → VM Frame / Scope / Value Stack / PC
  → 虚拟基本块、函数和调用关系
  → 业务输入、中间材料和最终输出
```

每层回答不同问题。不要用一层的数量、名称或边界直接代替另一层。

## 2. Handler 与 Opcode

### Opcode

Opcode 是 VM 程序数据中的指令编码。它可以是单字节、变长整数、经过映射的 ID，或与操作数共同解码的位域。

确定 Opcode 时记录：

```text
encoded form
decoded id
operand widths and decoding
next-PC rule
dispatch target
```

### Handler

Handler 是解释器对某类指令的实现。它通常读取操作数和 VM 状态，再改变 PC、值栈、Scope、Frame、Completion 或宿主对象。

不假设两者一一对应。可能存在：

- 一个 Opcode 对应一个 Handler；
- 多个 Opcode 共用一个 Handler，由操作数或模式位分流；
- 一个 Opcode 通过二次分派进入多个语义分支；
- 无效、保留或未被当前程序使用的 Opcode；
- 仅在解释器内部使用、不从 Bytecode 直接取指的辅助操作。

不要用“JS 中有多少个函数体”自动推出 Opcode 数量。使用实际取指空间、分派表、解码规则和 Bytecode 引用共同确定口径。

## 3. Record、Frame 与 VM 函数

### Record

Record 是样本定义的程序数据单元，没有跨 VM 的统一语义。它可能包含：

```text
bytecode
formal bindings or parameter count
strict-mode flag
exception table
constant references
scope metadata
```

当前 VM 中的 Record 可以类似一个可调用代码对象，但不要把这个经验推广为定义。

### Frame

Frame 是一次动态执行实例。同一个 Record 可能因递归、重入或多次调用产生多个 Frame。Frame 可能持有：

```text
record id
pc
operand/value stack
arguments and this
lexical/environment chain
return continuation
completion or exception state
```

因此：

```text
Record count != Frame count
Trace frame count != source function count
```

### VM 函数

VM 函数是可调用的虚拟语义单元。它可以由一个 Record 承载，也可以通过闭包创建指令把 Record 与当前 Scope 绑定后形成。

确认 VM 函数边界时查看：

- 创建指令和捕获的 Scope；
- 调用指令和参数绑定；
- 入口 PC 和返回/Completion 规则；
- 动态 Frame 进出证据；
- 宿主函数与 VM 函数的转换边界。

## 4. 基本块、CFG 与调用图

基本块是单入口、在块内按顺序执行、以控制转移结束的指令序列。使用以下坐标划分候选块：

- Record 入口；
- 跳转目标；
- 条件或无条件跳转后的下一条指令；
- Return、Throw、Completion 或帧切换；
- 异常表入口。

区分三种图：

```text
intra-record CFG   Record 内部控制流
VM call graph      VM 函数/Record 间创建与调用关系
business dataflow  从原始输入到最终输出的值依赖
```

完整 CFG 是可用产物，但不是每个目标的必要前置。如果最终映射只依赖一个可证明的主线切片，先恢复该切片；如果间接跳转、异常、共享状态或未覆盖分支影响输出，再扩大图的范围。

## 5. 机械语义与业务语义

先给 Handler 建立低语义合同：

```text
operands
values read
values written
stack before/after
scope/register effects
pc effect
frame/call effect
host side effect
exception/completion effect
```

例如：

```text
LOAD_SCOPE depth, slot
GET_PROPERTY
CALL argc
JUMP_IF_FALSE relativeTarget
RETURN
```

这些名称只描述机械操作。只有在数据流连接真实宿主输入和消费者后，才使用 `runtimeRiskBits`、`behaviorBits`、`buildSignatureMaterial` 等业务名称。

为每个语义名称标记级别：

```text
mechanically proven
business-linked
inferred
unknown
```

不以可读性为理由消除不确定性。

## 6. 字符串与数据恢复

先分类再决定是否解密：

| 类型 | 特征 | 处理 |
|---|---|---|
| 普通常量 | 直接被属性、比较或 API 消费 | 直接标注消费者 |
| 字符串池 | 索引或简单 decoder 访问 | 恢复索引映射和真实字面量 |
| 编码/加密常量 | 经稳定 decoder 后进入主线 | 在前提和输入可固定时恢复 |
| 运行时派生字符串 | 依赖环境、时间、随机或状态 | 保留输入合同，不固化一次结果 |
| VM 程序数据 | 数字数组、Record 字节流或异常表 | 按格式解码，不冒充为文本解密 |

只在恢复后能增强 `RawInput → FinalOutput` 映射时投入字符串解密。对不影响当前映射的调试文本、第三方资源和不可达常量保持低优先级。

## 7. 数量口径

报告数量时始终同时报告计数对象和发现方法：

```text
N dispatch entries
N decoded opcode IDs
N handler implementation bodies
N raw records in the program container
N records reached by this trace
N dynamic frames
N recovered VM functions under the current definition
N source-level business functions, if proven
```

没有 Trace 也可以从静态程序容器和 Record 长度/元数据规则得到 Record 数量。Trace 只能告诉当前输入实际到达了哪些 Record 和产生了多少动态 Frame。

## 8. 适度恢复

用最终等价命题决定恢复深度：

- 不知道操作数宽度或 PC 规则时，先恢复指令格式。
- 不知道中间值如何影响输出时，恢复局部数据流和消费者。
- 间接跳转、异常或共享 Scope 影响主线时，扩大 CFG、Frame 或调用图。
- 独立实现已从原始输入与 Oracle 精确一致，且未知部分不影响声明范围时，停止为了形式完整扩展分析。

最终不用“还原了多少对象”验收，而用“已声明的原始输入是否能由独立实现得到与受控 iv8 相同的最终输出”验收。
