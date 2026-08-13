# AI Reverse Resources

面向 AI Agent 的逆向工程插件仓库，支持 Codex 和 Claude Code。当前提供 `js-reverse-plugin`。

## 安装

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

## 当前内容

`js-reverse-plugin`：JavaScript AST 解混淆、受控 iv8 运行、JSVMP 恢复，以及 `js-reverse-mcp@4.0.1` 浏览器动态取证。

## 本地校验

```bash
python3 scripts/validate_repository.py
claude plugin validate .
```

安装说明依据 [Codex Plugins](https://learn.chatgpt.com/docs/plugins) 和 [Claude Code Plugins](https://code.claude.com/docs/en/discover-plugins)。
