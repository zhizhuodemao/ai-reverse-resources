# 案例：抖音 JSVMP `a_bogus` 独立精确复现

本文只记录课程中 `bdms_1.0.1.19.js` 的已验证事实。它展示主线如何落地：以受控 iv8 中的原始程序作为 Oracle，结合静态 Bytecode 反编译和动态 Handler Trace，让纯 Python 从声明的原始输入逐字符生成相同 `a_bogus`。

不把本案例的 Record ID、字段布局、算法顺序或阈值当作其他 VMP 的通用结构。

## 目录

1. 样本和目标
2. 受控 Oracle
3. 静态程序容器
4. 动态 Trace
5. Trace 阶段的成果与边界
6. 五个未知点的静态闭合
7. 完整原始输入
8. 从原始输入到 `a_bogus`
9. 独立 Python 实现
10. 精确验收
11. 本案例教训

## 1. 样本和目标

```text
sample          bdms_1.0.1.19.js
source SHA-256  2728891a2506a544b48d591bca6c021886478dbf8197a61862a36d894ebfca51
final field     a_bogus
baseline length 192 characters
baseline hash   78b0663c770f9596d9f8b2366db3f008ddda826f4ffae431363e9233c8b1ad8d
```

最终目标不是恢复作者原变量名，也不是为全部 Record 生成高语义源码。唯一完成命题是：

```text
同一组原始输入
Python a_bogus === 固定 iv8 a_bogus
```

## 2. 受控 Oracle

基线执行固定：

```text
random seed       439041101 / 0x1a2b3c4d
fixed epoch ms    1786003200123
performance start 1000.0
performance step  0.125
```

确定性实验表明：

- 只固定随机源时，最终输出仍然变化；
- 同时固定随机和时间后，连续 3 次输出完全相同。

这个实验证明受控环境是反编译的前提：如果 Oracle 还在漂移，最终差异无法可靠地归因于恢复实现。

## 3. 静态程序容器

当前可审计的正式静态口径是：

```text
Opcode schema entries  77，编号 0..76
string-pool entries    1001
raw VM records         796
```

796 条 Record 直接来自静态恢复的原始 VM 程序容器，不依赖 Trace。每条是当前样本中的四元结构：

```text
bytecode
parameter-binding count
strict-mode flag
exception table
```

已完成：

- 796 条 Record 的全量线性反汇编；
- 单一总反汇编和按 Record 拆分的文件；
- 第一版低语义伪代码；
- 普通 CFG 和不可达代码；
- Opcode 名称、操作数宽度、栈效应和下一 PC 规则。

报告 Handler 数量时不要把“最大 Opcode ID 是 76”说成“只有 76 个 Opcode”。本案例当前的 Schema 是 77 项；如果另外按 JavaScript Handler 实现体数量计数，必须单独声明口径和共用/辅助函数的处理。

## 4. 动态 Trace

matched-request Trace 于固定输入下捕获：

```text
total events                         65,390
handler events                       65,094
frame events                            296
unique records reached                  103
unique opcode kinds reached               61
unique (recordId, PC, opcode)          3,603
dropped events                              0
handler events without after                0
trace internal errors                       0
```

Trace 证明了当前输入的真实动态路径，不证明只有 103 个 Record，也不证明只有 61 种 Opcode。静态容器是 796 条 Record，当前 Trace 只覆盖其中 103 条。

Trace 还确认：

- `record130` 生成最终编码字符串；
- `record107` 执行 `searchParams.append("a_bogus", signature)`；
- 主链包含 SM3、随机化 3→4 打包、Modified RC4 和自定义 6-bit 编码；
- Focus Trace 捕获了五次 SM3、99→132 打包、两次 Modified RC4、header/prefix 和 s3/s4 输入输出。

## 5. Trace 阶段的成果与边界

Trace 阶段先恢复了：

- 加密和编码链；
- 50 字节 core、环境文本、时间尾串和 XOR checksum 的材料布局；
- 变长材料长度 `50 + len(environmentText) + len(timeText) + 1`；
- 原始 JS 现场生成的新密文可被独立解密并语义解析；
- 只接收请求、环境、时间和 seed 的早期完整生成链。

但 Trace 中的基线值仍存在同值歧义和未执行分支，以下五项当时只知道基线值和大致消费位置，不知道全部公式和业务语义：

```text
record149
record699
record277
record697
record150 descriptor branch
```

因此转入 Bytecode、CFG、Scope 和定向原 VM 变体，而不仅继续观察同一基线 Trace。

## 6. 五个未知点的静态闭合

五项都使用同一证据结构：

```text
Bytecode / CFG / Scope 静态恢复
→ 原 VM 定向单变量执行
→ Record 返回值与 50 字节 core 偏移对账
```

28/28 组原 VM 变体全部通过。最终语义是：

| Record | 早期占位名 | 最终语义 | 基线 |
|---:|---|---|---:|
| 149 | `environmentCode` | 当前 VM 生命周期内签名累计调用次数分桶 | `6` |
| 699 | `platformCode` | 运行环境/自动化异常位集 `runtimeRiskBits` | `1` |
| 277 | `trackCode` | 交互行为异常位集 `behaviorBits` | `14` |
| 697 | 五项特征向量 | 四个行为队列变更计数 + 一组环境异常位集 | `[0,0,0,0,1]` |
| 150 | `descriptorFlag` | `window.onwheelx._Ax` own descriptor 的 `writable` 检查 | `3` |

关键纠正：

```text
platformCode     → runtimeRiskBits
trackCode        → behaviorBits
environmentCode  → signatureInvocationBucket
```

这些不是浏览器平台枚举。这个纠正说明中性占位名应保留到输入来源、全分支公式和下游消费者都明确。

### `record149`

