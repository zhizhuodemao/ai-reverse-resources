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
