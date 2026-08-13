#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""parity_check.py —— P4 验收对账：iv8 产物 vs 真机产物，逐字符/逐字段找首个差异。

作用（对应 SKILL.md 的 P4「parity 对账 + 服务器判决唯一真相」）：
    把「iv8 补环境跑出来的签名/token」和「真实浏览器抓到的同场景签名/token」放一起，
    逐字符（或逐字段，若是 JSON/query-string）对比，定位第一个不一致的位置，
    帮你把「补环境哪里还没对齐」收窄到具体字段。

    ⚠ 铁律（本 skill 的验收真相层）：
      本地一致只是「必要不充分」条件。parity 全绿也不代表过盾——
      很多签名含时间戳/随机盐，本来就该逐次不同；对账目的是排查「结构性字段」对齐，
      不是要求整串相等。**唯一的最终真相是把 iv8 产物发到目标服务器，看它判 200 / code=0。**
      算出来被服务器拒 → 回 P3 继续补环境；返回 403（风控/IP/频率）→ 不是环境问题，别在补环境里空转。
      服务器判决怎么读见 references/part2-discovery.md。

对账模式（自动判定，也可 --mode 强制）：
    - raw   ：整串逐字符对比，报首个差异下标 + 两侧上下文窗口
    - kv    ：query-string（a=1&b=2）逐键对比，报缺键/多键/值不同
    - json  ：JSON 逐字段递归对比，报首个路径差异

关系与边界：
    - 上游：iv8 产物来自 assets/env_starter.py 跑出的签名；真机产物来自 js-reverse MCP
            或真实浏览器抓包（找入口/抓真机产物见 references/part1-entry-location.md）。
    - 本脚本只做「本地一致性」这一必要条件；充分条件（服务器判决）由你手动发包核对。

用法：
    python parity_check.py <iv8产物> <真机产物> [--mode raw|kv|json] [--file]
      默认两个位置参数是「值本身」；加 --file 则当作文件路径读取内容。
      示例：
        python parity_check.py "a_bogus=xxx" "a_bogus=yyy"
        python parity_check.py iv8_out.txt real_out.txt --file
        python parity_check.py iv8.json real.json --file --mode json
"""

import argparse
import json
import sys
from urllib.parse import parse_qsl


def _read(value, is_file):
    if not is_file:
        return value
    with open(value, "r", encoding="utf-8") as f:
        return f.read().strip()


def guess_mode(a, b):
    """自动判定对账模式。"""
    for s in (a, b):
        t = s.strip()
        if t[:1] in "{[":
            try:
                json.loads(t)
                return "json"
            except ValueError:
                pass
    if ("=" in a and ("&" in a or "&" in b)) or ("=" in a and "=" in b and " " not in a):
        return "kv"
    return "raw"


def check_raw(a, b):
    """逐字符对比，返回 (是否一致, 报告文本)。"""
    if a == b:
        return True, f"完全一致（长度 {len(a)}）"
    n = min(len(a), len(b))
    idx = next((i for i in range(n) if a[i] != b[i]), n)
    lo = max(0, idx - 20)
    win_a = a[lo:idx + 20]
    win_b = b[lo:idx + 20]
    report = [
        f"首个差异位置: 下标 {idx}（长度 iv8={len(a)} / 真机={len(b)}）",
        f"  iv8 : ...{win_a!r}",
        f"  真机: ...{win_b!r}",
    ]
    if idx < n:
        report.append(f"  差异字符: iv8={a[idx]!r}  真机={b[idx]!r}")
    else:
        longer = "iv8" if len(a) > len(b) else "真机"
        report.append(f"  前 {idx} 字符相同，{longer} 更长（尾部多出内容）")
    return False, "\n".join(report)


def check_kv(a, b):
    """query-string 逐键对比。"""
    da = dict(parse_qsl(a, keep_blank_values=True))
    db = dict(parse_qsl(b, keep_blank_values=True))
    keys = list(dict.fromkeys(list(da) + list(db)))
    diffs = []
    for k in keys:
        if k not in da:
            diffs.append(f"  [多键] 真机有、iv8 缺: {k}={db[k]!r}")
        elif k not in db:
            diffs.append(f"  [缺键] iv8 有、真机缺: {k}={da[k]!r}")
        elif da[k] != db[k]:
            diffs.append(f"  [值异] {k}: iv8={da[k]!r}  真机={db[k]!r}")
    if not diffs:
        return True, f"所有键值一致（共 {len(keys)} 键）"
    return False, f"共 {len(diffs)} 处键差异:\n" + "\n".join(diffs)


def _first_json_diff(a, b, path="$"):
    """递归找 JSON 首个字段差异，返回路径描述或 None。"""
    if type(a) is not type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        return f"{path}: 类型不同 iv8={type(a).__name__} 真机={type(b).__name__}"
    if isinstance(a, dict):
        for k in dict.fromkeys(list(a) + list(b)):
            if k not in a:
                return f"{path}.{k}: iv8 缺此键（真机={b[k]!r}）"
            if k not in b:
                return f"{path}.{k}: 真机缺此键（iv8={a[k]!r}）"
            d = _first_json_diff(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: 数组长度不同 iv8={len(a)} 真机={len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = _first_json_diff(x, y, f"{path}[{i}]")
            if d:
                return d
        return None
    if a != b:
        return f"{path}: 值不同 iv8={a!r} 真机={b!r}"
    return None


def check_json(a, b):
    try:
        ja, jb = json.loads(a), json.loads(b)
    except ValueError as e:
        return False, f"JSON 解析失败: {e}（改用 --mode raw）"
    diff = _first_json_diff(ja, jb)
    if diff is None:
        return True, "所有字段一致"
    return False, "首个字段差异:\n  " + diff


def main():
    ap = argparse.ArgumentParser(description="iv8 产物 vs 真机产物 对账；服务器判决才是最终真相")
    ap.add_argument("iv8_value", help="iv8 补环境产物（值，或加 --file 传路径）")
    ap.add_argument("real_value", help="真机产物（值，或加 --file 传路径）")
    ap.add_argument("--mode", choices=["raw", "kv", "json"], default="auto", help="对账模式（默认自动判定）")
    ap.add_argument("--file", action="store_true", help="把两个位置参数当作文件路径读取")
    args = ap.parse_args()

    a = _read(args.iv8_value, args.file)
    b = _read(args.real_value, args.file)

    mode = args.mode if args.mode != "auto" else guess_mode(a, b)
    print(f"对账模式: {mode}\n")

    ok, report = {"raw": check_raw, "kv": check_kv, "json": check_json}[mode](a, b)
    print(report)

    print("\n" + "=" * 72)
    if ok:
        print("本地对账: 一致 ✓（必要条件满足）")
    else:
        print("本地对账: 不一致 ✗ → 回 P3 补环境（对准差异字段）")
    print(
        "⚠ 本地一致只是必要不充分。最终真相 = 把 iv8 产物发到目标服务器看判决:\n"
        "   服务器 200 / code=0 才算翻过；被拒→回 P3；403（风控/IP/频率）→ 非环境问题。\n"
        "   （含时间戳/随机盐的签名本就逐次不同，对账看结构性字段而非整串相等。）\n"
        "   服务器判决怎么读见 references/part2-discovery.md。"
    )
    # 退出码：本地一致 0 / 不一致 1（便于脚本串联），但仍以服务器判决为准
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
