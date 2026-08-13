# iv8 专坑与版本门控（version-gotchas）

> **版本 BANNER（必读）**：本文件每条坑都**绑定 iv8 版本**。iv8 是闭源编译 wheel，
> 一个补丁在旧版是必需、在新版可能已被引擎修掉。**唯一权威版本 = `scripts/preflight.py`
> 打印的实测版本**（读它，别读本文标题）。凡标 **[已修 @ x.y.z]** 的坑：若 preflight
> 打印版本 ≥ 该版本，**别照抄补丁**——照抄反而制造与真浏览器的差异，自曝。
>
> 单一真相源：版本从 preflight 消费，不在本文写死"当前是 0.1.3"当结论。
> 目标 JavaScript 强制在 iv8 中运行。所有修正必须遵循 `references/patching-principles.md` 的 iv8 原生补丁契约；本文只写 iv8 专属差异。

---

## 门控总则（先读再往下）

1. 每条坑三段：**现象 / 代码骨架 / 版本状态+适用边界**。
2. 遇到崩溃先查 preflight 版本 → 对照本表判断"这条坑在你的版本还存不存在"。
3. 补一个 stub 前先问：它是 §三态里的哪一态？只有 **stub 空壳**该补，**陷阱缺失绝不补**（见 references/trap-blacklist.md）。
4. 修完必须回到验收：本地不崩 ≠ 成功，**服务器 200/code=0 才是唯一真相**（见 SKILL.md P4 / scripts/parity_check.py）。

---

## E1. `btoa()` Latin1 判定过窄 — **[已修 @ 0.1.3]**

- **现象（旧版）**：`btoa(String.fromCharCode(0xE9))` 等 charCode 128–255 的 Latin1 输入被错误拒绝抛异常。
  sensor/collect 里含二进制字节 → btoa 失败 → 提交体空/`solution=null` → 服务端罐头错误。
- **代码骨架（仅旧版注入，跑原版 SDK **之前**覆盖 `window.btoa`，`&0xff` 只取低字节绕字符校验）**：
  ```javascript
  (function(){ var B="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    window.btoa=function(d){ var s=String(d),o=""; for(var i=0;i<s.length;i+=3){
      var a=s.charCodeAt(i)&0xff,b=i+1<s.length?s.charCodeAt(i+1)&0xff:0,c=i+2<s.length?s.charCodeAt(i+2)&0xff:0;
      o+=B[a>>2]+B[((a&3)<<4)|(b>>4)]+(i+1<s.length?B[((b&15)<<2)|(c>>6)]:'=')+(i+2<s.length?B[c&63]:'='); } return o; };
  })();
  ```
- **版本状态/边界**：**0.1.3 已修**（README 更新记录明列）。preflight 版本 ≥ 0.1.3 **勿注入**——原生 btoa 已正确，
  盖一层纯 JS 版会让 `btoa.toString()` 变成 `function(){...}`（非 `[native code]`），凭空制造检测点。只有 <0.1.3 才注入。

---

## E2. `MessageChannel`/`Worker` 的 port 为 null — core-js microtask 降级链

- **现象**：iv8 内置 `MessageChannel` 是 **stub 空壳**（typeof=function、toString=[native code] 过检测），
  但 `new MessageChannel().port1 === null`。core-js（bdms 等字节系 SDK 的 microtask polyfill）探测
  MessageChannel 做快速异步调度，对 null port 调 `.postMessage`/设 `.onmessage` →
  `Cannot set properties of null (setting 'onmessage')` → 事件循环断裂，`data()`/采集 Promise 永挂。
- **代码骨架（覆盖成"非 null 但行为为空"的 port，让 core-js 安全降级到 setTimeout；再配 advance+drain 推进）**：
  ```javascript
  window.Worker=function Worker(){this.onmessage=null;this.onerror=null;this.postMessage=function(){};this.terminate=function(){};};
  window.MessageChannel=function MessageChannel(){
    var mk=function(){return{onmessage:null,onmessageerror:null,postMessage:function(){},start:function(){},close:function(){}};};
    this.port1=mk(); this.port2=mk();
  };
  // 装完后驱动：ctx.eval("window.__iv8__.eventLoop.advance(50)"); ctx.eval("...drain()")
  ```
- **版本状态/边界**：属 **stub 空壳窟窿**（三态之一），未随版本消失——每次跑新 SDK 仍可能撞。**用 `wrapNative` 包装保 `[native code]`**。
  依赖 core-js microtask 降级链的 SDK 通用；若覆盖后 async 采集仍不推进，是"Promise 不推进"更深问题，见 references/network-and-eventloop.md 的 drain 章节。

---

## E4. WASM 反调试：instanceof 校验 + ~410MB OOM 炸弹

- **现象**：wasm-bindgen 型签名器内置多层"是否真实浏览器"检测，任一不过即分配 ~410MB ArrayBuffer 做
  OOM 炸弹/panic。典型五关：① `global` 必须 `undefined`；② `self instanceof Window===true`；
  ③ `location instanceof Location`；④ `documentElement instanceof HTMLElement`；⑤ direct `eval` 语义。
