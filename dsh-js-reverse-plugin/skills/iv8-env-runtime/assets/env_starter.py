#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
env_starter.py — iv8 environment 起手模板（阶段 P2 零配起手）

用途：
  给一个「最小可跑」的 environment 起手 dict，只填几乎必配的两项：
    - location 全字段（iv8 默认 location.href 是 about:blank，几乎必须覆盖成真实页面 URL）；
    - navigator.userAgent（对外浏览器版本由它决定）。
  canvas / webgl / DOM / screen 等一律「看站再加，别一次补全」——
  P2 的做法是先零配跑、用 monitor∩defaults 交集找出真正被读到的字段，再按需补，
  过度预配反而制造不一致红线。

用法：
    from env_starter import make_environment
    env = make_environment(
        href="https://www.example.com/path?x=1",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
    )
    # 交给 scripts/consistency_lint.py 体检后再喂 iv8.JSContext(environment=env)

本文件属于 iv8-env-runtime skill。
交叉引用：
  - 字段归属与默认值见 references/config-defaults-cheatsheet.md；
  - 一致性红线（UA↔platform↔时区↔语言↔webgl）先跑 scripts/consistency_lint.py；
  - canvas/webgl 等指纹值必须来自真实浏览器证据，并通过 iv8 environment/config 注入。
说明：下方所有具体值均为「仅示例」占位，真实站点请按 P1/P2 观测到的真机值替换。
"""

try:  # 仅用于类型/URL 解析，缺失也不影响 make_environment 被直接改字段字典使用
    from urllib.parse import urlsplit
except Exception:  # noqa: BLE001
    urlsplit = None


def _split_location(href):
    """把一个页面 URL 拆成 iv8 location 各字段。href 是 location 里最关键的一项。"""
    if urlsplit is None:
        # 极简兜底：至少把 href 填上，其余留空由调用方补
        return {"href": href, "origin": "", "protocol": "", "host": "",
                "hostname": "", "port": "", "pathname": "", "search": "", "hash": ""}
    u = urlsplit(href)
    origin = "{}://{}".format(u.scheme, u.netloc) if u.scheme and u.netloc else ""
    return {
        "href": href,
        "origin": origin,
        "protocol": (u.scheme + ":") if u.scheme else "",
        "host": u.netloc,
        "hostname": u.hostname or "",
        "port": str(u.port) if u.port else "",
        "pathname": u.path or "",
        "search": ("?" + u.query) if u.query else "",
        "hash": ("#" + u.fragment) if u.fragment else "",
    }


def make_environment(href, user_agent, language="en-US", languages=None):
    """构造起手 environment。只配必需项；其余看站再加。

    参数：
      href       : 真实页面 URL（必配；iv8 默认 about:blank 几乎总要覆盖）。
      user_agent : navigator.userAgent（必配；决定对外浏览器版本）。
      language / languages : 语言，注意 language 应是 languages[0]（红线，见 consistency_lint）。
    """
    if languages is None:
        languages = [language, "en"]
    return {
        # ★ 必配：location 默认 about:blank，站点脚本读 location.* 时必须是真实页面
        "location": _split_location(href),
        # ★ 必配：navigator.userAgent 决定对外浏览器版本；其余 navigator 字段有 200+ 默认值，
        #   通常只需覆盖 UA（以及和 UA 自洽的 language/languages）。
        "navigator": {
            "userAgent": user_agent,
            "language": language,
            "languages": languages,
        },
        # 以下为「看站再加」示例，默认注释掉——不要一次补全，过度预配会制造不一致红线：
        #   canvas 站点必配 canvas.fingerprint.toDataURL.png（默认 ''）：
        # "canvas": {"fingerprint": {"toDataURL": {"png": "<真机抓的 dataURL,仅示例,勿写死>"}}},
        #   webgl 指纹（须与 UA 显卡语义自洽）：
        # "webgl": {"vendor": "Google Inc. (NVIDIA)",
        #           "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 ...)"},
        #   屏幕：
        # "screen": {"width": 1920, "height": 1080, "colorDepth": 24},
    }


# 一个可直接参考/拷贝的示例实例（值均为占位，真实站点务必替换）。
STARTER_ENVIRONMENT_EXAMPLE = make_environment(
    href="https://www.example.com/page",  # 仅示例
    user_agent=(  # 仅示例，按真机替换
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
)


if __name__ == "__main__":
    import json
    print(json.dumps(STARTER_ENVIRONMENT_EXAMPLE, ensure_ascii=False, indent=2))
