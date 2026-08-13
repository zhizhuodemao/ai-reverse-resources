#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_target.py — iv8 标准 runner（阶段 P3，内联 drain-before-read 断言）

用途：
  用最小的确定性流程把目标反爬 JS 在 iv8 里跑起来并收割签名/token：
    建 JSContext(environment=...) → 载入原始 JS → 求值入口表达式 → 收割结果。
  它把一条容易被忘、忘了就得到「空 netLog / 半成品 token」的铁律固化进代码：
    ★ 读取 netLog.entries / 任何异步产物之前，必须先 eventLoop.drain() 推进事件循环。
  本脚本用 _read_netlog() 包装强制「先 drain 再读」，任何绕过它直接读 netLog
  的写法在本 runner 里会被断言拦下。

  deploy 绑定值（aid / script id / bdms 版本 / u 数组 / golden sum 等）一律不写死，
  全部从函数参数或外部文件传入，运行时解析。

用法（库调用，推荐）：
    from run_target import run
    result = run(
        target_js_path="target.js",
        environment={...},          # 见 assets/env_starter.py 起手模板
        entry_expr="window.getSign('/api/x')",   # P1 定位到的真实生成入口
        need_network=False,
    )
    # result = {"value": <入口返回值>, "netlog": [...已 drain 后的请求...]}

用法（命令行）：
    python3 scripts/run_target.py target.js env.json "window.getSign('/api/x')"

本文件属于 iv8-env-runtime skill。
交叉引用：
  - 入口表达式 entry_expr 怎么定位见 references/part1-entry-location.md；
  - environment 该配什么见 references/config-defaults-cheatsheet.md 与
    assets/env_starter.py；
  - stub 窟窿（MessageChannel/Worker 等）的 iv8 原生替换契约见
    references/patching-principles.md；
  - 真实网络桥接（need_network=True 的四步握手）见 scripts/network_bridge.py。
"""

import json
import sys


class DrainError(RuntimeError):
    """未先 drain 事件循环就读取异步产物时抛出。"""


def _new_context(environment, config=None, time_mode="logical"):
    """创建一个最小配置的 JSContext。import 失败给清晰指引（先跑 preflight）。"""
    try:
        import iv8
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            "import iv8 失败：{}；请先跑 scripts/preflight.py 确认 P0 环境就绪。".format(e))
    return iv8.JSContext(environment=environment or {}, config=config or None,
                         time_mode=time_mode)


def _read_netlog(ctx, drained_flag):
    """★ 唯一允许的 netLog 读取通道：调用前必须已 drain。

    drained_flag 是一个单元素 list（可变引用），run() 在调用 drain 后置 True。
    若为 False 直接读 netLog，抛 DrainError —— 把「先 drain 再读」变成硬约束，
    而不是一句注释里的提醒。
    """
    if not drained_flag[0]:
        raise DrainError(
            "读取 netLog.entries 之前未调用 eventLoop.drain()：异步 XHR/fetch 可能尚未落账，"
            "会读到空或半成品。请先 ctx.eval(\"window.__iv8__.eventLoop.drain()\") 再读。")
    return ctx.eval("window.__iv8__.netLog.entries", to_py=True)


def run(target_js_path, environment, entry_expr,
        need_network=False, config=None, time_mode="logical",
        stub_setup_js=None, drain_max=None):
    """跑目标 JS 并收割结果。

    参数：
      target_js_path : 原始目标 JS 文件路径（未改写）。
      environment    : iv8 画像 dict（location.href 通常必配，默认 about:blank）。
      entry_expr     : P1 定位到的真实「生成」入口表达式，其返回值即要收割的产物。
      need_network   : 目标是否会发真实请求。社区版无真实网络栈，True 时请改用
                       scripts/network_bridge.py 的桥接流程；这里仅收 netLog 便于观察。
      config         : 引擎行为标量（timezone/permissions.* 等），可选。
      time_mode      : 'logical'（默认）或 'system'（POW/时间差校验时用）。
      stub_setup_js  : 可选，载入目标前先注入的 stub 替换/wrapNative 补丁 JS 字符串。
                       补丁应依据目标证据最小实现；本 runner 不内置固定清单。
      drain_max      : 传给 eventLoop.drain(max) 的上限，None=排空全部已到期任务。

    返回：
      {"value": <entry_expr 求值结果>, "netlog": [...]}
    """
    with open(target_js_path, "r", encoding="utf-8") as f:
        js_code = f.read()

    drained_flag = [False]  # 可变引用，drain 后置 True，给 _read_netlog 做硬断言
    ctx = _new_context(environment, config=config, time_mode=time_mode)
    try:
        # 1) 载入目标之前先打有证据的最小 stub 补丁（如 MessageChannel/Worker 替换）
        if stub_setup_js:
            ctx.eval(stub_setup_js, name="stub_setup")

        # 2) 载入原始目标 JS（不改写）
        ctx.eval(js_code, name=target_js_path)

        # 3) 求值真实生成入口，拿返回值
        value = ctx.eval(entry_expr, name="entry_expr", to_py=True)

        # 4) ★ 读任何异步产物（netLog）之前，强制 drain 推进事件循环
        if drain_max is None:
            ctx.eval("window.__iv8__.eventLoop.drain()")
        else:
            ctx.eval("window.__iv8__.eventLoop.drain({})".format(int(drain_max)))
        drained_flag[0] = True

        netlog = _read_netlog(ctx, drained_flag)

        return {"value": value, "netlog": netlog}
    finally:
        try:
            ctx.close()
        except Exception:  # noqa: BLE001 —— 关闭失败不应掩盖主流程结果
            pass


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main(argv):
    if len(argv) < 4:
        print('用法：python3 run_target.py target.js env.json "<entry_expr>"', file=sys.stderr)
        return 2
    target_js = argv[1]
    environment = _load_json(argv[2])
    entry_expr = argv[3]

    result = run(target_js, environment, entry_expr)
    print("[run_target] 入口返回值：")
    print(json.dumps(result["value"], ensure_ascii=False, indent=2, default=str))
    print("[run_target] netLog 条目数（已 drain）：{}".format(len(result["netlog"])))
    for e in result["netlog"]:
        if isinstance(e, dict):
            print("  {} {}".format(e.get("method", ""), e.get("url", "")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
