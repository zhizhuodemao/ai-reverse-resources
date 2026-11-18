# DSH 插件市场收录说明

记录 `dsh-reverse-plugin` 在 DeepSeek Harness（dsh）插件市场的收录位置、条目数据与更新方式。更新于 2026-11-18。

## 当前状态

| 项目 | 值 |
|---|---|
| 收录条目 | `dsh-reverse-plugin` |
| 市场卡片标题 | `zhizhuodemao/ai-reverse-resources#reverse-plugin` |
| 分类 | `tools` |
| 收录来源 | npm（`dsh-reverse-plugin`） |
| 当前版本 | `0.3.1` |
| 兼容范围 | `engines.dsh: ^0.2.1-rc.3`，Node >= 24.9 |
| 收录时间 | 2026-11-13（[awesome-dsh-plugin #14987](https://github.com/awesome-dsh-plugin/awesome-dsh-plugin/pull/14987) 合并） |
| 详情页 | <https://awesome-dsh-plugin.com/p/zhizhuodemao/ai-reverse-resources--dsh-reverse-plugin/> |
| npm 页面 | <https://www.npmjs.com/package/dsh-reverse-plugin> |

## 收录链路

市场不是上传制，而是一条单向下游链：

```
awesome-dsh-plugin（目录数据，唯一投稿入口）
   └── dsh-plugin-catalog / awesome-dsh-plugin.com（format 1 索引）
          ├── dshmarket、Plugins → Discover
          └── realguan/dsh-plugin-market（每日重建的第三方索引）
```

条目只需要提交到 `awesome-dsh-plugin`：一个文件 `data/plugins/<owner>__<repo>.yml`。其余两个索引都从它派生，不收 PR。

## 索引源

| 索引源 | 地址 | 当前收录数 | 生效速度 |
|---|---|---|---|
| GitHub Pages | `https://awesome-dsh-plugin.com/index.json` | 6112 | 合并后约 10 分钟 |
| npm 分发（推荐） | `https://cdn.jsdelivr.net/npm/dsh-plugin-catalog/index.json` | 6112 | jsDelivr 缓存最长 12 小时 |
| 第三方（桌面端已配置） | `https://cdn.jsdelivr.net/gh/realguan/dsh-plugin-market@dist/dsh-index.json` | 11179 | 每日 03:17 UTC 重建 |

三个源的内容口径一致，只需添加一个；同时添加会出现重复条目。

## 安装方式

从市场（需要先加索引源）：

1. 打开 **Plugins → Discover**，添加上面的索引源；
2. 搜索 `reverse` 并安装。

命令行：

```bash
npm install -g @deepseek-ai/dsh
dsh plugin --profile web add dsh-reverse-plugin
```

DSH Desktop 不读 `profiles/web`，请走市场，或在应用的插件页按包名 `dsh-reverse-plugin` 安装。

装完后新开会话，在 Agent 预设里选择 **逆向模式**（`reverse`）。

## 条目符合的收录要求

| 要求 | 本仓库现状 |
|---|---|
| `package.json` 声明 `dsh.bundle.patch` | `dsh/reverse-plugin/package.json` → `["./preset/reverse.patch.yml"]` |
| 仓库创建满 1 天 | 创建于 2026-08-13 |
| 仓库带 `dsh-plugin` topic | 已添加 |
| 描述与代码一致 | 描述只列实际存在的三个技能、MCP 服务名与预设 |
| 已发布 npm（推荐） | `dsh-reverse-plugin@0.3.1` |
| 不与其他条目重复 | 同仓库旧条目已随包重命名一并更新 |

## 更新与发布

改版本号后打 tag，CI 自动发布：

```bash
# 1. 修改 dsh/reverse-plugin/package.json 的 version
# 2. 推 tag
git tag dsh-reverse-plugin-v<version>
git push origin dsh-reverse-plugin-v<version>
```

流水线会从 `plugins/*/skills` 复制技能到包内 `skills/<mode>`，跑 bundle 测试，然后发布到 npm。发布后索引按各自的节奏重建：GitHub Pages 约 10 分钟，npm 分发的索引受 jsDelivr 缓存影响最长 12 小时，第三方索引次日 03:17 UTC。

## 历史

- `dsh-js-reverse-plugin@0.2.2` 是改名前发布的最后一个版本，已在 npm 标记废弃（deprecated），提示迁移到 `dsh-reverse-plugin`。
- 市场条目最初指向 `dsh/js-reverse-plugin`，包重命名为「逆向总包」后同步改到 `dsh/reverse-plugin`，合并前完成，没有产生废弃条目。

## 待补内容

- 安卓逆向、iOS 逆向的技能目录尚未填充，市场描述只承诺当前存在的 JS 领域能力。
- 新增领域不需要改市场条目：在同一个包里追加技能目录与预设行即可，索引会在下次重建时自动沿用。