`record132` 创建 `record149` 和 `record150`，两者共享计数器。`record150` 开始执行时自增，`record149` 返回四档分桶：

```text
0..139      → 6
140..1283   → 5
1284..10745 → 4
10746+      → 3
```

### `record699`

从固定 bit0 开始，检查原生函数表面/canvas/plugins、Headless/WebDriver、自动化全局、Node/CommonJS、localhost/IP URL、UA/platform 矛盾和核心浏览器对象完整性。

### `record277`

将 Move、ClickStart 和 KeyDown 三个队列的空值、移动速度和按键间隔异常按位聚合。基线三队列为空，得到 `2 | 4 | 8 = 14`。

### `record697`

前四项是 Move、ClickStart、ClickEnd、KeyDown 环形队列变更计数的低字节，不是队列长度或布尔状态。第五项检查 `document.all`、Error stack、screen 对象形状、嵌入式浏览器桥、storage/quota/私密模式、frame 身份和 DevTools 窗口差。

### `record150`

```javascript
if (!window.onwheelx || !window.onwheelx._Ax) return 11;
descriptor = Object.getOwnPropertyDescriptor(window.onwheelx, "_Ax");
return descriptor?.writable === false ? 3 : 12;
```

基线 iv8 中 `_Ax` 为 truthy，且 own descriptor 的 `writable === false`，所以返回 `3`。这是对特定宿主表面/完整性哨兵的检查，不是通用业务属性。

## 7. 完整原始输入

纯 Python 公开入口允许接收：

```text
请求      query、body
环境      window/document/navigator/screen/location 等原始宿主事实
行为      Move、ClickStart、ClickEnd、KeyDown 原始队列/事件
时间      Date.now/new Date/performance 的固定序列
随机源  Math.random 初始状态和调用序列
配置      pageId、aid、track.mode、SDK 版本
初始状态 签名共享计数器等 VM 生命周期输入
```

公开入口禁止接收：

```text
runtimeRiskBits
behaviorBits
featureVector
descriptorFlag
invocationBucket
environmentBytes
timeBytes
header8
prefix4
checksum
material
```

这些都必须由 Python 从原始输入自己计算。

## 8. 从原始输入到 `a_bogus`

已恢复的当前样本主线是：

```text
原始请求、环境、行为、时间、随机源、配置
→ runtimeRiskBits / behaviorBits / featureVector
→ Query / Body / UA 三组摘要
→ environmentBytes / timeBytes
→ header8
→ 50 字节 core
→ checksum
→ material = core || environmentBytes || timeBytes || checksum
→ prefix4
→ record148 随机打包
→ Modified RC4(header8 || packedMaterial)
→ prefix4 || ciphertext
→ s4
→ a_bogus
```

当前基线 `material` 长度为 99，但 99 不是协议定长。已验证 97、98、99 字节材料和 188/192 字符最终输出。

## 9. 独立 Python 实现

独立实现：

- 不加载原始 `bdms` JavaScript；
- 不依赖 iv8；
- 入口只接收 `FixedIv8RawInput`；
- 从原始环境、行为和共享状态计算五个早期未知字段；
- 自行计算摘要、core、材料、随机序列、header/prefix、Modified RC4 和 s4；
- 拒绝在环境、行为或配置中传入预计算协议字段。

原始课程工作区曾按以下路径组织实现与证据。这些路径仅用于说明案例来源，不随插件分发，也不是 skill 的运行依赖：

```text
课程案例demo/douyin-jsvmp/vm-analysis/trace/recovered/
课程案例demo/douyin-jsvmp/vm-analysis/trace/derived/fixed-iv8-raw-input.json
课程案例demo/douyin-jsvmp/vm-analysis/trace/derived/full-generation-l3.json
课程案例demo/douyin-jsvmp/vm-analysis/decompiler/
```

## 10. 精确验收

完成证据：

```text
45 组材料单变量差分
28/28 组原 VM 定向语义变体
8/8 组同 RawInput 的 Python 与原 JS + iv8 端到端对账
```

8/8 用例中以下项目全部一致：

```text
探针字段
material
header8
prefix4
随机调用序列
最终 a_bogus
```

固定基线最终输出为 192 字符，SHA-256 为：

```text
78b0663c770f9596d9f8b2366db3f008ddda826f4ffae431363e9233c8b1ad8d
```

该结论的范围是固定 iv8 原始输入合同和已列变体。不要扩大为“支持任意真实浏览器”。

## 11. 本案例教训

可迁移的是判断原则，不是样本工作流：

1. 先建立可重复 Oracle，否则差异无法归因。
2. Trace 快速恢复了当前路径的算法和材料，但不能单独消除基线同值歧义和未执行分支。
3. 静态 Bytecode/CFG/Scope 补全公式，原 VM 单变量实验反驳或验证语义。
4. 全量反汇编和 CFG 在该案例中是有价值的基础，但完整高语义全库 CFG 不是最终验收前提。
5. 中间值对账帮助定位，最终仍以同 `RawInput` 下的精确输出一致验收。
6. 删除公开入口中的预计算辅助字段，才使“从原始输入恢复完整映射”成为真命题。
7. 完成范围由可验证命题决定，不由 Handler、Record 或 CFG 的形式完整度决定。

不可迁移的是：

- 77 个 Opcode Schema 和 796 条 Record；
- `record149/699/277/697/150` 的 ID 与语义；
- 50 字节 core 布局；
- SM3、Modified RC4、s4 和当前随机打包顺序；
- `window.onwheelx._Ax` 等当前版本哨兵；
- 基线输出长度、Hash 和所有阈值。

分析新 VMP 时，重用“受控 Oracle + 静态全分支 + 动态实例 + 独立精确复现”的证据模型，不重用本案例的字段和顺序。
