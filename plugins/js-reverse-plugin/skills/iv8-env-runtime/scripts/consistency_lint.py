#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
consistency_lint.py — environment / config 静态拒错器（阶段 P2/P3 护栏）

用途：
  在把 environment / config 交给 iv8.JSContext 之前做静态体检，
  在「补环境跑起来」之前就拦掉四类会导致翻车却难查的错误：
    1) config 里出现数组值 —— iv8 的 config 只接标量（引擎行为，如 timezone/
       permissions.*），画像类字段（可数组、JS 可观测）必须放 environment。
    2) 画像字段（navigator/screen/webgl/canvas...）被误塞进 config。
    3) 一致性红线不自洽：UA 里的平台/OS ↔ navigator.platform ↔
       userAgentData.platform ↔ 语言 ↔ 时区 互相矛盾（反爬最常查的交叉项）。
    4) 检测到 POW/时间敏感特征线索，却没把 time_mode 设成 'system'（给告警）。

  本脚本只做静态判定，不会创建 JSContext，因此不需要装 iv8 即可运行。

用法（库调用，推荐）：
    from consistency_lint import lint
    problems = lint(environment, config, time_mode="logical")
    # problems 为字符串列表，空列表=通过

用法（命令行）：
    python3 scripts/consistency_lint.py env.json config.json [time_mode]
    退出码 0 = 无问题；非 0 = 有问题（逐条打印到 stderr）。

本文件属于 iv8-env-runtime skill。
交叉引用：environment/config 的字段归属与默认值见
         references/config-defaults-cheatsheet.md；
         一致性红线的完整清单见 references/iv8-api-contract.md。
