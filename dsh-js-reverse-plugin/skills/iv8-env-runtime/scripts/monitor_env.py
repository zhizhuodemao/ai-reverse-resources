#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""monitor_env.py —— P2 发现阶段核心工具：跑一遍目标 JS，抓 iv8 C++ 层监控日志分六类。

作用（对应 SKILL.md 的 P2「起手跑 + 发现缺口」）：
    用 iv8 mode='debug' 加载目标 JS 并触发一次签名/取数，把引擎在 C++ 层记录的
    「浏览器 API 访问链路 + JS 内置反射路径」实时打到 stdout(fd1)/stderr(fd2)，
    本脚本用 fd 重定向把它落盘再正则解析，按六类打印：
        ① 属性读 getter   —— 目标读了哪些指纹字段（配 environment 的清单来源）
        ② 属性写 setter   —— 目标改/挂了什么（常见是 XHR.open / fetch 的 hook）
        ③ 方法调用 call
        ④ 存在性探测 query（typeof / in，反爬最爱）
        ⑤ 反射层 —— Object.keys / getOwnPropertyDescriptor / toString / JSON.* 等探测
        ⑥ ⚠ 疑似缺失 API —— 目标摸了但 iv8 未实现（单列，见下方处置纪律）

第⑥类「疑似缺失 API」的处置纪律（贯穿本 skill 的三态原则）：
    默认按「陷阱」处理 —— 绝不无脑补。process / _phantom / __webdriver_script_fn /
    StyleMedia / Float16Array 之类是反爬故意探测的不存在物，补了反而暴露。
    只有在真机（真实 Chrome）核对确认「真实浏览器里此 API 确有值」时，才配置/补它。
    详见 references/trap-blacklist.md 与 references/patching-principles.md。

关系与边界：
    - 本脚本只做「发现」：告诉你目标读了什么、探测了什么、摸了哪些缺失物。
    - 「读了什么」→ 拿去 environment 配值，交集算法见 scripts/defaults_audit.py。
    - 抛 TypeError 的 stub 窟窿（如 MessageChannel port=null）→ scripts/reproduce_stub_error.py。
    - stub 替换按 references/patching-principles.md 的 iv8 原生补丁契约执行。
    - 权威 API 契约见 references/iv8-api-contract.md；坑位版本门控见 references/version-gotchas.md。

用法：
    python monitor_env.py <目标JS路径> [--url <触发URL>] [--trigger <触发JS表达式文件>]
                          [--env <environment JSON文件>] [--log <日志落盘路径>]

    最小用法（零配跑，观察默认环境下都缺什么）：
        python monitor_env.py ./target.js
    带触发（脚本加载后还需调一次才产签名）：
        python monitor_env.py ./target.js --trigger ./trigger.js
    trigger.js 内是一段 JS（示例）：
        var x = new XMLHttpRequest(); x.open('GET','https://api.example.com/d'); x.send();
        window.__iv8__.eventLoop.drain(); window.__iv8__.netLog.entries;

注意：社区版无真实网络栈，--url 只用于把 URL 拼进默认触发表达式；真请求/响应注入见
      scripts/network_bridge.py 与 references/network-and-eventloop.md。
