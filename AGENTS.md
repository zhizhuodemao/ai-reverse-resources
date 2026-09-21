# AGENTS.md

本文件面向维护者和 AI Agent。使用者安装指南见 [README.md](README.md)。

## 技能单一来源

技能唯一来源是 `plugins/<name>/skills/`。修改技能只改这里；Claude Code、Codex、DeepSeek Harness 三个生态共享同一份内容，仓库中不保留副本。

## 发布 dsh 包

```bash
# 1. 修改 dsh/js-reverse-plugin/package.json 的 version
# 2. 打 tag 推送，CI 自动发布到 npm
git tag dsh-js-reverse-plugin-v<version>
git push origin dsh-js-reverse-plugin-v<version>
```

发布时 CI 从 `plugins/js-reverse-plugin/skills` 复制技能进包。tag 规则：`dsh-<package>-v<version>`，只触发 matrix 中对应的包。

## dsh agent preset 跟随 dsh 版本

`dsh/<name>/preset/agent.cordis.yml` 逐行引用 harness 插件包名和 config 字段，两者都随 dsh 版本变化，包改名或字段改签名都会让 preset 整体判为 broken。改这个文件时以当前 dsh 仓库的 `packages/preset/agent-presets/presets/standard/agent.cordis.yml` 为基准，只保留本 preset 真正的差异。

`installPreset` 对已存在的文件一律跳过，所以发布新版不会替换用户机器上的旧 preset，README 的升级章节要求用户手动删除 `~/.dsh/.agent-presets/<id>/`。

## 新增插件的 dsh 适配

1. 在 `dsh/` 下建与插件同名的目录（独立 npm 包，包名 `dsh-<plugin-name>`）
2. 本地开发时 `skills` 软链指向 `../../plugins/<plugin-name>/skills`（不提交，见 `.gitignore`）
3. 在 `.github/workflows/publish-dsh-plugin.yml` 的 matrix 加一行 `- package: <name>`

## 本地校验

```bash
python3 scripts/validate_repository.py
claude plugin validate .
```

## 仓库布局

```text
.
├── plugins/<name>/             # 插件本体（skills + 各生态清单）
├── .claude-plugin/             # Claude Code marketplace 清单
├── dsh/<name>/                 # DeepSeek Harness bundle（独立 npm 包）
└── .github/workflows/          # dsh 包发布流水线（tag 触发，matrix 每包一行）
```
