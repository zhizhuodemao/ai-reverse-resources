# 受控 iv8 Oracle 与精确等价

本文定义 VMP 语义恢复中“参考实现”、“原始输入”和“正确”的可量化含义。主线始终是：让独立实现从与受控 iv8 完全相同的原始输入出发，得到精确相同的最终输出。

## 目录

1. Oracle 命题
2. 为什么使用 iv8
3. RawInput 合同
4. 受控性维度
5. 原始值与派生值
6. Oracle 完整性
7. 精确比较
8. 受控变体
9. 中间对账
10. 服务器判决
11. 完成声明

## 1. Oracle 命题

把未修改的原始程序在声明的受控 iv8 条件下的输出定义为 Oracle：

```text
O(x) = OriginalVMP_in_Controlled_iv8(x)
R(x) = IndependentRecoveredImplementation(x)
```

对某个固定输入 `x0` 的基线命题是：

```text
R(x0) === O(x0)
```

对一组受控变体 `X` 的扩展命题是：

```text
对每个 x in X，R(x) === O(x)
```

静态全分支恢复可以继续扩大可信范围，但不要在没有证据时声称对无限输入空间完全等价。

## 2. 为什么使用 iv8

把 iv8 视为受控参考执行环境，而不是分析目标本身。

```text
纯 Node
  优点：轻量、可控、方便断点和脚本化
  缺点：浏览器对象形状和原生语义需要大量手工补齐

真实浏览器
  优点：DOM、渲染、网络和对象形状更真实
  缺点：Cookie、LocalStorage、缓存、网络、时间、调度和页面生命周期难以完全固定

iv8
  优点：比纯 Node 更接近浏览器形状，比真实浏览器轻量且易于固定输入和运行状态
```

目标依赖布局、字体、GPU、真实网络栈或浏览器内部状态时，使用可定制浏览器或受控 CDP 环境。保留同一 Oracle 原则：先声明可控状态，再比较独立实现。

安装、版本、iv8 API、补环境、网络桥接和 event loop 操作使用 `iv8-env-runtime`，不在本 reference 重复。

## 3. RawInput 合同

在分析算法之前，先声明独立实现允许接收的输入层。通用类别是：

```text
request        URL、query、body、method、headers 中确实被读取的原始值
environment    window/document/navigator/screen/location 等宿主可观测事实
behavior       原始事件、事件序列或已声明的初始队列状态
time           Date/performance/timer 的初始状态和调用序列
randomness     Math.random/crypto 等随机源的初始状态与调用序列
configuration  SDK 版本、aid、page id、mode 等原始配置
initialState   Cookie、storage、cache、共享计数器、队列和初始化阶段
network        程序确实消费的响应字节、头和返回顺序
```

不要为了统一 Schema 强制每个样本都具有全部字段。记录当前程序真正读取的输入和没有读取的候选值。

对可变序列同时记录值和消费顺序。仅固定随机 seed 不代表随机流一致；调用次数或时序不同也会改变结果。

## 4. 受控性维度

对以下影响源作出显式声明：

| 维度 | 需要记录的事实 |
|---|---|
| 原始程序 | 路径、SHA-256、是否为原始文件或派生执行目标 |
| 运行时 | iv8/Python/V8 版本、平台、关键选项 |
| 环境 | 可观测属性、descriptor、prototype、对象身份和原生函数表面 |
| 时间 | epoch、performance 起点/步长、timer 执行顺序 |
| 随机 | 算法、seed、初始状态、每次调用序号 |
| 存储 | Cookie、LocalStorage、SessionStorage、IndexedDB、quota 的初始值 |
| 网络 | 请求匹配、响应内容、注入时机、错误和重试 |
| 行为 | 事件内容、时间戳、注入顺序、去抖/采样前后的边界 |
| 生命周期 | 初始化次数、签名调用次数、event loop 排空点和异步共享状态 |
| 观测 | 断点、Hook、Trace、wrapper、补丁和派生插桩文件 |

这些条件不是形式文档，而是 `O(x)` 定义的一部分。未记录的可变状态可能使同一输入看似不确定。

## 5. 原始值与派生值

使用一个简单问题判断字段边界：

> 这个值是由宿主、用户、配置或初始状态直接提供，还是原 VM 已经根据这些事实计算得出？

原始值示例：

