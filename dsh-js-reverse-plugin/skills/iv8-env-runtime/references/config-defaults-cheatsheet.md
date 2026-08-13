# get_defaults() 导航 · 默认值体检表 —— 配不配值

> 服务于 **P2 发现 / P3 配环境**。核心问题：目标读的某个字段，iv8 默认是不是占位（about:blank/空）——占位就必须配真值。
> `iv8.JSContext.get_defaults()` 实测返回 **393 路径**；本页教你怎么在这 393 条里导航，而不是逐条背。
> 拉全量清单用 `scripts/defaults_audit.py`。

---

## 0. 先分清：environment 还是 config

| 桶 | 放什么 | 能不能放数组 | 例子 |
|---|---|---|---|
| **environment** | **画像**：JS 可观测的指纹值 | **可以**（languages/brands 等） | navigator / screen / location / webgl / canvas / document 内容 |
| **config** | **引擎行为**：框架怎么跑 | **仅标量**，无数组 | `timezone`、`permissions.*` |

红线：画像塞进 config 不生效；数组塞进 config 报错。拿不准 → environment。

---

## 1. 默认值体检表（占位就必配）

实测 `get_defaults()` 各前缀"空/占位 vs 有合理默认"的比例：

| 前缀 | 空/占位 | 有默认 | 结论 |
|---|---|---|---|
| **location** | **6** | 2 | `href=about:blank`、`hostname=localhost`、`origin/port/search/hash=''` → **几乎全占位，必配** |
| **canvas** | **4** | 1 | `toDataURL`/`toBlob` 系列全空（iv8 不真画像素）→ **靠 canvas 指纹的站必配** |
| navigator | 3 | **30** | 绝大多数有合理默认（UA=Chrome/platform=Win32/cores=8…）；3 个空（`doNotTrack`/`vendorSub`/`userAgentData.model`）**真 Chrome 也空，别动** |
| screen | 0 | **11** | 全有默认（1920×1080×24），一般吃默认 |
| webgl | 0 | **71** | 全有默认（内置一套 GPU 画像），一般吃默认 |
| window | 3 | 18 | `origin`/`name`/`status` 空 → 个别站配 `window.origin` |
| document | 3 | 6 | `domain`/`referrer`/`dir` 空 → 个别站配 |

> 数字随版本可能微调；判断逻辑不变：**空/占位 = 你要负责喂真值，有默认 = 通常吃默认，只在对齐真机时才覆盖。**

---

## 2. 三层配置清单（照这个优先级配）

- **① 必配（默认就错，躲不掉）**：`location.*`。默认 `about:blank` → 不配则域名校验/cookie 域/拼 URL 全错、签名上下文错。**几乎每个案例都有 location** 就是这原因。
- **① 看站必配**：
  - `canvas.fingerprint.toDataURL.png`（默认 `''`）—— 只有用 canvas 指纹的站；真值从真机抓注入。
  - **DOM 内容**（页面元素/`<meta>`/`title`，默认空骨架）—— 只有读页面 DOM 的站；用 `innerHTML` 或 `page.load` 填真实 HTML（何时用哪个见 `references/part2-discovery.md`）。
- **② 有默认、通常只补 UA**：`navigator.userAgent`（默认某 Chrome 版本；要指定就配，因 UA 入签名）。其余 30 个 navigator 字段、screen、webgl **吃默认**，只在对齐真机时才配。
- **③ 别动**：`navigator.doNotTrack`/`vendorSub`/`userAgentData.model`（真 Chrome 也空）、DOM 的 **API**（createElement/querySelector…，iv8 自洽）、事件/crypto/timer。

---

## 3. 分层体检口诀（DOM 特别注意"API 齐 ≠ 内容有"）

- **API 齐、内容空**：DOM 的 `createElement`/`querySelector`/`getElementById` 全自洽**不用补**；但 `document.title=''`、`documentElement.innerHTML` 仅 ~26 字符空壳、`querySelector('meta')=null`。读页面内容的站必须填真实 HTML。
- **location 几乎全占位**：默认 `about:blank`/`localhost`，是"默认就坑、躲不掉"的唯一前缀。
- **canvas 看站**：不真画像素，`toDataURL` 空串；图形指纹站必配，不用 canvas 的站不碰。
- **screen/webgl 全默认**：整套自洽，一般直接吃；只在需要伪装特定机型时才成套覆盖。

---

## 4. 一致性红线（配指纹最易翻车）

改一个字段牵一串。**UA ↔ userAgentData ↔ platform ↔ 时区(timezone) ↔ 语言(language/languages) ↔ webgl(vendor/renderer) 必须整套对齐。**
改了 UA 说是 Mac，就别让 `userAgentData.platform` 还是 Windows、别让 webgl 还报 NVIDIA。
这条红线由 `scripts/consistency_lint.py` 静态拒错（配环境提交前先过 lint）。

---

## 5. 怎么用 get_defaults() 导航

```python
import iv8
d = iv8.JSContext.get_defaults()          # 393 路径 → 值
for path, val in sorted(d.items()):
    if path.startswith("location"):        # 只看某前缀
        print(path, "=", repr(val))
```
把 debug 监控列出的"目标访问了哪些字段"与这里的默认值取交集：**目标读的 ∩ 默认占位的 = 你要配的清单**（P2 主力手段，见 `references/part2-discovery.md`）。全量导出与占位标注用 `scripts/defaults_audit.py`。
