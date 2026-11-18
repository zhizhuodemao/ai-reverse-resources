# pymobiledevice3 命令速查表

按能力分类索引常用原语（macOS / Linux 使用 `python3 -m pymobiledevice3`，Windows 使用 `python -m pymobiledevice3`）。若连接多台设备，在子命令后追加 `--udid <UDID>`。

## 1. 设备探活与基础信息

```bash
# 列出当前 USB / 网络发现的所有 iOS 设备（JSON）
python3 -m pymobiledevice3 usbmux list

# 查看锁定状态、机型、iOS 版本、硬件信息
python3 -m pymobiledevice3 lockdown info

# 若设备提示未配对（手机端需点击“信任此电脑”）
python3 -m pymobiledevice3 lockdown pair
```

## 2. 应用枚举与信息（只读）

```bash
# 仅列出用户安装的第三方 App（JSON，含 Bundle ID、名称、版本）
python3 -m pymobiledevice3 apps list -t User

# 查询单个 App 的详细信息（含签名权限 Entitlements、路径等）
python3 -m pymobiledevice3 apps query <BUNDLE_ID>

# [高危：需先向用户确认] 安装 / 卸载 IPA
# python3 -m pymobiledevice3 apps install <LOCAL_IPA_PATH>
# python3 -m pymobiledevice3 apps uninstall <BUNDLE_ID>
```

## 3. 文件与沙盒拉取（只读副本到本地）

```bash
# 查看媒体目录 (/var/mobile/Media)
python3 -m pymobiledevice3 afc ls /

# 拉取媒体目录下的文件到本地
python3 -m pymobiledevice3 afc pull <REMOTE_PATH> <LOCAL_PATH>

# 访问支持文件共享或调试权限的 App 沙盒（Documents / 容器目录）
python3 -m pymobiledevice3 apps afc <BUNDLE_ID> ls /
python3 -m pymobiledevice3 apps afc <BUNDLE_ID> pull /Documents/target.db ./local_copy.db
```

## 4. 日志与崩溃报告取证

```bash
# 截取 5 秒实时 syslog 并过滤关键字（避免无限阻塞）
timeout 5 python3 -m pymobiledevice3 syslog live | grep -i "<KEYWORD>" || true

# 列出并拉取设备上的崩溃日志 (.ips / .crash)
python3 -m pymobiledevice3 crash ls /
python3 -m pymobiledevice3 crash pull / ./crash_reports/
```

## 5. USB 端口转发（配合 SSH / Frida）

```bash
# 将设备端 22 端口（越狱 SSH）转发到宿主机本地 2222 端口
python3 -m pymobiledevice3 lockdown forward 2222 22

# 或使用 libimobiledevice 的 iproxy（常驻后台需注意进程管理）
iproxy 2222 22 -u <UDID>
```

## 6. 开发者服务与 iOS 17+ 隧道

```bash
# 挂载对应版本的 DeveloperDiskImage（iOS 16 及以下部分开发者服务需要）
python3 -m pymobiledevice3 mounter auto-mount

# 截图（验证界面状态）
python3 -m pymobiledevice3 developer dvt screenshot ./screen.png

# 查看运行中的进程（需要 DVT 权限）
python3 -m pymobiledevice3 developer dvt sysmon process single

# iOS 17.0-17.3（Linux/Windows）或外部工具（如 lldb）需启动内核隧道（需 root/管理员）：
# sudo python3 -m pymobiledevice3 remote tunneld
```
