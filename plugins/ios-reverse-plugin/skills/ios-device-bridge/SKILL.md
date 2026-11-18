---
name: ios-device-bridge
description: >-
  Cross-platform iOS physical device bridge for macOS, Windows, and Linux using
  pymobiledevice3, iproxy, and devicectl. Use when the agent needs to inspect
  connected iPhones/iPads, list installed apps, pull sandbox or AFC files,
  capture syslog or crash reports, forward USB ports for SSH/Frida, or check
  iOS 17+ developer tunnels.
---

# iOS Device Bridge

本技能划定宿主机（macOS / Windows / Linux）与 USB/Hub 连接的 iOS 真机交互时的**能力边界、环境前提、安全红线与证据标准**。不在固定流程里锁死操作顺序，由 Agent 根据当前逆向目标在圈内自主组合原语。

## 1. 职责与工具边界

* **职责范围**：只负责宿主机与 iOS 真机之间的设备通信、应用信息查询、文件拉取、日志/崩溃取证、USB 端口转发与调试通道检查；**不越权覆盖**静态 Mach-O 反编译或 Frida Hook 逻辑。
* **主力工具**：统一优先使用 `python3 -m pymobiledevice3`（Windows 上用 `python -m pymobiledevice3`），作为 iOS 端的 `adb` 等价物。
* **辅助工具**：USB 端口转发（如 SSH 22 或 Frida 27042）优先用 `iproxy` 或 `pymobiledevice3 lockdown forward`；macOS 上标准 App 安装/启动可备选 `xcrun devicectl`。
* **命令字典**：具体子命令与参数映射按需查阅 [pymobiledevice3-cheatsheet.md](references/pymobiledevice3-cheatsheet.md)，不在本文件重复堆砌。

## 2. 环境与设备前提边界

在执行任何业务操作前，先通过 `scripts/check_device.sh`（macOS/Linux）或 `python -m pymobiledevice3 usbmux list` 探明现实：

1. **单 / 多设备唯一性**：
   * 只有 1 台设备时可直接操作。
   * 若检测到 **2 台及以上**设备，禁止盲猜默认设备，必须显式传入 `--udid <UDID>` 并向用户确认目标机。
2. **宿主机系统前提**：
   * **macOS**：自带 `usbmuxd`，插线信任即可。
   * **Windows**：必须已安装包含 `Apple Mobile Device Service` 的经典版桌面端 iTunes（微软商店 *Apple Devices* 应用在部分发现场景不完整）；识别不到设备时直接报错提示检查驱动，不盲试。
3. **iOS 版本与隧道分界**：
   * **iOS 16 及以下**：直接通过 `usbmux` 通信，无需 `tunneld` 或管理员权限。
   * **iOS 17.4 及以上**：开发者服务（DVT、截图、进程监控等）自动通过用户态隧道（`--userspace`）建立，无需 root/管理员权限。
   * **iOS 17.0 – 17.3**：macOS 走原生隧道；Windows/Linux 依赖管理员权限运行的 `remote tunneld`。若隧道未就绪，明确告知缺少的条件。
4. **越狱 vs 非越狱能力边界**：
   * **非越狱设备**：可合法读取设备信息、系统日志（`syslog`）、崩溃报告（`crash`）、媒体目录（`afc`）以及开启文件共享/调试权限的应用沙盒（`house_arrest`）。
   * **越狱 / 高权限能力**：涉及系统分区读写、任意 App 完整沙盒、SSH 或 Frida-server 注入前，必须先实测端口转发与通道存活；通道不可用时如实汇报缺失，禁止伪造或套用安卓/模拟器假设。

## 3. 安全红线与防卡死约束

* **设备端只读优先**：分析数据库、Plist、二进制文件时，先用 `afc` 或 `house_arrest` 拉取到宿主机临时副本再分析，**禁止直接在设备端覆写、删除或修改原始数据**。
* **破坏性变更必须确认**：安装、覆盖或卸载 App（`apps install` / `uninstall`）、重启设备、修改系统配置或触发账号侧业务请求前，必须先停下来征得用户确认。
* **防超时与防刷屏**：禁止在单次 Shell 调用中无限制阻塞运行实时流（如裸跑 `syslog live` 或 `tunneld`）。抓日志必须配合 `timeout` 或行数/关键字截断；常驻转发进程需在任务结束后清理或交由后台任务管理。

## 4. 证据与交接标准

* 所有关于机型、系统版本、UDID、Bundle ID、崩溃堆栈和文件内容的结论，必须附带实际命令返回的原始字段或本地落盘路径。
* 严格区分“设备实测事实”与“基于静态结构的推断”。
