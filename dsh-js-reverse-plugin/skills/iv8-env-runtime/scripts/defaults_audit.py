#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""defaults_audit.py —— P2/P3 桥梁：审计 iv8 的 environment/config 默认值，算出「真正要配的清单」。

作用（对应 SKILL.md 的 P2「monitor∩defaults 交集=要配的清单」）：
    调 iv8.JSContext.get_defaults()（返回全部支持路径及默认值），做两件事：
      1) 按前缀分组（location / canvas / navigator / screen / webgl / window / document …）
         打印，并「标出空/占位默认」（''、about:blank、0.0 等）——这些是最可能需要覆盖的必配候选。
      2) 若给了「目标读过的字段清单」（monitor_env.py 第①类 getter 的输出），
         与 defaults 求交集 = 目标真正读到、且 iv8 有默认可覆盖的字段 = 真正要配的清单。

    典型默认坑（务必核对，见 references/config-defaults-cheatsheet.md）：
      - location.href 默认 'about:blank' —— 几乎必配（目标常读 origin/host/href 做校验）
      - canvas.fingerprint.toDataURL.png 默认 '' —— canvas 指纹站必配
      - navigator.* 已有 200+ 默认 —— 通常只需覆盖 userAgent（及联动字段）

    environment（画像，JS 可观测，可含数组）与 config（引擎行为，仅标量，无数组）是两条独立通道；
    本审计只帮定位「哪些默认是空壳需要填」，具体填什么值 / 一致性红线（UA↔platform↔时区↔语言↔webgl）
    见 references/config-defaults-cheatsheet.md 与 references/patching-principles.md。

关系与边界：
    - 上游：scripts/monitor_env.py 的①类 getter 清单是本脚本 --read-fields 的输入。
    - 下游：交集清单 → 填进 assets/env_starter.py 的 environment/config。
    - 一致性静态校验（填错值自动拒）见 scripts/consistency_lint.py。
    - 权威 API 契约见 references/iv8-api-contract.md。

用法：
    python defaults_audit.py                         # 全量分组 + 标空默认
    python defaults_audit.py --group navigator       # 只看某前缀
    python defaults_audit.py --empty-only            # 只列空/占位默认（必配候选）
    python defaults_audit.py --read-fields fields.txt  # 与目标读过的字段求交集
        fields.txt：每行一个字段路径，如 navigator.userAgent / location.href
        （可直接从 monitor_env.py 第①类输出里摘）
"""

import argparse
import sys

try:
    import iv8
except ImportError:
    sys.exit("未找到 iv8。先跑 scripts/preflight.py 确认安装（安装见 references/cross-platform-install.md）。")


# 视为「空/占位」的默认值 —— 命中即列为必配候选
_EMPTY_LITERALS = ("", "about:blank", "about://blank")


def is_empty_default(value):
    """判断一个默认值是否为空/占位（很可能需要覆盖）。"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() in _EMPTY_LITERALS
    return False


def group_of(path):
    """取路径的一级前缀作为分组名。"""
    return path.split(".", 1)[0] if "." in path else path


def load_read_fields(path):
    """读取目标读过的字段清单（每行一个路径，# 起始为注释）。"""
    fields = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            # 容忍 monitor 输出里带计数前缀，如 "   42  navigator.userAgent"
            token = s.split()[-1]
            fields.add(token)
    return fields


def main():
    ap = argparse.ArgumentParser(description="审计 iv8 默认值，定位必配候选 / 与目标读过字段求交集")
    ap.add_argument("--group", default="", help="只显示该一级前缀（如 navigator / webgl）")
    ap.add_argument("--empty-only", action="store_true", help="只列空/占位默认（必配候选）")
    ap.add_argument("--read-fields", default="", help="目标读过的字段清单文件，求交集")
    args = ap.parse_args()

    defaults = iv8.JSContext.get_defaults()
    print(f"iv8 get_defaults(): 共 {len(defaults)} 条支持路径\n")

    # ---- 分组 ----
    groups = {}
    for path in sorted(defaults):
        groups.setdefault(group_of(path), []).append(path)

    def emit(path):
        val = defaults[path]
        flag = "  ⚠必配候选(空/占位)" if is_empty_default(val) else ""
        print(f"    {path} = {val!r}{flag}")

    for gname in sorted(groups):
        if args.group and gname != args.group:
            continue
        rows = groups[gname]
        if args.empty_only:
            rows = [p for p in rows if is_empty_default(defaults[p])]
            if not rows:
                continue
        print(f"[{gname}]  ({len(rows)} 条)")
        for path in rows:
            emit(path)
        print()

    # ---- 与目标读过的字段求交集 ----
    if args.read_fields:
        read = load_read_fields(args.read_fields)
        default_paths = set(defaults)
        # 直接命中 + 前缀命中（目标读 navigator.userAgent，defaults 有该路径）
        hit = sorted(read & default_paths)
        # 目标读了但 defaults 里没有的路径 → 可能是缺失 API / 陷阱，走 trap 纪律
        miss = sorted(read - default_paths)

        print("=" * 72)
        print("交集（monitor∩defaults）= 目标读到且 iv8 有默认可覆盖 = 真正要配的清单")
        print("=" * 72)
        for path in hit:
            emit(path)
        if not hit:
            print("    （无交集：目标读的字段都不在 defaults 里，见下方 miss）")

        if miss:
            print("\n" + "-" * 72)
            print("⚠ 目标读了、但 defaults 无此路径 —— 可能是缺失 API / 反爬陷阱：")
            print("  默认按陷阱处理，除非真机核对确有值。见 references/trap-blacklist.md")
            print("-" * 72)
            for path in miss:
                print(f"    {path}")

    print(
        "\n[下一步] 交集清单填进 assets/env_starter.py 的 environment/config；\n"
        "        填的值做一致性静态校验 → scripts/consistency_lint.py；\n"
        "        值怎么填 / 一致性红线见 references/config-defaults-cheatsheet.md。"
    )


if __name__ == "__main__":
    main()
