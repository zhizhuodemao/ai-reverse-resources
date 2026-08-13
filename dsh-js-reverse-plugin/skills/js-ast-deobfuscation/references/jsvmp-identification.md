# JSVMP 识别与反误判

本文只回答两个问题：

1. 什么源码证据足以确认存在 JSVMP；
2. AST 解混淆应该清理到哪里并交接。

它不解释 Opcode，不跟踪 PC、值栈或帧栈，也不反编译字节码。

## 目录

1. [判定结论](#1-判定结论)
2. [四道硬门](#2-四道硬门)
3. [结论等级](#3-结论等级)
4. [本地真实样本](#4-本地真实样本)
5. [常见误判](#5-常见误判)
6. [静态与动态边界](#6-静态与动态边界)
7. [记录与交接](#7-记录与交接)

## 1. 判定结论

JSVMP 不是“大数字数组”“`while + switch`”或“变量名像 `pc`”。

只有同一条数据流形成以下闭环，才能确认代码中存在自定义 JavaScript 指令解释器：

```text
自定义程序数据
  → 按指令位置取出 opcode 和 operands
  → dispatcher 选择可复用的指令语义
  → handler 修改持续存在的虚拟执行状态
  → 跳转、调用、返回或异常处理决定下一条指令
```

再证明目标公开 API、业务返回值或业务副作用依赖这条闭环，才确认“目标业务被 JSVMP 虚拟化”。

## 2. 四道硬门

以下 A～D 必须同时成立，而且必须属于同一个执行闭环。

### A. 程序被表示为数据

找到数组、字符串、Buffer 或结构化记录，并证明它不是普通配置或资源，而是提供：

- opcode；
- operands；
- 跳转目标；
- 常量或名称索引。

只看到高熵数组或二进制数据，不算通过。

### B. 存在重复取指和分派

证明 dispatcher 的选择值直接或间接来自程序数据，并在一次执行中反复取得“下一条指令”。

分派形式可以是比较树、`switch`、handler table、函数线程或递归 continuation；不要求固定语法。

### C. 存在持续的虚拟执行状态

除指令位置外，至少还要看到一种跨指令保存的状态：

- operand/value stack；
- register 或 accumulator；
- virtual locals、scope 或 environment；
- virtual call frames；
- completion、return 或 exception state。

普通模块缓存、parser 输入游标或业务状态字段不算 VM 执行状态。

### D. handler 实现抽象的 JS 语义和虚拟控制流

至少证明：

- 一类数据或计算语义，例如 load、property access、call、arithmetic；
- 一类虚拟控制语义，例如 jump、branch、call、return、throw。

handler 应是可被不同指令位置复用的抽象操作。若每个分支直接写着某个原函数的业务基本块，更像控制流平坦化。

## 3. 结论等级

使用结构门，不使用“出现几个特征”的打分法。

```text
CONFIRMED_VM_STRUCTURE
  A ∧ B ∧ C ∧ D

CONFIRMED_BUSINESS_JSVMP
  A ∧ B ∧ C ∧ D
  ＋ 公开 API、目标业务路径或可观察结果确实经过该 VM

PROBABLE_JSVMP
  已形成大部分闭环，但关键来源或消费者仍不可见；
  同时没有打包器、parser、普通状态机等更直接解释

INSUFFICIENT_VM_EVIDENCE
  只有数组、dispatcher、状态变量或其他孤立表象

NOT_JSVMP
  已证明结构属于模块加载、数据解析、packer、Wasm 或其他机制
```

不知道时保留 `Unknown`。不要为了给出确定答案而把 `PROBABLE` 升级成 `CONFIRMED`。

## 4. 本地真实样本

以下短片段来自一个真实本地样本的派生分析视图。只省略无关分支，并给局部变量补充说明性中性名；判定依赖数据流，不依赖名称。

### 4.1 程序记录进入解释器

```js
vmRecords = [
  [[63, 1, 54, 0, 8, /* ... */, 76], 0, true, []],
  [[73, 0, 69, 1, /* ... */, 76], 1, true, []]
];

function executeVmEntry(entryId, thisArg, args, hostSlots) {
  return executeVmRecord(vmRecords[entryId], thisArg, args, hostSlots);
}
```

`vmRecords` 单独出现时只是候选。`entryId → vmRecords[entryId] → executeVmRecord` 证明记录被当作程序执行，A 通过。

### 4.2 初始化独立执行状态

```js
var instructionData,
  strictMode,
  exceptionTable,
  scopeChain,
  instructionPointer,
  completionType,
  completionValue,
  stackPointer = -1,
  valueStack = [],
  callFrames = [];

instructionData = vmRecord[0];
exceptionTable = vmRecord[3];
scopeChain = [hostSlots, argumentsObject];
instructionPointer = 0;
```

这里同时存在指令位置、值栈、调用帧、作用域和完成状态，C 通过。

### 4.3 从程序数据取指并持续分派

```js
function dispatchInstructions() {
  for (;;) {
    var opcode = instructionData[instructionPointer++];
    if (opcode < 38) {
      // ...
    } else {
      // ...
    }
  }
}
```

嵌套比较树与 `switch` 等价：选择值来自 `instructionData[instructionPointer++]`，B 通过。

### 4.4 handler 操作虚拟状态

```js
var argc = instructionData[instructionPointer++];
stackPointer -= argc;
var args = valueStack.slice(stackPointer + 1, stackPointer + argc + 1);
var callee = valueStack[stackPointer--];
var receiver = valueStack[stackPointer--];

if (vmFunctionMetadataByFunction.has(callee)) {
  callFrames.push([
    instructionData,
    scopeChain,
    instructionPointer,
    completionType,
    completionValue
  ]);
  initializeVmFrame(/* virtual callee */);
} else {
  valueStack[++stackPointer] = callee.apply(receiver, args);
}
```

同一个 dispatcher 还会修改 `instructionPointer` 做条件跳转，并用 `completionType`、`completionValue` 和 `callFrames.pop()` 处理返回与异常。它实现的是可复用的调用、跳转、返回和异常语义，不是单个业务基本块，D 通过。

### 4.5 公开 API 与 VM 相连

```js
e.d(n, {
  init: function () {
    return publicInit;
  }
});

executeVmEntry(0, void 0, arguments, {
  get 19() {
    return publicInit;
  },
  set 19(value) {
    publicInit = value;
  }
});

window.bdms = n;
```

这段代码先证明 `entry 0 → host slot 19 → publicInit → window.bdms.init` 的宿主桥。要证明 VM 确实向桥中写入函数，还要继续读取记录 0 和对应 handler。

记录 0 含有连续数据：

```js
63, 128, 54, 1, 19
```

解释器中，与这段数据相连的两个 handler 效果是：

```js
valueStack[++stackPointer] = createVmFunction(
  instructionData[instructionPointer++],
  scopeChain
);

var depth = instructionData[instructionPointer++];
var slot = instructionData[instructionPointer++];
var target = scopeChain;
while (depth > 0) {
  target = target[0];
  --depth;
}
target[slot] = valueStack[stackPointer--];
```

由于虚拟帧初始化为 `scopeChain = [hostSlots, argumentsObject]`，这段数据会创建 `vmRecords[128]` 对应的 VM 函数，再写入 `hostSlots[19]`，触发 setter 把它赋给 `publicInit`。

因此这个样本不只是“含有一个解释器”，而是可以静态确认公开的 `window.bdms.init` 由 VM 函数支撑。这里只识别了证明宿主边界所需的 handler 效果，没有恢复完整 Opcode 表或记录 128 的业务算法。

完整证明链是：

```text
vmRecords[entryId]
  → executeVmRecord
  → instructionData / instructionPointer / valueStack / callFrames
  → instructionData[instructionPointer++]
  → dispatcher handlers
  → return / exception / host slots
  → public init
```

确认这条边界不需要解释任意一个 Opcode 的业务含义。

## 5. 常见误判

### 数字模块 ID

```js
6696: function (module, exports, require) {
  var isCallable = require(5437);
  module.exports = function (value) {
    if (isCallable(value)) return value;
    throw TypeError("not a function");
  };
}
```

这里 `6696` 是模块地址，函数体仍由 JavaScript 引擎直接执行。没有程序流、取指指针、虚拟状态和指令闭环，所以不是 JSVMP。

同一个文件可以同时包含打包器和 JSVMP。本地样本就是外层模块加载器包着内层 VM；不要把两类结论互斥化。

### 其他弱证据

| 表象 | 默认分类 | 决定性缺口 |
|---|---|---|
| 大数字数组、Base64、TypedArray | 数据候选 | 未证明数据被当作程序 |
| `while + switch(state)` | 状态机或控制流平坦化候选 | selector 未必来自 `program[pc]` |
| 大量数字 `case` | dispatcher 候选 | 未证明 operands、VM state 和重复取指 |
| Webpack 模块表 | 打包器 | 模块 ID 不是 opcode |
| parser/regex/template VM | 领域解释器 | 指令语义未承载目标 JS 业务 |
| 解码后交给 `eval`/`Function` | packer 或动态载荷 | 最终由原生 JS 引擎执行 |
| `WebAssembly.instantiate` | Wasm | JS 中没有自定义取指解释闭环 |
| 名为 `pc`、`stack`、`opcode` 的变量 | 命名线索 | 名称不能替代数据流证据 |

Parser 确实可能使用 VM。此时应写“确认存在 parser VM”，不能自动写成“业务使用 JSVMP”。继续比较 handler 是 `shift/reduce/token`，还是 `load/property/call/branch/return`。

## 6. 静态与动态边界

本地样本的 A～D 和公开入口关联都在源码中形成闭环，因此静态即可确认，不需要先补环境或运行程序。

只有下列关键事实在源码中不可见时，才考虑最小动态边界取证：

- 指令数据在运行时才解密或下载；
- entry ID 或公开入口只在特定生命周期确定；
- dispatcher 或 handler 在运行时生成；
- 只能通过一次公开调用确认目标路径是否进入候选 VM。

动态取证只观察公开调用、VM 入口、entry/record 身份和外部结果。不要在 AST Skill 中记录 Opcode trace、PC trace、值栈或帧栈；若确认结论必须依赖这些内部证据，保留 `PROBABLE_JSVMP` 并交接 VM 分析。

## 7. 记录与交接

在 `ANALYSIS.md` 中记录：

```text
verdict:
  CONFIRMED_BUSINESS_JSVMP |
  CONFIRMED_VM_STRUCTURE |
  PROBABLE_JSVMP |
  INSUFFICIENT_VM_EVIDENCE |
  NOT_JSVMP

A_program_as_data: pass | fail | unknown
B_fetch_dispatch: pass | fail | unknown
C_virtual_state: pass | fail | unknown
D_instruction_semantics: pass | fail | unknown
business_or_public_path: pass | fail | unknown
connected_dataflow:
source_anchors:
alternative_explanations:
counterevidence:
unknowns:
```

确认后，AST 阶段可以：

- 恢复阻碍边界识别的外层字符串；
- 用 `vmRecords`、`executeVmEntry`、`entry_0`、`slot_19` 等中性名称建立坐标；
- 建立 entry、record、host binding、slot、public API 和原始位置映射；
- 清理解释器外围、打包器和宿主桥中确有收益的隐藏。

一旦下一问题变成“某个 Opcode 做什么”“某段字节码是什么算法”或“如何采集 PC/栈轨迹”，停止 AST 解混淆并交接。
