# AGENTS.md

本文件面向维护者和 AI Agent。使用者安装指南见 [README.md](README.md)。

## 技能单一来源

技能唯一来源是 `plugins/<name>/skills/`。修改技能只改这里；Claude Code、Codex、DeepSeek Harness 三个生态共享同一份内容，仓库中不保留副本。

## 发布 dsh 包

```bash
# 1. 修改 dsh/reverse-plugin/package.json 的 version
# 2. 打 tag 推送，CI 自动发布到 npm
git tag dsh-reverse-plugin-v<version>
git push origin dsh-reverse-plugin-v<version>
```

`dsh-reverse-plugin` 是「逆向」总包：一个 npm 包，按领域提供多个模式预设。发布时 CI 把各模式的技能从 `plugins/<mode>-reverse-plugin/skills` 复制成包内 `skills/<mode>`。tag 规则：`dsh-<package>-v<version>`，只触发 matrix 中对应的包。

## 新增逆向模式

模式 = DSH agent preset。新增一个模式要同步四处：

1. `plugins/<mode>-reverse-plugin/`：技能 + Codex/Claude 清单（技能唯一来源）
2. `dsh/reverse-plugin/preset/<mode>-reverse.patch.yml`：预设文件；技能行的 `config.dir` 指向 `skills/<mode>`
3. `.github/workflows/publish-dsh-plugin.yml` 的「Sync skills」加一行复制
4. `scripts/validate_repository.py` 的 `PLUGINS` 和 `DSH_PACKAGE["modes"]` 各加一条

技能注册行必须写在预设内部（`config.plugins`），不能放到 profile 层——只有预设内部注册才是 scoped 的，否则所有会话都会看到该模式的技能。

本地开发时 `dsh/reverse-plugin/skills/<mode>` 软链指向 `plugins/<mode>-reverse-plugin/skills`（不提交，见 `.gitignore`）。

## 本地校验

```bash
python3 scripts/validate_repository.py
claude plugin validate .
```

## 仓库布局

```text
.
├── plugins/<name>/              # 生态插件：skills + 各生态清单
├── .claude-plugin/              # Claude Code marketplace 清单
├── dsh/reverse-plugin/          # DSH 总包（独立 npm 包，模式预设 + 技能注册器）
├── evals/<name>/                # 技能评测
└── .github/workflows/           # dsh 包发布流水线（tag 触发，matrix 每包一行）
```
