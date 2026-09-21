# AI Reverse Resources

面向 AI Agent 的逆向工程插件仓库，支持 Codex、Claude Code 和 DeepSeek Harness。当前提供 `js-reverse-plugin`。

## 安装全部（推荐）

当前仓库只有 `js-reverse-plugin`，因此“安装全部”就是安装该插件。

### Codex CLI

```bash
codex plugin marketplace add zhizhuodemao/ai-reverse-resources
codex plugin add js-reverse-plugin@ai-reverse-resources
```

安装后启动新的 Codex 会话。

### Codex App

1. 在终端添加 Marketplace：

   ```bash
   codex plugin marketplace add zhizhuodemao/ai-reverse-resources
   ```

2. 重启 ChatGPT 桌面端，进入 Codex 的 **Plugins**。
3. 选择 **AI Reverse Resources**，安装 **JS Reverse Plugin**。
4. 新建任务。

### Claude Code CLI

```bash
claude plugin marketplace add zhizhuodemao/ai-reverse-resources
claude plugin install js-reverse-plugin@ai-reverse-resources
```

安装后启动新会话；如果在当前会话内安装，运行 `/reload-plugins`。

### Claude Code Desktop

1. 在终端添加 Marketplace：

   ```bash
   claude plugin marketplace add zhizhuodemao/ai-reverse-resources
   ```

2. 打开 Claude Desktop 的 **Code** 标签，选择 **+ → Plugins → Add plugin**。
3. 从 **ai-reverse-resources** 安装 **js-reverse-plugin**。

Claude Code Desktop 的插件适用于本地和 SSH 会话，不适用于 cloud 或 WSL 会话。

### DeepSeek Harness (dsh)

#### 方案 A（推荐，一劳永逸）：全局安装 CLI，之后 `dsh` 永久可用

```bash
npm install -g @deepseek-ai/dsh
dsh plugin --profile web add dsh-js-reverse-plugin
```

安装后启动新的 dsh 会话：

- 三个技能出现在对话输入框 `/` 命令面板：`js-ast-deobfuscation`、`iv8-env-runtime`、`iv8-jsvmp-recovery`
- MCP 工具注册为 `mcp__js-reverse__*`（如 `mcp__js-reverse__navigate_page`）
- 「逆向模式」出现在 **设置 → Agent 预设 → 自定义**

DeepSeek Harness 没有插件市场；插件发布在 npm：[dsh-js-reverse-plugin](https://www.npmjs.com/package/dsh-js-reverse-plugin)。

#### 升级：必须手动删除旧的 agent preset

安装时插件会把「逆向模式」preset 写入 `~/.dsh/.agent-presets/reverse/`，**已存在的文件一律不覆盖**，以保护用户对 preset 的本地改动。代价是升级插件拿不到新版 preset：dsh 的 agent preset 会引用具体的 harness 插件包名和 config 字段，而这些随 dsh 版本演进，旧 preset 迟早引用到已改名或已改字段的插件，届时预设卡片显示红色「加载失败」且不可选。

因此升级插件后，如果没有改过该 preset，删掉目录再重启，让新版重新写入：

```bash
rm -rf ~/.dsh/.agent-presets/reverse
```

改过的话，先备份再删除，重启后把自己的改动重新应用到新版之上。技能和 MCP 工具不受影响，正常随插件升级。

## 自选安装

添加 Marketplace 后，可以只安装需要的插件：

```bash
# Codex
codex plugin add <plugin-name>@ai-reverse-resources

# Claude Code
claude plugin install <plugin-name>@ai-reverse-resources
```

当前可选插件：`js-reverse-plugin`。在 Codex App 或 Claude Code Desktop 中，也可以直接从插件浏览器选择安装，不会因为添加 Marketplace 而无提示安装全部插件。

## 目录结构

```text
.
├── plugins/                     # 插件本体（每插件一个目录）
│   └── js-reverse-plugin/
│       ├── skills/              # ← 技能唯一来源，三个生态共享
│       ├── .claude-plugin/      # Claude Code 插件清单
│       └── .codex-plugin/       # Codex 插件清单
├── .claude-plugin/              # Claude Code marketplace 清单
├── dsh/                         # DeepSeek Harness 适配区（每插件一个 npm 包）
│   └── js-reverse-plugin/       # 包名 dsh-js-reverse-plugin
└── .github/workflows/           # dsh 包发布流水线（tag 触发）
```

修改技能只动 `plugins/<name>/skills/`；三个生态的适配壳各自独立。新增插件的 dsh 适配时，在 `dsh/` 下建同名目录。

## 当前内容

`js-reverse-plugin`：JavaScript AST 解混淆、受控 iv8 运行、JSVMP 恢复，以及 `js-reverse-mcp@4.0.5` 浏览器动态取证。

## 本地校验

```bash
python3 scripts/validate_repository.py
claude plugin validate .
```

安装说明依据 [Codex Plugins](https://learn.chatgpt.com/docs/plugins) 和 [Claude Code Plugins](https://code.claude.com/docs/en/discover-plugins)。
