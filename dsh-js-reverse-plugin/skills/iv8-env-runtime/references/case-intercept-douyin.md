# 案例 · 拦截式：抖音 a_bogus（P1→P4 端到端）

> 拦截式入口标本：目标签名不是「调函数返回」，而是 init 装 XHR hook 后、发请求那一刻
> 被注入 URL。演示 P1 用 MCP 三招递进找到 bdms，P2/P3 用 iv8 装 hook + 触发 + 捞 netLog。
> 全部 deploy 绑定值（bdms 版本 / aid / pageId / paths / a_bogus 样例）**仅示例，运行时
> 从真机解析，勿写死**。

---

## P1 定位：三招递进找到 bdms（拦截式）

**目标字段**：URL query 里的 `a_bogus`。删掉重放 → 被拦/空数据 ⇒ 确认是门票。
位置在 **URL query**（不是 header/body），这决定了往「网络出口」方向找。

**招① 搜参数名**（`search_in_sources("a_bogus")`）→ `No matches found`。
反爬藏了名字，是常态，不卡住，换招（见 part1-mcp-tool-map §3-A）。

**招② 堵网络出口**（`evaluate_script(mainWorld=true)`）：
```js
XMLHttpRequest.prototype.open.toString()   // 不是 [native code]，被改写成安全代理
window.fetch.toString()
```
`open` 被改写成 `function(){ this.secureOpenArgs=arguments; this.ucProxyParam={...};
t.nativeXMLHttpRequestOpen.apply(this,arguments) }` ⇒ 网络出口被安全代理接管，`a_bogus`
在这条代理链里注入。

**招③ 搜 hook 明文胎记**：hook 自用属性名 `secureOpenArgs`、`nativeXMLHttpRequestOpen`
没被混淆 → `search_in_sources("secureOpenArgs")` 命中字节 `@byted/uc-secure-dtrait-core`，
顺藤摸到真正算签名的模块 **bdms**。

**等价快招**：`break_on_xhr`(带 a_bogus 的请求) → `get_paused_info` 看调用栈 → 栈里直接
显示安全 SDK wrapper → 一步到 SDK。

**判类型**：`evaluate_script` 求 `Object.keys(window.bdms)` → 只有 `["getReferer","init"]`，
没有 `sign(url)`。没有签名函数 + 出口被 hook ⇒ **拦截式**。
对照实验（P1 铁证）：同一 XHR，不 init → URL 无 a_bogus；init 后 → URL 自动带 a_bogus。
这就是「上一层没有、下一层有」的动态边界。

**抓 init 的 config**（拦截式必须拿对 config，否则 hook 装不对）：
init 是 webpack 转发壳 `function(){return X(e,this,arguments,r)}`，所有 export 共用 →
下**条件断点**只在真 init 命中：
```
set_breakpoint_on_text("return X(e,this,arguments,r)",
    condition="arguments[0]&&arguments[0].paths&&arguments[0].aid")
navigate(reload)   → 命中
evaluate(frameIndex=0, "() => arguments[0]")   // 箭头函数取暂停帧实参 = config
```
抓到（**仅示例**）：`{"aid":6383,"pageId":6241,"paths":["^/aweme/v1/",...],"boe":false,
"ddrt":8.5,"ic":8.5}`。唯一要上心的是 `paths`——确认 `^/aweme/v1/` 命中你的接口
`/aweme/v1/web/aweme/detail/`；其余字段照搬真机值。

P1 结论落 `assets/entry-report-template.txt`：入口类型=拦截式，来源类型=本地生成
（hook 现场算），结论=已定位。

---

## P2 起手跑 + 发现缺口

最小 environment 零配跑 bdms（location 默认 about:blank 必配；navigator 配 UA）。
加载 bdms 直接崩：`TypeError: Cannot set properties of null (setting 'onmessage')`。
这是**报错驱动**发现的 stub 窟窿——iv8 的 `MessageChannel` 看起来存在，但
`new MessageChannel().port1/port2` 是空壳。定位见 `references/trap-blacklist.md` 的
API 三态（stub 空壳→替换）。

---

## P3 配环境 + 补漏 + 跑通

```python
import iv8
from urllib.parse import urlencode

environment = {
    "location": {  # 必配，默认 about:blank 会让签名上下文错
        "href": "https://www.douyin.com/video/<id>", "origin": "https://www.douyin.com",
        "protocol": "https:", "host": "www.douyin.com", "hostname": "www.douyin.com",
        "port": "", "pathname": "/video/<id>", "search": "", "hash": "",
    },
    "navigator": {"userAgent": "Mozilla/5.0 ... Chrome/124.0.0.0 Safari/537.36",
                  "language": "en-US", "languages": ["en-US", "en"]},
}

with iv8.JSContext(environment=environment) as ctx:
    # ① 替换 MessageChannel stub 空壳（wrapNative 伪装成原生，降检测差异）
    ctx.eval("""
    window.MessageChannel = __iv8__.wrapNative(function(){
      const p1={onmessage:null}, p2={onmessage:null};
      p1.postMessage=d=>{ if(p2.onmessage) setTimeout(()=>p2.onmessage({data:d}),0); };
      p2.postMessage=d=>{ if(p1.onmessage) setTimeout(()=>p1.onmessage({data:d}),0); };
      return {port1:p1, port2:p2};
    },'MessageChannel');
    """)
    ctx.eval(open("examples/js/bdms_1.0.1.19.js", encoding="utf-8").read())  # ② 加载 SDK
    ctx.eval('window.bdms.init({...抓到的 config 原样照搬...});')             # ③ 装 hook
    entries = ctx.eval(f'''                                                  # ④ 触发 + 捞
        var xhr=new XMLHttpRequest();
        xhr.open("GET","{url}?{urlencode(params)}",true);
        xhr.setRequestHeader("Content-Type","application/json, text/plain, */*");
        xhr.send(null);
        window.__iv8__.netLog.entries;
    ''', to_py=True)

signed_url = entries[0]["url"]   # ← 带 a_bogus 的最终 URL（hook 副作用产出，非 bdms 返回值）
```

MessageChannel 走 core-js microtask 降级链时若不产出，需配 `wrapNative` +
`eventLoop.advance`/`drain` 推进，见 `references/network-and-eventloop.md`。

---

## P4 验收：服务器判决唯一真相

```python
resp = requests.get(signed_url, headers=headers, cookies={"ttwid": "..."})
print(resp.status_code)   # 200 + 拿到真实视频详情 JSON ⇒ 服务器认账
```

- **200 = 服务器端判决**，证明本地 a_bogus 通过抖音真实风控，不是本地自欺。
- 本地 netLog 有 a_bogus 但**不算成功**——必须服务器认账。算出被拒 → 回 P3 对齐指纹；
  `403` 多半非环境（cookie/ttwid/IP/参数过期），先排除非环境因素再谈指纹对齐。

---

## 排错速查

| 现象 | 说明 | 下一步 |
|---|---|---|
| 搜参数名 No matches | 反爬藏名（常态） | 换堵网络出口招 |
| open 是 [native code] | 没被 hook 或 hook 在别处 | 查 send/fetch/setRequestHeader 或下 XHR 断点看栈 |
| 断点命中无数次 | webpack 转发壳共用 | 加 condition 只在 paths+aid 时停 |
| 跑崩 TypeError null onmessage | 撞 MessageChannel stub | 替换该 stub |
| netLog 有记录无 a_bogus | 未 init / paths 不命中 / 没真触发 | 逐条核对 init、paths、xhr、读 netLog |
| URL 有 a_bogus 但请求 403 | 多半非环境 | 先查 cookie/ttwid/IP/参数过期 |
