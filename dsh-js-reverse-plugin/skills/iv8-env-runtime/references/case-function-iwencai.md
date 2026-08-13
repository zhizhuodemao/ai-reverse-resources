# 案例 · 函数式：爱问财 hexin-v（P1→P4 端到端）

> 函数式入口标本：目标 token 是一个**纯函数**的返回值，把输入喂对就逐字符复现，
> 与时间/鼠标键盘/cookie/刷新逻辑全无关。演示 P1 用断点证「纯函数」、P4 用「相同输入 ⟹
> 相同输出」当对账契约。deploy 绑定值（脚本 deploy 号 / `n(328)`/`n(598)` 方法名映射 /
> `TOKEN_SERVER_TIME` / token 样例）**仅示例，运行时从当前脚本解析，勿写死、勿跨 deploy 抄**。

---

## P1 定位：断点证 hexin-v 是 u 数组的纯函数

**目标字段**：请求 **header** 里的 `hexin-v`（位置在 header，不在 URL/body——先看清）。

**生成链路**（断点实证，调用栈自顶向下）：
```
XMLHttpRequest.open → A() → M.update() → i() → encode
```
`i()` 是跑 switch 的内部函数：先 refresh（刷新 `u` 的动态槽位：时间 `u[2]`、事件
`u[7..12]`、计数器 `u[16]++`…），最后 `case"2": return h[n(328)](i)` 做 encode 返回 token。
encode 的输入 `i = u[n(598)]()`，即 `u` 自身的序列化。

**下断点 → 防重入 → 帧内快照**（对应 part1-mcp-tool-map §3-B/C）：
1. 在脚本 `u[16]++` 处 `set_breakpoint_on_text` 下断点。
2. 触发一次 XHR `open()`（页面自身或手动 `new XMLHttpRequest().open('GET','/x')`）让执行停在
   `i()` 帧。
3. **`remove_breakpoint` 移除断点**——否则下一步嵌套调用会再次暂停死锁。
4. 帧内 `evaluate_script`（用箭头函数取帧内局部）做快照与验证：
```js
// 帧内可访问：u(索引可读写)、n(字符串解码器)、h(encode 模块)、M.update、z(="hexin-v")
const origNow = Date.now;
Date.now = () => 1782744000000;         // 冻结时间 → u[2] 固定，排除时间干扰
u[16] = 4999; const T0 = M.update();     // ++ 后 = 5000
const S0 = []; for (let k=0;k<18;k++) S0[k] = u[k];
u[16] = 4999; const T1 = M.update();
u[16] = 4999; const T2 = M.update();     // 期望 T0===T1===T2
// 纯函数验证：设回 S0 直接 encode，绕过 refresh
const enc = s => { for (let k=0;k<18;k++) u[k]=s[k]; return h[n(328)](u[n(598)]()); };
const T_direct = enc(S0);                // 期望 === T0
Date.now = origNow;                      // 还原
```

**关键实测（P1 铁证）**：把 refresh 整段绕过、直接用一组固定 `u` 喂 encode，token 仍逐字符
复现 ⇒ encode 不读 `u` 以外任何动态源（不读 Date/Math.random/事件/cookie）。这就是
「中间结果 == 最终结果」的边界证据，且改任一 `u[k]`（如 `u[3]`、`u[16]`）token 就变，
证明它确实依赖全部 `u` 且是确定性纯函数。

`u` 索引语义（**仅示例**）：`u[0]`=cookie `v` 种子；`u[1]`=serverTime 常量；`u[2]`=秒级时间；
`u[3]`=UA 哈希；`u[4/5/6]`=屏幕指纹；`u[7..12]`=键鼠事件计数；`u[13]`=浏览器特征位；
`u[16]`=per-call 自增计数器；`u[17]`=常量 3。注意 `u` 不是原生数组
（`Array.isArray(u)===false`、无 `.length`），只能 `u[k]` 索引逐个读写。

P1 结论落 `assets/entry-report-template.txt`：入口类型=函数式，来源类型=本地生成，
结论=已定位。

---

## P2/P3：iv8 复现 = 直接调函数（对账解耦成两层）

函数式复现骨架比拦截式简单——不装 hook、不发 XHR，**直接调 encode**。补环境职责因此
退化为一件事：**让 iv8 里的 `u` 数组等于浏览器里的 `u`**。对账被解耦成两层：

| 层 | 内容 | 是否需要补环境 |
|---|---|---|
| A. encode 纯函数 | 喂相同 `u` → 相同 token | 否，同一份脚本在受控 iv8 中必须与浏览器样本一致 |
| B. 环境 → u | `u[0]`=cookie、`u[3]`=UA、`u[4/5/6/13]`=指纹… | 是，这才是补环境真正要做的 |

**P2**：iv8 加载**同一 deploy** 的 chameleon 脚本；A 层零补环境就该过（过不了说明脚本没
正确加载/运行）。**P3**：补 `location`/`navigator`(UA)/指纹，让 B 层各槽位 == 浏览器；
逐槽对账，差哪槽补哪槽（iv8 原生配置与补丁契约见 `references/patching-principles.md`）。

---

## P4 验收：相同输入 ⟹ 逐字符相同 token（+ 服务器判决）

**A 层对账契约**（铁判据）：iv8 里把 `u[0..17]` 设成采样快照的 18 个整数，调
`h[n(328)]( u[n(598)]() )`，**必须逐字符等于**采到的 token 样例（**仅示例**）：
```
u = [100,1782743000,1782744000,200,7,10,5,0,0,0,0,0,0,3748,0,0,5000,3]
  ⟹ A8jIp4oFNqnBHVotsalEM-aFnz3fcSx7DtUA_4J5FMM2XWZjKoH8C17lwwfR
```
对到 18 个整数，token 自动对——不必去赌最终那串 token。A 层通过后再让 B 层把 `u` 逐槽
对齐浏览器。

**最终真相仍是服务器**：把带对齐 `u` 产出的 `hexin-v` 放进 header 发真包，服务器响应正常
（可接受标准）或与浏览器完全一致（最强标准）才算成功；本地自洽不算。算出被拒 → 回 P3
定位差异槽位（`u[0]`/`u[13]` 定位法）。`403` 非环境优先排查。

---

## 陷阱

- **绑定 deploy**：encode 算法、`n(328)/n(598)` 方法名映射、`TOKEN_SERVER_TIME` 都随 deploy
  变。iv8 与浏览器必须用**同一份脚本**对账；换 deploy 重新采标准答案。方法名要在当前脚本
  运行时里取，不能跨 deploy 硬抄。
- 冻结 `Date.now` 只为 P1 排除时间干扰、证纯函数；证完即还原，避免影响页面。
- `u` 非原生数组：别用 `Array.from(u)`（得空），逐 `u[k]` 读写。
