# AI Reverse Resources

AI 辅助逆向工程的插件与资源仓库。仓库以 Codex Marketplace 结构组织可独立安装的插件，并把 Skill、MCP 工具和独立评测资产分层保存。

## 当前插件

### `js-reverse-plugin`

JavaScript 逆向工程插件，包含三个递进 Skill：

```text
js-ast-deobfuscation
  → 外层 JavaScript 解混淆与 JSVMP 宿主边界

iv8-env-runtime
  → 受控 iv8 运行、环境配置与真实生成入口

iv8-jsvmp-recovery
  → 静态分析 + 动态 Trace + 独立精确复现
```

插件同时注册 `js-reverse-mcp@4.0.1`，用于浏览器网络、源码、断点、调用栈、Scope、Frame 和运行状态取证。

## MCP 支持

插件内置名为 `js-reverse` 的本地 stdio MCP 服务，安装后通过固定版本命令启动：

```text
npx -y js-reverse-mcp@4.0.1
```

它为三个 Skill 提供浏览器、源码、网络、断点和运行时取证能力。MCP 浏览器是动态观察与调试界面；受控 `iv8` 仍是确定性等价验收的唯一参考运行时。

## 仓库结构

```text
.agents/plugins/marketplace.json   仓库级 Marketplace 索引
plugins/                           可安装插件
evals/                             插件包外的独立评测资产
```

每个插件自己保存 `.codex-plugin/plugin.json`、Skill 和 MCP 配置。评分规则、触发查询和测试运行记录保存在插件包外，不随 Skill 注入模型上下文。

## 设计原则

- Skill 提供模型无法凭空知道的领域背景、判断标准和边界。
- MCP 提供确定的动态操作与证据接口，不代替模型判断任务语义。
- Evals 验证结果质量、触发边界和证据判断，不验证模型是否服从固定流程。
- 案例知识必须显式标注适用版本，不得冒充通用逆向规律。
- 目标 JavaScript 强制以 iv8 为唯一受控执行底座；Node.js 只可用于格式化、AST 和构建等静态工程任务，不得替代 iv8 运行目标程序。

## 本地校验

```bash
python3 scripts/validate_repository.py
```

该命令校验 Marketplace、插件 Manifest、三个 Skill、MCP 配置和现有 eval 资产，不运行未知目标 JavaScript。
