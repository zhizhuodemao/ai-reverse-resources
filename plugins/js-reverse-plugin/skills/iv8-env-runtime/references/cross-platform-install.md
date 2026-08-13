# 跨平台安装（cross-platform-install）

> iv8 是**二进制编译扩展**（C++ V8，.so/.pyd），wheel 的平台 tag（cpXX / manylinux/macosx / 架构）
> 必须与你的 Python 精确匹配，不跨平台。安装前先跑 **scripts/preflight.py**——它硬门控平台/Python/架构，
> 装错组合直接阻断并打印实测已装版本（版本单一真相源，version-gotchas 消费它）。
> 项目强制用 **uv** 管理（见 CLAUDE.md）。

---

## 平台矩阵（唯一权威分发路径）

| 平台 / 架构 | 分发渠道 | Python | 装法 | 状态 |
|---|---|---|---|---|
| **Windows x64** | PyPI | 3.9 – 3.14 | `uv pip install iv8` | 正式 |
| **Linux x64** | PyPI（manylinux 标准编译） | 3.9 – 3.14 | `uv pip install iv8` | 正式，CentOS/Ubuntu/Debian/Fedora 通用 |
| **Linux aarch64（arm64）** | 查 PyPI 有无 manylinux aarch64 wheel | 3.9 – 3.14 | 有则 `uv pip install iv8`；**无则暂无路** | 待查，不保证 |
| **macOS Apple Silicon（arm64）** | **GitHub Releases（不上 PyPI）** | 3.11 – 3.14 / macOS 14+ | 下 wheel → `uv pip install ./…whl` | **实验/灰度** |
| **Intel Mac（x86_64）** | 无 | — | — | **不支持**（阻断，转替代） |
| **macOS + Python <3.11** | 无 | — | — | **不支持**（阻断，转替代） |

> **为什么 macOS 走 Releases 不走 PyPI**：作者无 macOS 设备无法长期实测，arm64 版为社区实验/灰度性质
> （已通过离线 API 综合自测 173/173），刻意不发布到 PyPI。所以 macOS 上 `pip install iv8` **必然装不到**，
> 只能从 Releases 拿对应 wheel。

---

## Windows x64 / Linux x64（PyPI 正式版）

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python iv8 requests
```

- 建议 PyPI 官方源；部分第三方镜像同步延迟，可能取不到最新版。
- `requests` 一并装：社区版无网络栈，案例发真包靠它（见 references/network-and-eventloop.md）。

---

## Linux aarch64（先查 wheel 是否可得）

```bash
# 探测 PyPI 是否为 aarch64 提供 manylinux wheel（不下载，只看有没有匹配文件）
uv pip install --python .venv/bin/python --no-deps --dry-run iv8
```

- 若解析到 `manylinux*_aarch64` wheel → 正常 `uv pip install iv8 requests`。
- 若报"no matching distribution / 只有 x86_64 wheel" → **当前暂无 aarch64 路**。不要硬装 x64 wheel（架构不符必然
  `import iv8` 崩）。明确告知用户此平台暂不支持，转 references/version-gotchas.md E7 提到的真机 CDP 路线或换 x64/Windows 机器。

---

## macOS Apple Silicon（arm64 实验版，GitHub Releases）

wheel 文件名**三段必须精确匹配**（二进制扩展不跨平台）：`cp311`(Py3.11) / `macosx_14_0`(macOS14+) / `arm64`(Apple Silicon)。
版本号、cpXX 以 Releases 页实际文件为准（**仅示例，运行时解析，勿写死某个版本**）。

```bash
# ① 建独立 venv（uv，遵 CLAUDE.md，不污染系统 Python / 不与现有逆向项目依赖打架）
uv venv --python 3.11 .venv

# ② 装本地 wheel + requests。uv pip install 既支持本地路径，也支持直接喂 Releases URL：
#    路径法（先 curl -L 下到本地再装）
uv pip install --python .venv/bin/python ./iv8-0.1.3-cp311-cp311-macosx_14_0_arm64.whl requests
#    URL 法（省去 curl，让 uv 直接拉）
uv pip install --python .venv/bin/python \
  "https://github.com/HanZzzzz000/iv8/releases/download/v0.1.3/iv8-0.1.3-cp311-cp311-macosx_14_0_arm64.whl" requests
```

- Python 必须 3.11–3.14 且 macOS 14+，否则 wheel tag 不匹配装不上。
- 装反 wheel（如把 cp312 装进 3.11 venv）→ `uv pip install` 会直接拒绝 tag 不符，属预期阻断，不是 bug。

---

## Intel Mac / macOS Python <3.11（阻断 + 替代）

无可用 wheel。preflight 检出后**直接阻断**，别尝试编译或硬装。替代路：

- 换 Apple Silicon 机 / 升到 Python 3.11+（若是 Intel Mac 则升 Python 也无用，仍无 x86_64 macOS wheel）。
- 换 Windows x64 / Linux x64 机器走 PyPI 正式版。
- 若只差临门一脚的物理量指纹（字体/audio），走真机 CDP 路线（见 references/version-gotchas.md E7），不依赖本机装 iv8。

---

## 验证：import iv8 冒烟测试

装完必跑（preflight.py 已内置这套断言）：

```bash
.venv/bin/python -c "import iv8; \
print('iv8', iv8.__version__ if hasattr(iv8,'__version__') else '(no __version__)'); \
import iv8 as I; ctx=I.JSContext(); \
assert ctx.eval('1+2')==3; \
print('UA:', ctx.eval('navigator.userAgent')); \
print('webdriver:', ctx.eval('navigator.webdriver')); \
print('typeof document:', ctx.eval('typeof document')); \
ctx.close()"
```

预期：`1+2=3` / UA 为 Chrome/Windows 默认串 / `navigator.webdriver=False` / `typeof document='object'`。
四项全绿 = iv8 在本平台完整可用，可进 P1。任一失败 → 回本文平台矩阵核对 wheel tag，别往下推进。

---

## 相关文件

- scripts/preflight.py — P0 硬门：平台/Python/架构校验 + 打印实测版本 + 冒烟断言（版本单一真相源）。
- references/version-gotchas.md — 各版本专坑门控，消费 preflight 打印的版本。
- references/network-and-eventloop.md — 为什么要一并装 requests（社区版无网络栈）。