"""

import json
import sys

# environment（画像）专属的顶层键；出现在 config 里即为错放。
_PROFILE_KEYS = {
    "navigator", "screen", "location", "webgl", "canvas",
    "document", "window", "history", "performance", "plugins",
    "userAgentData", "audio", "fonts",
}


def _is_array(v):
    return isinstance(v, (list, tuple))


def _walk_config_for_arrays(node, path, problems):
    """递归查 config 中的任何数组值。config 只接标量。"""
    if isinstance(node, dict):
        for k, v in node.items():
            _walk_config_for_arrays(v, "{}.{}".format(path, k) if path else str(k), problems)
    elif _is_array(node):
        problems.append(
            "[config-数组] config['{}'] 是数组，但 config 只接标量引擎行为值；"
            "画像/可数组字段请移到 environment。".format(path))


def _check_config_shape(config, problems):
    if not config:
        return
    if not isinstance(config, dict):
        problems.append("[config-类型] config 必须是 dict（当前 {}）。".format(type(config).__name__))
        return
    # 2) 画像字段误塞进 config
    for k in config:
        if k in _PROFILE_KEYS:
            problems.append(
                "[画像错放] config 里出现画像字段 '{}'，它属于 environment（JS 可观测）；"
                "config 只放引擎行为（timezone/permissions.* 等标量）。".format(k))
    # 1) config 数组值
    _walk_config_for_arrays(config, "", problems)


def _ua_platform_hint(ua):
    """从 UA 字符串粗判操作系统家族，返回 'windows'/'mac'/'linux'/'android'/None。"""
    if not ua:
        return None
    low = ua.lower()
    if "windows" in low or "win64" in low or "win32" in low:
        return "windows"
    if "android" in low:  # android 要先于 linux 判（UA 里两者都含 linux）
        return "android"
    if "mac os x" in low or "macintosh" in low:
        return "mac"
    if "linux" in low or "x11" in low:
        return "linux"
    return None


def _navigator_platform_family(platform_str):
    """navigator.platform -> OS 家族。"""
    if not platform_str:
        return None
    low = platform_str.lower()
    if "win" in low:
        return "windows"
    if "mac" in low:
        return "mac"
    if "linux" in low or "x11" in low:
        return "linux"
    if "android" in low or "arm" in low:
        return "android"
    return None


def _check_consistency_redline(env, problems):
    """一致性红线：UA↔platform↔userAgentData.platform↔语言↔时区 自洽。"""
    if not isinstance(env, dict):
        problems.append("[env-类型] environment 必须是 dict（当前 {}）。".format(type(env).__name__))
        return

    nav = env.get("navigator", {}) or {}
    ua = nav.get("userAgent")
    nav_platform = nav.get("platform")
    uad = nav.get("userAgentData", {}) or {}
    uad_platform = uad.get("platform")  # 形如 "Windows" / "macOS" / "Linux"

    ua_fam = _ua_platform_hint(ua)
    nav_fam = _navigator_platform_family(nav_platform)

    # UA 家族 vs navigator.platform 家族
    if ua_fam and nav_fam and ua_fam != nav_fam:
        problems.append(
            "[红线-OS] navigator.userAgent 指向 {}，但 navigator.platform='{}' 指向 {}，不自洽。"
            .format(ua_fam, nav_platform, nav_fam))

    # UA 家族 vs userAgentData.platform
    if ua_fam and uad_platform:
        uad_low = uad_platform.lower()
        uad_fam = ("windows" if "win" in uad_low else
                   "mac" if "mac" in uad_low else
                   "linux" if "linux" in uad_low else
                   "android" if "android" in uad_low else None)
        if uad_fam and uad_fam != ua_fam:
            problems.append(
                "[红线-OS] userAgent 指向 {}，但 userAgentData.platform='{}' 指向 {}，不自洽。"
                .format(ua_fam, uad_platform, uad_fam))

    # 语言：navigator.language 应是 navigator.languages 的首项
    language = nav.get("language")
    languages = nav.get("languages")
    if language and _is_array(languages) and languages:
        if languages[0] != language:
            problems.append(
                "[红线-语言] navigator.language='{}' 与 navigator.languages[0]='{}' 不一致。"
                .format(language, languages[0]))

    # 时区：environment 侧无标准时区字段，时区归 config.timezone。
    # 若 environment 里出现类时区键，提示挪到 config。
    for k in env:
        if "timezone" in str(k).lower():
            problems.append(
                "[红线-时区] environment 里出现 '{}'；时区属于 config.timezone（引擎行为），"
                "请挪到 config，并确保与语言/UA 地区自洽。".format(k))


def _detect_time_sensitive(env, config):
    """粗测是否有 POW/时间差校验线索。返回命中的线索列表。"""
    hints = []
    blob = json.dumps({"env": env, "config": config}, ensure_ascii=False).lower()
    for kw in ("pow", "proof_of_work", "proofofwork", "hashcash", "nonce", "difficulty"):
        if kw in blob:
            hints.append(kw)
    return hints


def lint(environment, config=None, time_mode="logical"):
    """静态体检，返回问题字符串列表（空=通过）。不创建 JSContext。"""
    problems = []
    _check_config_shape(config, problems)
    _check_consistency_redline(environment or {}, problems)

    # 4) 时间敏感却未用 system 时间 —— 告警（不算硬错，但要提示）。
    hints = _detect_time_sensitive(environment or {}, config or {})
    if hints and time_mode != "system":
        problems.append(
            "[告警-时间] 检测到疑似 POW/时间差线索 {}，但 time_mode='{}'。"
            "POW/时间差校验应改用 time_mode='system'（否则 Date.now 不反映真实耗时）。"
            .format(hints, time_mode))

    return problems


def _load_json(path):
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main(argv):
    if len(argv) < 2:
        print("用法：python3 consistency_lint.py env.json [config.json] [time_mode]", file=sys.stderr)
        return 2
    env = _load_json(argv[1])
    config = _load_json(argv[2]) if len(argv) >= 3 else {}
    time_mode = argv[3] if len(argv) >= 4 else "logical"

    problems = lint(env, config, time_mode=time_mode)
    if not problems:
        print("[consistency_lint][通过] environment/config 静态体检无问题。")
        return 0
    print("[consistency_lint][不通过] 发现 {} 个问题：".format(len(problems)), file=sys.stderr)
    for p in problems:
        print("  - " + p, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
