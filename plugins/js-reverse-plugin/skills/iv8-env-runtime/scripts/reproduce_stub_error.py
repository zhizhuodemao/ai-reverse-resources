#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reproduce_stub_error.py —— P2 定位 stub 空壳窟窿：跑目标直到抛 TypeError，压缩打印异常栈。

作用（对应 SKILL.md 的 P2「TypeError 栈=stub 窟窿」）：
    iv8 对很多浏览器 API 给了「接口级 stub」——存在但内部为空壳（典型：
    MessageChannel 构造出来 port1/port2 为 null）。目标 JS 一旦真去用它（如
    core-js 的 microtask 降级链会 new MessageChannel() 再取 port.postMessage），
    就在运行时抛 TypeError。本脚本分步 eval 目标（load → init → 触发），
    第一处抛错即捕获，并把冗长的混淆源码行压掉，只留「异常类型 + 位置摘要」，
    再打印一个「用 wrapNative 替换 stub」的提示模板。

    这是「三态」里的中间态：stub 空壳（替换）——区别于「真实现（别动）」与
    「陷阱缺失（绝不补）」。stub 的判定证据就是这里的 TypeError 栈。

关系与边界：
    - 上游：scripts/monitor_env.py 第⑥类「疑似缺失 API」提示哪里可能有窟窿；
            本脚本用「真跑抛错」坐实是不是 stub 空壳（缺失=没有该 API；stub=有但为空壳）。
    - 下游：确认是 stub → 按 references/patching-principles.md 的 iv8 原生补丁契约，
            用 __iv8__.wrapNative 写一个有真机证据的最小替身。
            本脚本只复现 MessageChannel / Worker 的 core-js 降级链与 iv8 调度问题。
    - MessageChannel/Worker null port 属已知坑 E2，版本门控见 references/version-gotchas.md。
    - 权威 API 契约见 references/iv8-api-contract.md。

用法：
    python reproduce_stub_error.py <目标JS路径> [--init <init表达式文件>] [--trigger <触发表达式文件>]
                                   [--env <environment JSON文件>] [--patch <预置替身JS文件>]

    - 不给 --patch：复现原始 TypeError（先看窟窿在哪）
    - 给 --patch：把替身 JS 先注入再跑（验证替换后是否跑通），
      --patch 文件内应是一段用 __iv8__.wrapNative 写的替身（示例见文末提示模板）。
"""

import argparse
import json
import os
import re
import sys

try:
    import iv8
except ImportError:
    sys.exit("未找到 iv8。先跑 scripts/preflight.py 确认安装（安装见 references/cross-platform-install.md）。")


# wrapNative 替换 stub 的提示模板（以 MessageChannel 为例，别照抄值，按目标改）
WRAPNATIVE_HINT = """\
[提示] 若确认是 stub 空壳（如 MessageChannel port=null），用 __iv8__.wrapNative 替换：

    window.MessageChannel = __iv8__.wrapNative(function() {
        var p1 = { onmessage: null }, p2 = { onmessage: null };
        p1.postMessage = function(d) {
            if (p2.onmessage) setTimeout(function(){ p2.onmessage({ data: d }); }, 0);
        };
        p2.postMessage = function(d) {
            if (p1.onmessage) setTimeout(function(){ p1.onmessage({ data: d }); }, 0);
        };
        return { port1: p1, port2: p2 };
    }, 'MessageChannel');

要点：
  - wrapNative 让替身 toString() 显示 [native code]，降低可观测差异。
  - 触发后需 __iv8__.eventLoop.advance(...) / drain() 排空 setTimeout 回调（微任务降级链）。
  - 三态：stub=替换 / 真实现=别动 / 陷阱缺失=绝不补（见 references/patching-principles.md）。
  - 完整替身必须按目标证据最小实现，并按 references/patching-principles.md 补后对账。
"""


def summarize_exception(exc, limit=1200):
    """压缩 iv8 异常字符串：混淆目标的源码行可能是整份几十 KB bundle，这里裁掉只留位置。"""
    text = str(exc) or repr(exc)
    text = re.sub(r"\s+", " ", text).strip()
    # iv8 异常串常形如 "... ( @ <line> : <col> ) -> <整行源码>"，裁掉 -> 之后
    m = re.match(r"^(.*?\( @ \d+ : \d+ \))\s*->", text)
    if m:
        return m.group(1)
    if len(text) > limit:
        return text[:limit] + " ...<truncated>"
    return text


def run_step(ctx, label, source):
    """执行一步，成功返回 (True, value)，抛错则打印压缩摘要返回 (False, None)。"""
    print(f"\n== {label} ==")
    try:
        value = ctx.eval(source, name=label, to_py=True)
    except Exception as exc:  # noqa: BLE001 —— 就是要捕获任意运行时异常
        print("FAILED")
        print("  exception type   :", type(exc).__name__)
        print("  exception summary:", summarize_exception(exc))
        return False, None
    print("OK")
    return True, value


def main():
    ap = argparse.ArgumentParser(description="跑目标直到抛 TypeError，压缩打印，定位 stub 空壳窟窿")
    ap.add_argument("js_path", help="目标 JS 文件路径")
    ap.add_argument("--init", default="", help="加载后的初始化表达式文件（如 xxx.init({...})）")
    ap.add_argument("--trigger", default="", help="触发签名/取数的表达式文件")
    ap.add_argument("--env", default="", help="environment 画像 JSON 文件路径")
    ap.add_argument("--patch", default="", help="预置替身 JS 文件（先注入再跑，验证替换是否跑通）")
    args = ap.parse_args()

    if not os.path.isfile(args.js_path):
        sys.exit(f"目标 JS 不存在: {args.js_path}")

    env = None
    if args.env:
        with open(args.env, "r", encoding="utf-8") as f:
            env = json.load(f)

    with open(args.js_path, "r", encoding="utf-8") as f:
        js = f.read()

    def read_opt(path):
        if not path:
            return ""
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()

    patch_src = read_opt(args.patch)
    init_src = read_opt(args.init)
    trigger_src = read_opt(args.trigger) or "window.__iv8__.eventLoop.drain();"

    print("目标 JS   :", args.js_path)
    print("JS 字节   :", len(js.encode("utf-8")))
    print("预置替身  :", "有（--patch）" if patch_src else "无（复现原始报错）")

    # prod 模式即可复现（不需要 debug 监控开销）
    with iv8.JSContext(environment=env) as ctx:
        if patch_src:
            ok, _ = run_step(ctx, "inject patch (wrapNative 替身)", patch_src)
            if not ok:
                print("\n替身注入本身就抛错，先修替身。")
                print(WRAPNATIVE_HINT)
                return

        ok, _ = run_step(ctx, "eval target", js)
        if not ok:
            print(WRAPNATIVE_HINT)
            return

        if init_src:
            ok, _ = run_step(ctx, "init", init_src)
            if not ok:
                print(WRAPNATIVE_HINT)
                return

        ok, val = run_step(ctx, "trigger + drain", trigger_src)
        if not ok:
            print(WRAPNATIVE_HINT)
            return

        print("\n全部步骤跑通，未复现 stub 报错。")
        if patch_src:
            print("→ 替身有效：该 stub 窟窿已补上。")
        else:
            print("→ 目标此路径未触发 stub 窟窿（或缺口在别处）。")
        if isinstance(val, list):
            print(f"trigger 返回条目数: {len(val)}")


if __name__ == "__main__":
    main()