```text
navigator.userAgent
screen.width
mousemove event list
Date.now sequence
Math.random initial state
SDK aid
signature invocation count before this call
```

派生值示例：

```text
UA digest
behavior bit field
environment feature vector
50-byte core
checksum
packed material
RC4 ciphertext
final encoded token
```

派生值可以作为调试断言和中间对账点，但不能作为对外公开的恢复实现输入。

如果一个值是原程序在更早生命周期生成并持久化的，明确选择它是本次调用的 `initialState` 还是必须恢复的上游计算。该选择决定完成声明的起点，不能隐藏。

## 6. Oracle 完整性

用以下证据确认 Oracle 可作为参考：

1. 固定原始文件 Hash，保留原始入口。
2. 分开原始运行目标和 Trace/插桩派生目标。
3. 在同一 `RawInput` 和同一运行条件下至少重复执行，确认最终输出稳定。
4. 输出不稳定时，按时间、随机、存储、网络、异步、共享计数器和运行时补丁查找可变量。
5. 保存无 Trace 与有 Trace 的 A/B，确认观测没有改变最终输出或明确降低证据等级。

只固定一个可变源后输出仍变化，是还有其他状态未受控的证据，不是算法无法恢复的证据。

## 7. 精确比较

先按实际协议定义比较单位：

- 字符串协议：声明字符编码，再比较编码后字节；
- 原始密文：直接比较字节；
- JSON 或对象：只在协议不定义文本序列化时才比较解析结构；如果字符顺序就是签名输入，保留原始文本。

报告：

```text
raw input hash
source/bytecode hash
oracle length and hash
recovered length and hash
exact equality
first differing byte offset, when any
comparison encoding or raw-byte mode
```

使用 `scripts/verify-equivalence.py` 完成这个机械事实。不让比较脚本删除空白、规范化 Unicode、解码 Base64 或改写换行，除非协议和用户明确把这些转换定义为比较前处理。

## 8. 受控变体

固定基线是主要锚点。当需要确认某个原始字段、分支或中间语义时，设计只改变一个因素的变体：

```text
x0 = baseline raw input
x1 = x0 with exactly one declared change
```

同时执行 Oracle 和独立实现：

```text
O(x0), R(x0)
O(x1), R(x1)
```

检查：

- 变体是否真的只改变一个宿主事实；
- 原 VM 是否实际读取该变化；
- 两套实现的最终输出是否继续精确一致；
- 预期中间字段和下游消费者是否一起改变；
- 时间或随机调用次数是否因分支改变。

变体不是为了堆数量。优先构造能区分竞争性解释、触发关键分支或验证边界的用例。

## 9. 中间对账

最终输出是验收标准，中间值是定位工具。当 `R(x) !== O(x)` 时，沿共同坐标对账：

```text
raw input read
→ probe/feature result
→ digest or material
→ packing/header/checksum
→ cipher state or ciphertext
→ final encoding
```

寻找首个分歧，不只比较最后的密文。首个分歧之后的大量差异通常是下游扩散，不代表多个独立错误。

中间对账通过后仍要比较最终输出；最终输出通过后仍要检查独立实现没有从外部读取这些中间值。

## 10. 服务器判决

区分两个问题：

```text
服务器接受：
  证明请求在当前 Cookie、IP、时间窗口、参数和服务端策略下可用

本地精确等价：
  证明独立实现复现了受控原 VM 的计算结果
```

服务器成功可以是产品或补环境任务的最终验收，但不能替代 VMP 语义恢复的对照实验。服务器可能容忍多个等价表示、忽略某些字段，也可能因非算法因素拒绝正确输出。

## 11. 完成声明

声明完成时写清：

```text
Oracle source and hash
controlled runtime and mutable-state contract
RawInput schema and concrete baseline hash
independent implementation entry point
forbidden precomputed fields absent from its public input
oracle/recovered output lengths and hashes
exact comparison result
tested variants and static coverage
known untested or out-of-scope paths
```

允许作出范围清晰的完成声明：

> 固定 iv8 基线和已列出变体已完成从原始输入到最终输出的独立精确复现；未覆盖的真实浏览器、异常分支或其他生命周期不在本声明范围。

不要因为仍有与该范围无关的 Handler、Record 或 CFG 未高语义化而拒绝收束；也不要因为一个基线成功而隐藏未验证范围。