- **代码骨架（`Object.create(Proto.prototype)` 伪造满足 instanceof 的实例；`global=undefined`；跑真 WASM，**不跑 wasm2js fallback**——fallback 才含炸弹）**：
  ```javascript
  function Location(){} function HTMLElement(){} function Window(){}
  var location=Object.create(Location.prototype);            // ③ ✓
  var documentElement=Object.create(HTMLElement.prototype);  // ④ ✓
  var win=Object.create(Window.prototype);                   // ② self instanceof Window ✓
  win.self=win;win.window=win;win.globalThis=win;win.top=win;win.parent=win;
  s.global=undefined;                                        // ① 浏览器无 global ✓
  var inst=new WebAssembly.Instance(new WebAssembly.Module(wasmBytes),{wbg:glue}); // 真 WASM
  ```
- **版本状态/边界**：与 iv8 版本无关（是目标 WASM 的反调试，不是 iv8 引擎坑）。带 instanceof+OOM 的 wasm-bindgen 签名器通用。
  保留目标原始 glue、真实 WASM 字节及其 `__wbg_set_wasm`/`__wbindgen_start` 初始化顺序；只修正动态证据坐实的宿主 binding，不套跨目标桥接模板。iv8 侧不额外注入 eval/Function。

---

## E5. audio 指纹金标准 buffer — 真机抓一次注入

- **现象**：SDK 采 audio 指纹（`OfflineAudioContext(1,5000,44100)` → triangle@10kHz → DynamicsCompressor →
  渲染求 channel0`[4500:5000]` 绝对值和）。iv8 社区版**砍掉了真实渲染引擎**，算不出该浮点和。
- **代码骨架（真机 js-reverse `evaluate_script` 跑一次拿金标准 Float32 buffer 落地 → 注入 `window.__AUDIO_F32__` → mock `startRendering` 直接吐真 buffer）**：
  ```javascript
  mkOAC.prototype.startRendering=function(){var self=this; return new Promise(function(resolve){
    var d=window.__AUDIO_F32__||new Float32Array(self.length||5000);
    var arr=d.length>=self.length?d.subarray(0,self.length):d;
    self.state='complete'; setTimeout(function(){resolve({sampleRate:self.sampleRate,length:self.length,
      numberOfChannels:self.numberOfChannels,getChannelData:function(){return arr;}});},0);
  });};
  ```
- **版本状态/边界**：**硬天花板类**，非版本坑——iv8 永不做像素/音频渲染（README 明确社区版无布局/渲染）。
  分辨：sum 校验型用注入 buffer；属性采集型（只读 destination/channelCount/sampleRate/state）mock 属性即可。金标准值随采集参数变，**运行时抓，勿写死**。

---

## E6. jsvmp null-safe 操作码 patch

- **现象**：jsvmp 渲染阶段大量 DOM 读写（`.style`/`.appendChild()`），操作码形如 `bx(i,Y)[bx(i,Z)]`。
  无 layout 时元素常返回 null，jsvmp 对 null 取属性/赋值 → TypeError → 采集中途崩。
- **代码骨架（正则把 property-GET/SET 操作码改 null-safe，命中 null 落到黑洞对象）**：
  ```javascript
  src=src.replace(/ux\(i,(\w+),bx\(i,(\w+)\)\[bx\(i,(\w+)\)\]\)/g,'ux(i,$1,bx(i,$2)==null?window.__nullSafe:bx(i,$2)[bx(i,$3)])');
  src=src.replace(/([\w$.\[\]]+)\.appendChild\(/g,'($1||window.__nullSafe).appendChild(');
  // window.__nullSafe = new Proxy(function(){},{get:(t,k)=>k==='length'?0:window.__nullSafe,set:()=>true,apply:()=>window.__nullSafe,construct:()=>window.__nullSafe});
  ```
- **版本状态/边界**：与 iv8 版本无关，属源码级 patch。iv8 有 C++ DOM/layout 表面，很多此类 null 崩本不会出现；
  仅当目标 jsvmp 读到 iv8 未实现的 layout 量（如真实 `getBoundingClientRect` 宽）才需要。**先跑，撞到再 patch**，别预防性乱改。

---

## E7. 字体渲染指纹 — 采集物理量后注回 iv8

- **现象**：探测字体渲染精确像素宽（`getBoundingClientRect()` 测 Verdana 等文字宽）。iv8 无字体引擎，
  只能 `length*fontSize*0.55` 近似，精度不够 → 风控判负。
- **对策**：用真实浏览器只采集目标实际读取的字体宽度或渲染测量表，把这些值声明为原始环境输入并注回 iv8；最终 SDK、生成入口和 token 仍在 iv8 中执行。不要直接拿浏览器生成的 token 代替 iv8 结果。
- **版本状态/边界**：**永久物理量缺口**，任何 iv8 版本都不会内置完整字体渲染。若无法把所需测量值隔离为可声明输入，状态应记为 `ORACLE_BLOCKED`，不能静默切换参考运行时。

---

## 一致性红线（跨所有坑重申）

改指纹只能改"值"，改不掉"API 存不存在"。**安全区 = Chrome/Chromium 家族内换不同机器；别伪装 Safari/Firefox**（涉 API 存在性差异，iv8 改不动）。
以下六条必须整套对齐，任一漏改就自相矛盾秒露馅（曾实测：改了 `navigator.userAgent` 为 Mac、漏改 `navigator.userAgentData.platform` 仍 Windows → UA 说 Mac、UA-CH 说 Windows）：

> **UA ↔ userAgentData ↔ platform ↔ 时区 ↔ 语言 ↔ webgl(vendor/renderer)**

对齐逻辑得自己保证（与逐字段对齐同功夫）。可配路径清单见 references/config-defaults-cheatsheet.md；三态与陷阱名单见 references/trap-blacklist.md。