"""

import argparse
import json
import os
import re
import sys
from collections import Counter

try:
    import iv8
except ImportError:
    sys.exit("未找到 iv8。先跑 scripts/preflight.py 确认安装（安装见 references/cross-platform-install.md）。")


# ---- 日志正则：匹配 iv8 debug 模式在 C++ 层打印的监控行 ----
ANSI = re.compile(r"\x1b\[[0-9;]*m")
RE_INST = re.compile(r"实例访问 - (.+?) -> (getter|setter|call|query)")
RE_REFL = re.compile(r"反射层 - (.+?) - 目标：([^\[\-]+)")
RE_MISS = re.compile(r"疑似缺失API - (\S+)")


def build_default_trigger(url):
    """没给 --trigger 时的兜底触发：发一次 XHR + drain + 读 netLog。

    drain 是「drain-before-read」纪律：社区版异步 XHR 回调不排空就读不到结果。
    完整事件循环推进语义见 references/network-and-eventloop.md。
    """
    if not url:
        # 纯加载即产签名的目标：不触发，只 drain 一轮微任务
        return "window.__iv8__.eventLoop.drain();"
    safe_url = json.dumps(url)
    return (
        "var __x = new XMLHttpRequest();"
        "__x.open('GET', %s, true);"
        "try { __x.send(null); } catch (e) {}"
        "window.__iv8__.eventLoop.drain();"
        "window.__iv8__.netLog.entries;" % safe_url
    )


def run_and_capture(js_path, trigger_src, env, log_path):
    """在 debug 模式下加载目标并触发一次，把 C++ 监控日志重定向到 log_path。"""
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    # fd1 + fd2 重定向到文件，捕获引擎层 debug 输出（Python print 也会进同一文件）
    saved_out, saved_err = os.dup(1), os.dup(2)
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    os.close(fd)
    try:
        # mode='debug' 打开 API 监控；environment 只放 JS 可观测画像（可含数组）
        with iv8.JSContext(environment=env, mode="debug") as ctx:
            ctx.eval(js, name=os.path.basename(js_path))
            if trigger_src:
                ctx.eval(trigger_src, name="__trigger__")
    finally:
        os.dup2(saved_out, 1)
        os.dup2(saved_err, 2)
        os.close(saved_out)
        os.close(saved_err)


def parse_log(log_path):
    """解析监控日志，返回六个 Counter。"""
    reads, writes, calls, queries, refl, missing = (Counter() for _ in range(6))
    total = 0
    with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = ANSI.sub("", raw)
            total += 1
            m = RE_INST.search(line)
            if m:
                api, kind = m.group(1).strip(), m.group(2)
                if "__iv8__" in api:  # 工具对象自身不算目标行为
                    continue
                {"getter": reads, "setter": writes,
                 "call": calls, "query": queries}[kind][api] += 1
                continue
            m = RE_REFL.search(line)
            if m:
                refl[f"{m.group(1).strip()} → {m.group(2).strip()}"] += 1
                continue
            m = RE_MISS.search(line)
            if m:
                missing[m.group(1)] += 1
    return total, reads, writes, calls, queries, refl, missing


def show(title, counter, top):
    print(f"\n{'=' * 72}\n{title}\n  去重 {len(counter)} / 命中 {sum(counter.values())}\n{'=' * 72}")
    for k, v in counter.most_common(top):
        print(f"  {v:6d}  {k}")


def main():
    ap = argparse.ArgumentParser(description="iv8 debug 监控：跑目标 JS，六类打印 API 访问链路")
    ap.add_argument("js_path", help="目标 JS 文件路径")
    ap.add_argument("--url", default="", help="触发用 URL（拼进默认 XHR 触发表达式）")
    ap.add_argument("--trigger", default="", help="触发 JS 表达式文件路径（覆盖默认触发）")
    ap.add_argument("--env", default="", help="environment 画像 JSON 文件路径（省略=零配跑）")
    ap.add_argument("--log", default="", help="监控日志落盘路径（默认 <js>.monitor.log）")
    args = ap.parse_args()

    if not os.path.isfile(args.js_path):
        sys.exit(f"目标 JS 不存在: {args.js_path}")

    env = None
    if args.env:
        with open(args.env, "r", encoding="utf-8") as f:
            env = json.load(f)

    if args.trigger:
        with open(args.trigger, "r", encoding="utf-8") as f:
            trigger_src = f.read()
    else:
        trigger_src = build_default_trigger(args.url)

    log_path = args.log or (args.js_path + ".monitor.log")

    run_and_capture(args.js_path, trigger_src, env, log_path)
    total, reads, writes, calls, queries, refl, missing = parse_log(log_path)

    print(f"\n日志总行数: {total}  (原始: {log_path})")
    show("① 属性读 getter —— 目标读了哪些字段（→ environment 配值清单来源）", reads, 60)
    show("② 属性写 setter —— 目标改/挂了什么（常见 XHR.open / fetch hook）", writes, 30)
    show("③ 方法调用 call —— 目标调了哪些 API", calls, 40)
    show("④ 存在性探测 query（typeof / in，反爬最爱）", queries, 40)
    show("⑤ 反射层 —— Object.keys / getOwnPropertyDescriptor / toString / JSON.*", refl, 30)
    show("⑥ ⚠ 疑似缺失 API（目标摸了但 iv8 未实现）", missing, 80)
    print(
        "\n[⑥ 处置纪律] 默认按陷阱处理，除非真机核对确有值。\n"
        "  绝不无脑补的探测物（process/_phantom/__webdriver_script_fn/StyleMedia/Float16Array 等）\n"
        "  见 references/trap-blacklist.md；三态与补漏原则见 references/patching-principles.md。\n"
        "[下一步] ① 读到的字段 → scripts/defaults_audit.py 求交集算真正要配的；\n"
        "        抛 TypeError 的 stub 窟窿 → scripts/reproduce_stub_error.py。"
    )


if __name__ == "__main__":
    main()
