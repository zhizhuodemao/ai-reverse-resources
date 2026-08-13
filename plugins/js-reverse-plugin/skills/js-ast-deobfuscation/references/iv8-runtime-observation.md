# iv8 最小动态取证

本文只解决一个问题：

> 当一次 AST 解混淆缺少某个运行事实时，怎样用 iv8 在不修改原始 JavaScript 文件的前提下取得最小充分证据，并把证据带回静态分析主线。

本文不是 iv8 安装手册、完整补环境教程、网络爬虫模板或 token 运行框架。需要系统补环境、真实网络桥接或完整运行验收时，推荐交接专门的 iv8 运行环境 Skill。

## 目录

1. [读取时机](#1-读取时机)
2. [证据任务先于工具](#2-证据任务先于工具)
3. [原始文件与运行产物](#3-原始文件与运行产物)
4. [版本门控与最小冒烟](#4-版本门控与最小冒烟)
5. [L0～L4 观测阶梯](#5-l0l4-观测阶梯)
6. [L0：引擎层旁路监控](#6-l0引擎层旁路监控)
7. [捕获 fd1 与 fd2](#7-捕获-fd1-与-fd2)
8. [netLog 的准确边界](#8-netlog-的准确边界)
9. [L1：DevTools 与 API watch](#9-l1devtools-与-api-watch)
10. [L2：独立 harness 与 trigger](#10-l2独立-harness-与-trigger)
11. [L3：独立 probe](#11-l3独立-probe)
12. [L4：派生副本插桩](#12-l4派生副本插桩)
13. [runtime patched 与 A/B](#13-runtime-patched-与-ab)
14. [事件循环与异步结果](#14-事件循环与异步结果)
15. [动态证据映射回 AST](#15-动态证据映射回-ast)
16. [证据记录格式](#16-证据记录格式)
17. [分流与返回主线](#17-分流与返回主线)
18. [禁止事项](#18-禁止事项)

## 1. 读取时机

只在以下条件同时满足时读取并使用本文：

- 当前候选已被分类为 `dynamic` 或 `hybrid`。
- 静态分析已经定位结构，但缺少明确的运行事实。
- 缺失事实依赖浏览器 API、初始化顺序、闭包状态、实际分支、事件循环或运行期属性。

可以在向用户提交决策卡之前读取本文，用它设计最小实验、说明风险和执行范围。读取 reference 不需要批准；真正创建或执行 iv8 harness、trigger、probe 或插桩副本前，必须取得用户对本次动态取证范围的批准。

以下情况不应使用 iv8：

- AST、作用域、binding、引用关系或确定性语义已经足够证明结论。
- decoder 可以作为纯函数在更小的受控环境中执行。
- 只是为了“看看运行起来会发生什么”，尚未定义证据问题。
- 已经进入 VM Opcode、PC、值栈、字节码或虚拟控制流。
- 必须依赖真实字体、布局、音频渲染、浏览器网络栈或现有页面会话。

iv8 是证据提供者，不是解混淆主线。

## 2. 证据任务先于工具

开始前先写清：

```text
当前问题：
静态已经证明：
唯一或有限的事实缺口：
为什么必须运行：
最小执行入口：
需要观察的值、顺序、异常或调用：
成功条件：
显式不证明：
```

不接受以下模糊目标：

```text
跑一下看看。
把日志全打出来。
动态分析整个文件。
看看 iv8 能不能解。
```

动态取证应回答有限问题，例如：

```text
固定输入 X 下，decoder D(17) 的返回值是什么？
public init 调用后，哪个宿主 API 被替换？
请求触发时，最终 URL 新增了哪个参数？
闭包变量 K 在调用 decoder 前的实际值是什么？
```

一次运行只能证明声明输入、环境和覆盖路径下的事实，不能自动推广到全部输入或全部分支。

## 3. 原始文件与运行产物

至少区分以下角色：

```text
target.original.js
  固定 hash 的原始运行目标；只读，不格式化，不插日志。

target.formatted.js
  Prettier 生成的阅读副本；只用于阅读和建立源码坐标。

analysis.current.js
  当前 AST 分析视图；可以不可执行，不作为原始行为证据。

harness.py
  创建 Context、加载目标、捕获日志和保存证据。

trigger.js
  独立触发文件；只调用本次批准的入口。

probe.js
  独立运行时探针；只有 L3 使用。

target.instrumented.js
  独立插桩副本；只有 L4 使用。

runtime.raw.log
  原始引擎或调试日志。

runtime-evidence.json
  结构化证据、环境、覆盖范围和源码映射。
```

每次运行前重新计算并核对 `target.original.js` 的 hash。

动态执行默认加载原始文件：

```python
ctx.eval(original_source, name="target.original.js")
```

不要为了方便断点而执行格式化副本；格式变化可能触发 `toString()`、校验和或文件 hash 检测。

## 4. 版本门控与最小冒烟

iv8 是编译扩展，API 和已知 stub 可能随版本变化。不要凭记忆应用补丁。

每次新工作区至少记录：

```text
操作系统与架构
Python 版本
iv8 实际版本
import 是否成功
JSContext 冒烟结果
本次使用的 API
```

最小冒烟：

```python
import platform
import sys

import iv8

version = getattr(iv8, "__version__", "<unknown>")
print("platform:", platform.platform())
print("python:", sys.version)
print("iv8:", version)

with iv8.JSContext() as ctx:
    assert ctx.eval("1 + 1") == 2
    assert ctx.eval("navigator.webdriver") is False
```

规则：

- 版本号以实际 import 后读取的值为准。
- 冒烟失败时停止，不猜测 API。
- 先复现当前版本的实际行为，再决定是否需要 workaround。
- 已知问题在新版修复后，不得继续注入旧补丁。
- 本文使用的接口曾在 iv8 Community Edition 0.1.3 契约上核验，但不能据此假定所有版本完全相同。
- import、平台 wheel 或 API 契约不成立时，标记当前候选 `BLOCKED_CURRENT`，或交接专门的 iv8 运行环境 Skill。

本文只依赖以下已核验接口：

```text
iv8.JSContext(...)
ctx.eval(...)
ctx.add_resource(...)
ctx.with_devtools(...)
ctx.expose(...)
iv8.JSContext.get_defaults()
window.__iv8__.eventLoop.*
window.__iv8__.page.load(...)
window.__iv8__.netLog.entries
window.__iv8__.wrapNative(...)
```

不要臆造其他方法。

## 5. L0～L4 观测阶梯

优先选择能回答当前问题的最低级别。

| 等级 | 方法 | 原始文件字节 | 运行时对象 | 默认 `runtime patched` | 主要用途 |
| --- | --- | --- | --- | --- | --- |
| L0 | iv8 引擎层 debug 监控、netLog | 不变 | 不主动包装目标对象 | `false` | API 读写、调用、反射、缺失探测、请求结果 |
| L1 | DevTools、行断点、API watch、scope | 不变 | 不主动包装目标对象 | `false` | 局部变量、调用栈、实际分支 |
| L2 | 独立 harness 与 trigger | 不变 | 只按公开接口触发 | `false` | 初始化顺序、公开入口、参数和最终产物 |
| L3 | 独立 probe、wrapper、getter/setter、`expose` | 不变 | 已改变 | `true` | 公开边界参数、返回、异常和写入 |
| L4 | 独立运行插桩副本 | 原始文件不变；运行副本已改 | 已改变 | `true` | 前四级无法取得的内部值 |

注意：

- “原始文件未修改”不等于“运行时无影响”。
- `mode="debug"`、断点和日志仍有时间与暂停开销。
- `wrapNative` 只能降低 wrapper 的可观察差异，不能证明等价。
- iv8 文档将 `window.__iv8__` 设计为目标侧不可检测工具对象；证据报告仍不应把任何调试平面宣称为绝对无影响。

## 6. L0：引擎层旁路监控

`mode="debug"` 可记录：

- 浏览器 API 属性读取 `getter`。
- 属性写入 `setter`。
- 方法或构造调用 `call`。
- `typeof`、`in` 等存在性查询 `query`。
- `Object.keys`、descriptor、`Reflect.*`、`Function.prototype.toString`、JSON 等反射路径。
- 疑似缺失 API。

高频 Math、JSON、Array、TypedArray 等默认可能被静音。只有当前问题确实需要时才调整 `ignore_apis`，不要无边界放大日志。

最小骨架：

```python
import hashlib
from pathlib import Path

import iv8

target_path = Path("target.original.js")
target_bytes = target_path.read_bytes()
target_hash = hashlib.sha256(target_bytes).hexdigest()
target_source = target_bytes.decode("utf-8")
trigger_source = Path("trigger.js").read_text(encoding="utf-8")

with iv8.JSContext(mode="debug", environment={}) as ctx:
    ctx.eval(target_source, name="target.original.js")
    ctx.eval(trigger_source, name="trigger.js")
    net_entries = ctx.eval(
        "window.__iv8__.netLog.entries",
        to_py=True,
    )

print("target sha256:", target_hash)
```

`environment={}` 只是示例。只有目标实际依赖且本次实验已经声明的画像字段才应配置。

对“疑似缺失 API”不要直接补：

1. 先判断它是否只是反自动化陷阱。
2. 在真实 Chromium 中本来就应为 `undefined` 的对象必须保持缺失。
3. 只有确认真实浏览器存在、并且当前事实缺口确实依赖它时，才进入单独的环境修补任务。

## 7. 捕获 fd1 与 fd2

iv8 的 C++ debug 日志直接写进程的 stdout/stderr 文件描述符。Python 的 `contextlib.redirect_stdout()` 不能保证捕获这些日志。

fd1/fd2 是进程级资源。优先让每次 iv8 harness 在独立子进程中运行，并为每次运行创建唯一 `run_id` 目录；这样不会吞并主 Agent 或其他并发任务的输出。

只有确认当前进程单线程、没有其他 stdout/stderr 写入者时，才使用下面的进程内重定向。它使用进程内锁拒绝嵌套捕获，用 `O_EXCL` 拒绝覆盖既有证据，并始终在 `finally` 中恢复：

```python
import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path


_NATIVE_LOG_LOCK = threading.Lock()


@contextmanager
def capture_native_log(log_path):
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if not _NATIVE_LOG_LOCK.acquire(blocking=False):
        raise RuntimeError("native fd capture is already active in this process")

    saved_out = -1
    saved_err = -1
    log_fd = -1
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_CLOEXEC", 0)
        log_fd = os.open(str(log_path), flags, 0o644)

        sys.stdout.flush()
        sys.stderr.flush()
        saved_out = os.dup(1)
        saved_err = os.dup(2)
        os.dup2(log_fd, 1)
        os.dup2(log_fd, 2)
        os.close(log_fd)
        log_fd = -1
        yield
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        if saved_out >= 0:
            os.dup2(saved_out, 1)
            os.close(saved_out)
        if saved_err >= 0:
            os.dup2(saved_err, 2)
            os.close(saved_err)
        if log_fd >= 0:
            os.close(log_fd)
        _NATIVE_LOG_LOCK.release()
```

使用：

```python
from datetime import datetime, timezone
from pathlib import Path
import secrets


run_id = (
    datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    + "-"
    + secrets.token_hex(4)
)
run_dir = Path("evidence") / run_id
run_dir.mkdir(parents=True, exist_ok=False)

with capture_native_log(run_dir / "runtime.raw.log"):
    with iv8.JSContext(mode="debug", environment=environment) as ctx:
        ctx.eval(original_source, name="target.original.js")
        ctx.eval(trigger_source, name="trigger.js")
```

若目标日志已经存在，让本次运行失败，不得改回 `O_TRUNC`。保留原始日志，再生成分类摘要；不要只保留正则解析后的统计。

进程内锁只能协调调用同一 helper 的代码，不能阻止其他线程直接写 fd1/fd2。因此有并发、长生命周期服务或不受控库线程时，独立子进程是硬边界，不使用进程内重定向。

常用分类可以包括：

```text
getter
setter
call
query
reflection
suspected missing API
```

日志格式属于版本相关实现细节。解析器匹配失败时保留原始日志并停止分类推断，不要把“没有解析到”写成“目标没有访问”。

## 8. netLog 的准确边界

读取：

```python
entries = ctx.eval(
    "window.__iv8__.netLog.entries",
    to_py=True,
)
```

`netLog` 可以回答：

- 目标是否发起 XHR、fetch 或导航。
- 请求方法和最终 URL。
- 拦截式 SDK 是否在 URL 上追加签名参数。
- 某个 trigger 是否命中了网络 Hook。

它不能证明：

- 请求已经通过真实 HTTP/HTTPS 发送。
- 服务端已经接受该请求。
- TLS、代理、Cookie 池或真实浏览器网络栈与线上一致。

iv8 Community Edition 的 XHR、fetch 和外部资源默认匹配离线 resource bundle，不直接发送真实网络请求。

因此：

- 只观察签名后的 URL 或请求描述时，读取 `netLog` 即可。
- 需要响应时，必须单独声明 Python 真请求、`ctx.add_resource()` 和事件循环推进。
- 真请求需要额外用户授权，不属于默认 AST 动态取证。
- 完整网络桥接应交接专门运行环境流程，不在本文展开。

## 9. L1：DevTools 与 API watch

需要局部变量、闭包状态、调用栈或实际分支时，使用外部 DevTools：

```python
with (
    iv8.JSContext(mode="debug", environment=environment)
    .with_devtools(
        port=9229,
        watch_apis=[
            "navigator.userAgent",
            "document.cookie",
        ],
        enable_console=False,
    )
) as ctx:
    ctx.eval(original_source, name="target.original.js")
    ctx.eval(trigger_source, name="trigger.js")
```

规则：

- 优先在命名的原始脚本上设置外部行断点。
- `watch_apis` 只放与当前证据问题相关的 API。
- 记录实际命中的断点、调用栈、scope、输入和路径。
- 修改变量会改变运行事实；一旦修改，标记 `runtime patched: true`。
- 原生 `debugger;` 在 iv8 中被禁用，不会触发断点。
- iv8 提供 `vdebugger;`，但为了保持原始文件不变，只能把它放在独立 trigger/probe 中。
- 关闭标准 console 上报后，可在独立 probe 中使用 `vconsole.log()`；它只进入 DevTools 通道。

外部断点会暂停执行，因此 `runtime patched: false` 只表示未改运行时对象，不表示没有调试影响。

## 10. L2：独立 harness 与 trigger

很多目标不是“调用一个 sign 函数”，而是：

```text
加载目标
  → 调 public init
  → 触发 XHR/fetch/事件
  → 从宿主边界取得结果
```

把触发行为写进独立 `trigger.js`，不要拼进原始文件。

加载顺序必须记录：

```text
1. 创建全新 JSContext。
2. 配置本次声明的 environment/config。
3. 加载固定 hash 的原始目标。
4. 加载独立 trigger。
5. 按需要推进事件循环。
6. 从公开结果、netLog 或声明的观察点读取证据。
```

`trigger.js` 只包含本次问题需要的调用。例如：

```javascript
// 使用真实样本中已经确认的公开入口替换占位符。
window.publicApi.init(window.__CASE_INIT__);
window.publicApi.run(window.__CASE_INPUT__);
```

不要把案例专用入口固化成通用模板。入口名、初始化参数和 trigger 都是案例证据的一部分。

以下情况仍可标记 `runtime patched: false`：

- trigger 只调用目标已经公开的 API。
- 不替换目标函数、宿主属性或原型。
- 输入和环境配置均已单独记录。

## 11. L3：独立 probe

L0～L2 无法取得公开边界的参数、返回值、异常或写入时，使用独立 probe。

典型方法：

- 包装公开函数。
- 包装 prototype 方法。
- 使用 `Object.defineProperty` 观察属性写入。
- 使用 `ctx.expose()` 把小量证据送到 Python。

`ctx.expose()` 的对象位于 `__iv8__.data`，不污染普通 `window` 全局；JS 回调 Python 时会重新获取 GIL并阻塞当前 V8 执行，所以回调必须轻量。

Python 侧：

```python
events = []


def emit_evidence(event):
    events.append(event)


with iv8.JSContext(environment=environment) as ctx:
    ctx.expose(emit_evidence, "emitEvidence")
    ctx.eval(original_source, name="target.original.js")
    ctx.eval(probe_source, name="probe.js")
    ctx.eval(trigger_source, name="trigger.js")
```

probe 包装公开函数的骨架：

```javascript
(function () {
  var holder = window.publicApi;
  var key = "run";
  var desc = Object.getOwnPropertyDescriptor(holder, key);
  if (!desc || typeof desc.value !== "function") {
    throw new Error("probe precondition failed: publicApi.run");
  }

  var original = desc.value;
  var wrapped = function () {
    __iv8__.data.emitEvidence({
      phase: "call",
      argc: arguments.length,
      thisType: typeof this
    });

    try {
      var result = Reflect.apply(original, this, arguments);
      __iv8__.data.emitEvidence({
        phase: "return",
        resultType: typeof result
      });
      return result;
    } catch (error) {
      __iv8__.data.emitEvidence({
        phase: "throw",
        name: error && error.name,
        message: String(error && error.message)
      });
      throw error;
    }
  };

  Object.defineProperty(holder, key, {
    value: __iv8__.wrapNative(wrapped, key),
    writable: desc.writable,
    enumerable: desc.enumerable,
    configurable: desc.configurable
  });
})();
```

规则：

- 原样传递 `this` 和全部参数。
- 返回原始返回值，不替换 Promise。
- 异常只能记录后原样重抛。
- 尽可能保留 descriptor 和加载顺序。
- 不为日志进行可能触发 getter、Proxy 或序列化副作用的深拷贝。
- `wrapNative` 只降低 `toString()` 差异，不能证明 wrapper 不可检测。
- 使用 probe 的运行一律标记 `runtime patched: true`。

## 12. L4：派生副本插桩

只有在以下条件全部满足时才使用：

- L0～L3 不能取得完成当前 AST 步骤所需的内部事实。
- 插桩位置可以静态、稳定地定位。
- 用户明确批准运行派生副本。
- 能建立原始位置到插桩位置的映射。

文件角色：

```text
target.original.js
  不变，保留原始 hash。

target.instrumented.js
  单独生成，记录 transform、hash 和插桩点。
```

要求：

- `runtime patched: true`。
- 证据等级低于原始目标旁路观测。
- 固定输入下与原始目标做 A/B。
- 报告明确哪些结论来自插桩副本。
- 不把插桩副本的成功运行当成原始目标行为等价证明。
- 不在 AST Skill 中插桩 VM 分派器、PC、值栈、帧栈或虚拟函数。

## 13. runtime patched 与 A/B

每次动态实验必须显式写：

```text
runtime patched: true | false
```

以下情况为 `true`：

- 替换函数或 prototype。
- 安装 getter/setter。
- 修改局部变量或运行时对象。
- 注入缺失 API 或覆盖 stub。
- 执行插桩副本。

以下情况通常为 `false`：

- 仅启用 L0 debug 日志。
- 仅设置外部断点或 API watch，且未改值。
- trigger 只调用公开入口。

即使为 `false`，仍记录 debug、暂停和时间开销。

L3/L4 必须做 A/B：

```text
A：全新 Context + 原始目标 + trigger
B：全新 Context + 原始目标 + probe + 同一 trigger
```

对照至少包括：

- 是否完成相同阶段。
- 返回类型、异常类型和关键结构。
- 公开副作用。
- `netLog` 请求方法、URL 结构和顺序。
- 关键调用顺序。
- 是否出现新的环境探测或错误。

每次都创建全新 Context，避免上一次初始化、计数器或 Hook 污染。

如果输出含时间、随机数或计数器，不要求原始字符串完全相等；先冻结可冻结的输入，再比较结构性不变量。不能控制的熵源必须写入未覆盖范围。

A/B 发生实质差异时：

- 不使用该 probe 的结果支持 transform。
- 缩小 probe 或退回更低级别。
- 当前候选无法继续时标记 `BLOCKED_CURRENT`。

## 14. 事件循环与异步结果

iv8 不会替分析者自动推进所有逻辑时间。读取异步结果前必须选择正确的推进方式。

| 方法 | 准确语义 | 典型用途 |
| --- | --- | --- |
| `drain()` | 排空所有已到期任务，不推进时间 | 同步触发后的收尾、注入响应后的回调 |
| `drainMicrotasks()` | 只排空微任务 | Promise、`queueMicrotask`、MutationObserver |
| `drainTimers()` | 只处理已到期 timer | 已到期定时器 |
| `tick(ms?)` | 推进并执行一轮 | 逐轮观察 |
| `advance(total, step?)` | 分帧推进虚拟时间 | rAF、分帧逻辑、多个 timer |
| `sleep(ms?, max?)` | 推进指定逻辑时间并按顺序排队 | 明确延时 |

示例：

```python
ctx.eval(trigger_source, name="trigger.js")
ctx.eval("window.__iv8__.eventLoop.drainMicrotasks()")
ctx.eval("window.__iv8__.eventLoop.advance(100)")
result = ctx.eval("window.__CASE_RESULT__", to_py=True)
```

不要机械执行所有推进方法。根据目标实际注册的任务选择最小组合，并记录：

```text
time_mode
推进方法
推进时长
最大任务数
读取结果的时点
```

时间差、PoW 或真实耗时检查可能需要 `time_mode="system"`；普通可控实验优先逻辑时间。改变 time mode 会改变运行条件，必须进入证据记录。

拦截式 SDK 只在 XHR URL 上加签时，`netLog` 可能已经包含目标事实，不必为了等待不存在的响应而推进时间。

## 15. 动态证据映射回 AST

动态事实必须回到静态主线，不能停留在日志中。

推荐映射键：

- `ctx.eval(..., name="target.original.js")` 提供的脚本名。
- 原始行列或 byte offset。
- 调用栈中的函数位置。
- 唯一源码片段。
- AST 节点类型、父节点路径和邻近字面量。
- 格式化视图中的对应行列。
- transform 前后的稳定节点 ID。

映射表：

| evidence_id | 运行事实 | 输入与路径 | 原始位置 | 格式化位置 | AST 节点 | 置信度 |
| --- | --- | --- | --- | --- | --- | --- |
| `E-RUN-001` |  |  |  |  |  |  |

注意：

- Prettier 格式化会改变行列，不能把格式化行号直接当成原始断点位置。
- 找不到唯一映射时，只能把证据记为候选关联，不能据此批量替换。
- 动态值写回分析视图前，必须说明它是固定输入事实、路径事实还是可泛化常量。
- 路径事实不能被提升为未覆盖分支的静态常量。

完成映射后回到 AST 流程：

```text
动态取得事实
  → 绑定到原始 AST 节点
  → 检查适用范围
  → 生成或修正单步 transform
  → 验证派生分析视图
  → 重新阅读和画像
  → 向用户提交下一候选
```

## 16. 证据记录格式

每次实验至少保存：

```markdown
# Runtime Evidence <ID>

## Question

## Static Boundary

## Approval

## Runtime

- iv8 version:
- Python/platform:
- target path:
- target sha256:
- environment/config:
- time mode:
- trigger path and sha256:
- probe path and sha256:
- instrumented path and sha256:
- observation level: L0 | L1 | L2 | L3 | L4
- runtime patched: true | false

## Execution Order

## Observation

## Raw Evidence

- native log:
- netLog:
- DevTools notes:
- structured events:

## A/B

## Source Mapping

## Coverage

## Explicit Non-Conclusions

## Decision

Return to AST | retry lower intrusion | blocked | handoff
```

## 17. 分流与返回主线

| 结果 | 下一步 |
| --- | --- |
| 已取得有限、可映射事实 | 回到 AST 单步 transform |
| 只需再缩小一个观察点 | 重新设计更小实验 |
| probe 改变行为 | 退回 L0～L2，或缩小 probe |
| 需要系统补环境、离线资源和完整事件循环 | 推荐专门的 iv8 运行环境 Skill |
| 需要真实网络请求、账号、Cookie 或代理 | 单独申请授权并交接运行环境流程 |
| 需要真实布局、字体、音频、渲染或页面会话 | 转真实浏览器、CDP 或 js-reverse 能力 |
| 需要 VM Opcode、PC、值栈或 Trace | 交接 VM Skill |
| 当前事实仍无法取得 | `BLOCKED_CURRENT`，继续其他静态候选 |

动态取证结束后，iv8 不继续控制后续步骤；下一步重新由最新分析视图、收益和用户选择决定。

## 18. 禁止事项

- 不执行尚未定义证据问题的完整未知目标。
- 不在用户只批准静态步骤时静默升级动态。
- 不原地修改或格式化原始运行文件。
- 不把分析视图当成原始运行目标。
- 不把 `node:vm` 称为不可信代码安全沙箱。
- 不把 iv8 Community Edition 的 `netLog` 描述为真实网络请求。
- 不把 `drain()` 描述为推进时间。
- 不用 Python 普通 stdout 重定向冒充已捕获 C++ 日志。
- 不把 `wrapNative` 描述为绝对不可检测。
- 不把 runtime wrapper 描述为“零侵入”。
- 不把一次运行结果推广到全部输入和路径。
- 不因“疑似缺失 API”日志而批量补全浏览器对象。
- 不在本 reference 中复制完整补环境流程。
- 不在 AST Skill 中借动态调试进入 VM 内部。
