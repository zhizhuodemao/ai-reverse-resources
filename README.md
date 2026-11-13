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

DSH 侧是一个「逆向」总包，按领域提供模式（Agent 预设）：当前有 **JS 逆向模式**，安卓 / iOS 模式随后加入。

#### 方案 A（推荐）：从插件市场安装

1. 打开 **Plugins → Discover**（看不到这个标签页时，先在「实验性插件」里打开「自定义插件市场」）。
2. 添加索引源；已经加过就跳过这一步：

   ```text
   https://cdn.jsdelivr.net/npm/dsh-plugin-catalog/index.json
   ```

3. 搜索 `reverse` 并安装。

收录条目见 [awesome-dsh-plugin #14987](https://github.com/awesome-dsh-plugin/awesome-dsh-plugin/pull/14987)；合并前市场里还搜不到，先用方案 B。

#### 方案 B：命令行安装

```bash
npm install -g @deepseek-ai/dsh
dsh plugin --profile web add dsh-reverse-plugin
```

DSH Desktop 用户请走方案 A，或在应用的 **插件** 页按包名 `dsh-reverse-plugin` 安装：`--profile web` 装进的是 CLI / `dsh web` 的 profile，桌面端不读它。

装完后启动新的 dsh 会话，在 Agent 预设中选择 **JS 逆向模式**（`js-reverse`）：

- 三个技能出现在对话输入框 `/` 命令面板：`js-ast-deobfuscation`、`iv8-env-runtime`、`iv8-jsvmp-recovery`
- MCP 工具注册为 `mcp__js-reverse__*`（如 `mcp__js-reverse__navigate_page`）

技能与 MCP 挂在该模式内部，只有选了 JS 逆向模式的会话能看到它们；标准会话不会出现这些条目。

需要 Node.js 24.9 或更新版本，以及 DSH `^0.2.1-rc.3`。

插件同时发布在 npm：[dsh-reverse-plugin](https://www.npmjs.com/package/dsh-reverse-plugin)。

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
├── plugins/                     # 生态插件（Codex / Claude）
│   └── js-reverse-plugin/
│       ├── skills/              # ← 技能唯一来源，三个生态共享
│       ├── .claude-plugin/      # Claude Code 插件清单
│       └── .codex-plugin/       # Codex 插件清单
├── dsh/
│   └── reverse-plugin/          # DSH 总包 dsh-reverse-plugin
│       ├── index.js             # 技能注册器，按 config.dir 注册某个模式
│       ├── preset/              # 每个模式一个预设文件
│       │   └── js-reverse.patch.yml
│       └── tests/
├── evals/                       # 技能评测
├── scripts/                     # 仓库校验
└── .github/workflows/           # dsh 包发布流水线（tag 触发）
```

修改技能只动 `plugins/<name>/skills/`；三个生态的适配壳各自独立。新增逆向模式时：在 `plugins/` 加该模式的技能插件，在 `dsh/reverse-plugin/preset/` 加一个预设文件，并在发布流水线的技能复制步骤里加一行。

## 当前内容

- **JS 逆向模式**（DSH 预设 `js-reverse`，技能包 `js-reverse-plugin`）：JavaScript AST 解混淆、受控 iv8 运行、JSVMP 恢复，以及 `js-reverse-mcp@4.0.1` 浏览器动态取证。
- 安卓逆向、iOS 逆向：规划中。

## 本地校验

```bash
python3 scripts/validate_repository.py
claude plugin validate .
```

DSH bundle 的配置和技能注册回归检查：

```bash
cd dsh/reverse-plugin
npm install
mkdir -p skills
ln -s ../../../plugins/js-reverse-plugin/skills skills/js # 已有 skills/js 时跳过
npm test
```

安装说明依据 [Codex Plugins](https://learn.chatgpt.com/docs/plugins) 和 [Claude Code Plugins](https://code.claude.com/docs/en/discover-plugins)。
