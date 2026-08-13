#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preflight.py — iv8 环境就绪硬前置门（阶段 P0）

用途：
  在做任何补环境工作之前，先跑这一步。它按当前平台/架构/Python 版本判定
  iv8 能否安装与运行，装错平台或版本直接硬阻断（sys.exit 非 0），并在成功时
  打印已安装的 iv8.__version__ —— 这个版本号是「单一真相源」，
  references/version-gotchas.md 的所有版本门控（E1 btoa、E2 MessageChannel、
  E4 WASM 等）都以此处打印的实测版本为准，不要凭记忆判断。

用法：
  python3 scripts/preflight.py
  退出码 0 = 环境就绪；非 0 = 阻断（终端会打印具体原因与修复指引）。

约束（来自 iv8 README，实测 0.1.3）：
  - Windows x64 / Linux x86_64：pip 官方源可装（PyPI，Python 3.9–3.14）。
  - Linux aarch64：需自查 manylinux aarch64 wheel 是否可得。
  - macOS 仅 Apple Silicon(arm64) 实验版，不上 PyPI，去 GitHub Releases 下 wheel。
    支持 Python 3.11–3.14、macOS 14+。Intel Mac 或 Py<3.11 一律不支持。
  - 项目强制用 uv 管理依赖（见 CLAUDE.md）。

本文件属于 iv8-env-runtime skill。
交叉引用：安装细节见 references/cross-platform-install.md；
         版本坑门控见 references/version-gotchas.md（消费本脚本打印的版本号）。
"""

import platform
import sys

GH_RELEASES = "https://github.com/HanZzzzz000/iv8/releases"


def _py_tag():
    """把 3.11 -> 'cp311'，供拼 macOS wheel 名用。"""
    return "cp{}{}".format(sys.version_info.major, sys.version_info.minor)


def _fail(msg):
    """打印阻断原因并以非 0 退出。"""
    print("\n[preflight][阻断] " + msg, file=sys.stderr)
    sys.exit(2)


def _guide_install():
    """按平台/架构/Python 版本给出安装指引；不支持的组合直接 _fail。

    返回 True 表示「本平台应当已经能 import iv8」（走 PyPI 或已下载的 wheel），
    仅用于决定后续冒烟测试的措辞。
    """
    system = platform.system()
    machine = platform.machine().lower()
    py = sys.version_info

    print("[preflight] 平台检测：system={} machine={} python={}.{}.{}".format(
        system, machine, py.major, py.minor, py.micro))

    # ---- Windows ----
    if system == "Windows":
        if machine not in ("amd64", "x86_64"):
            _fail("Windows 仅支持 x64（当前 machine={}），无预编译 wheel。".format(machine))
        if not (3, 9) <= (py.major, py.minor) <= (3, 14):
            _fail("iv8 支持 Python 3.9–3.14，当前 {}.{} 不在范围内。".format(py.major, py.minor))
        print("[preflight] Windows x64：uv pip install iv8   （PyPI 官方源）")
        return True

    # ---- Linux ----
    if system == "Linux":
        if machine in ("x86_64", "amd64"):
            if not (3, 9) <= (py.major, py.minor) <= (3, 14):
                _fail("iv8 支持 Python 3.9–3.14，当前 {}.{} 不在范围内。".format(py.major, py.minor))
            print("[preflight] Linux x86_64：uv pip install iv8   （PyPI，manylinux）")
            return True
        if machine in ("aarch64", "arm64"):
            # aarch64 wheel 是否发布随版本变化，不写死结论，交给用户核对。
            print("[preflight] Linux aarch64：README 明确的官方轮子是 x64 manylinux。")
            print("            请自查 PyPI/Releases 是否提供 manylinux aarch64 wheel：")
            print("              uv pip install iv8   # 若报 no matching distribution 即无 aarch64 轮")
            print("            若确无 aarch64 wheel，则当前架构暂无本地安装路径。")
            return False
        _fail("Linux 未知架构 machine={}，无对应 wheel。".format(machine))

    # ---- macOS ----
    if system == "Darwin":
        if machine != "arm64":
            _fail("macOS 仅支持 Apple Silicon(arm64) 实验版；当前 machine={}（Intel Mac 不支持）。".format(machine))
        if not (3, 11) <= (py.major, py.minor) <= (3, 14):
            _fail("macOS 实验版仅支持 Python 3.11–3.14（且需 macOS 14+）；当前 {}.{} 不支持。".format(
                py.major, py.minor))
        tag = _py_tag()
        wheel = "iv8-<ver>-{tag}-{tag}-macosx_14_0_arm64.whl".format(tag=tag)
        print("[preflight] macOS Apple Silicon 实验版（不上 PyPI）：")
        print("            1) 去 GitHub Releases 下载对应 wheel：{}".format(GH_RELEASES))
        print("               文件名形如（<ver> 用实际版本替换，勿写死）：{}".format(wheel))
        print("            2) 用 uv 安装：uv pip install ./{}".format(wheel))
        return False  # 是否已装取决于用户是否下载过，冒烟测试会给出真实结论

    _fail("未识别的操作系统 system={}。".format(system))


def _smoke():
    """import iv8 冒烟：ctx.eval('1+1')==2 且 navigator.webdriver==False，并打印版本号。"""
    try:
        import iv8
    except Exception as e:  # noqa: BLE001 —— 需要把任何导入失败都转成清晰指引
        _fail("import iv8 失败：{}\n"
              "  说明 iv8 尚未安装或安装的 wheel 与当前平台/Python 不匹配。\n"
              "  按上方安装指引用 uv 安装对应 wheel 后重跑本脚本。".format(e))

    version = getattr(iv8, "__version__", "<未知>")

    try:
        with iv8.JSContext() as ctx:
            one_plus_one = ctx.eval("1 + 1")
            webdriver = ctx.eval("navigator.webdriver")
    except Exception as e:  # noqa: BLE001
        _fail("iv8 已导入但 JSContext 冒烟失败：{}".format(e))

    if one_plus_one != 2:
        _fail("冒烟异常：ctx.eval('1 + 1') 返回 {!r}（应为 2）。".format(one_plus_one))
    if webdriver is not False:
        _fail("冒烟异常：navigator.webdriver 返回 {!r}（应为 False）。".format(webdriver))

    # ★ 单一真相源：把实测版本号打印出来，供 version-gotchas 门控消费。
    print("\n[preflight][通过] iv8 冒烟成功。")
    print("[preflight] iv8.__version__ = {}".format(version))
    print("[preflight] ↑ 该版本号是版本门控唯一真相；references/version-gotchas.md")
    print("            按此判断 E1(btoa)/E2(MessageChannel)/E4(WASM) 等坑是否已修，勿凭记忆。")
    return version


def main():
    print("=" * 64)
    print("iv8-env-runtime · P0 preflight（环境就绪硬前置门）")
    print("=" * 64)
    _guide_install()
    _smoke()
    print("\n[preflight] P0 通过，可进入 P1（找入口）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
