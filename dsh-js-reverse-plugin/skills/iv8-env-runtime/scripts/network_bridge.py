#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
network_bridge.py — iv8 真实网络桥接（阶段 P3，固化四步握手）

======================================================================
四步握手红线（社区版无真实网络传输栈，真请求必须走 Python 侧）：
  1) JS 侧发起 XHR/fetch  —— iv8 只记账到 netLog，不真正发出请求。
  2) 暂停在这里，从 netLog 取出目标请求（url/method/headers/body）。
  3) Python 侧用真实 HTTP 客户端（requests / curl_cffi ...）真发，
     代理 / TLS 指纹 / cookie 池 / verify 由调用者决定。
  4) ctx.add_resource(url, body, status, headers) 注入响应，
     再 eventLoop.drain() 推进事件循环 —— XHR 回调此时才命中注入的响应。
  顺序错了（比如没 drain 就读结果，或没 add_resource 就 drain）都会拿到空/半成品。

⚠ GIL 警告：
  ctx.expose() 暴露给 JS 的 Python 函数，在被 JS 调用期间会持有 GIL 并阻塞
  当前 V8 执行与其他 Python 线程，是完全同步阻塞的。因此：
  - 暴露的桥接函数要尽量轻量，别在里面塞重逻辑；
  - 高并发场景优先用下面 bridge_request() 的「外部真发 + add_resource 注入」模式，
    而不是把 requests.get 直接 expose 进 JS 里循环调用。
======================================================================

用途：
  提供一个可复用的 bridge_request()：在 iv8 里让目标 JS 发起请求 → 从 netLog 捞出
  该请求 → Python 侧真发 → add_resource 注入响应 → drain 推进 → 返回真实响应。
  以及 __main__ 里一段最小可跑演示。

用法（库调用）：
    import iv8, requests
    from network_bridge import bridge_request
    with iv8.JSContext(environment={...}) as ctx:
        ctx.eval(open("target.js").read())
        # 让目标 JS 发起它的请求（这里只入 netLog，不真发）
        ctx.eval("window.startCollect()")
        resp_text = bridge_request(
            ctx,
            url_substr="/api/collect",      # 用于在 netLog 中定位目标请求
            session=requests.Session(),     # 由调用者提供，携带代理/cookie/TLS 策略
            verify=False,                   # curl_cffi/requests 自签名场景可关
        )

本文件属于 iv8-env-runtime skill。
交叉引用：事件循环 drain/advance 语义与 netLog 结构见
         references/network-and-eventloop.md；
         iv8 权威 API 见 references/iv8-api-contract.md。
"""

import sys


def _find_entry(netlog, url_substr):
    """在 netLog.entries 里按 url 子串定位目标请求，取最后一条匹配（通常是最新）。"""
    match = None
    for e in netlog:
        if not isinstance(e, dict):
            continue
        if url_substr in str(e.get("url", "")):
            match = e
    return match


def bridge_request(ctx, url_substr, session=None, method=None,
                   extra_headers=None, verify=True, proxies=None, timeout=15):
    """执行一次四步握手，返回注入到 iv8 后由 JS 侧收到的响应体文本。

    参数：
      ctx          : 已载入目标 JS 且已触发发请求的 iv8.JSContext。
      url_substr   : 在 netLog 中定位目标请求的 url 子串。
      session      : 调用者提供的 HTTP 客户端（requests.Session / curl_cffi.Session）；
                     None 时用一次性 requests。代理/TLS 指纹/cookie 全由它决定。
      method       : 覆盖请求方法；None 时用 netLog 记的方法。
      extra_headers: 追加/覆盖到真发请求上的头（如补 cookie/referer）。
      verify       : 传给客户端的 TLS 校验开关（curl_cffi 自签名场景常关）。
      proxies      : 传给客户端的代理配置。
      timeout      : 真发超时秒数。

    返回：注入后的响应体文本（同时已 add_resource + drain，JS 侧回调已命中）。
    """
    # 步骤 2：从 netLog 捞出目标请求（此前 JS 已 step 1 发起，仅入账未真发）
    netlog = ctx.eval("window.__iv8__.netLog.entries", to_py=True)
    entry = _find_entry(netlog, url_substr)
    if entry is None:
        raise LookupError(
            "netLog 中没有匹配 '{}' 的请求：确认目标 JS 已真的发起该请求，"
            "且 url_substr 写对了。当前 netLog 有 {} 条。".format(url_substr, len(netlog)))

    url = entry.get("url")
    req_method = (method or entry.get("method") or "GET").upper()
    headers = dict(entry.get("headers") or {})
    if extra_headers:
        headers.update(extra_headers)
    body = entry.get("body") or entry.get("postData")

    # 步骤 3：Python 侧真发（客户端由调用者决定，携带代理/cookie/TLS 指纹）
    if session is None:
        import requests
        session = requests.Session()
    resp = session.request(req_method, url, headers=headers, data=body,
                           verify=verify, proxies=proxies, timeout=timeout)

    # 步骤 4：注入响应 → drain 推进 → JS 侧 XHR 回调命中
    ctx.add_resource(
        url=url,
        body=resp.text,
        status=resp.status_code,
        headers=dict(resp.headers),
    )
    ctx.eval("window.__iv8__.eventLoop.drain()")
    return resp.text


# ---------------------------------------------------------------------------
# 最小可跑演示（需已安装 iv8 与 requests）：JS 发 XHR → 桥接真发 httpbin → 注入 → 读结果
# ---------------------------------------------------------------------------
def _demo():
    try:
        import iv8
        import requests  # noqa: F401 —— bridge_request 内部用；此处仅校验可导入
    except Exception as e:  # noqa: BLE001
        print("[network_bridge][demo] 依赖缺失：{}；先跑 preflight.py。".format(e), file=sys.stderr)
        return 2

    with iv8.JSContext() as ctx:
        ctx.eval("""
            window.__iv8__.page.load({
                baseURL: 'https://example.com',
                html: '<html><body></body></html>'
            });
        """)
        # 步骤 1：JS 侧发起异步 XHR（社区版只入 netLog，不真发）
        ctx.eval("""
            var xhr = new XMLHttpRequest();
            xhr.open('GET', 'https://httpbin.org/get?foo=bar');
            xhr.onload = function () { window._demoResult = xhr.responseText; };
            xhr.send();
        """)
        # 步骤 2/3/4：桥接
        body = bridge_request(ctx, url_substr="httpbin.org/get")
        print("[network_bridge][demo] 注入响应长度：{}".format(len(body)))
        got = ctx.eval("window._demoResult")
        print("[network_bridge][demo] JS 侧收到长度：{}".format(len(got) if got else 0))
    return 0


if __name__ == "__main__":
    sys.exit(_demo())
