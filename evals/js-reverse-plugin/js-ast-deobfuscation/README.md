# JS AST Deobfuscation eval

本目录在 Skill 包外验证两件事：

1. Skill 相比无 Skill 基线，是否更稳定地完成画像、正确分流并停在用户决策点。
2. `description` 是否在该触发时触发、在不该触发时保持安静。

## 资产

```text
fixtures/                 三个互异、小型、合成 JavaScript 样本
prompts/                  原始用户 prompt；测试代理只能看到 prompt 与对应 fixture
cases.jsonl               任务清单
rubrics.jsonl             评分规则；不得泄漏给测试代理
trigger-set.json          触发集声明计数
trigger-queries.jsonl     正负触发查询与 train/test 划分
schemas/                  任务对照与触发测试记录 schema
runs/pending-run.json     待执行计划，不是测试结果
validate_assets.py        无第三方依赖的资产验证器
```

## 任务对照协议

对每个 case 和 model 使用两个全新上下文：

- `skill`：显式提供当前 Skill；只给原始 prompt 和 fixture。
- `baseline`：不提供本 Skill，也不允许读取本目录的 rubric。

两组保持模型、参数、fixture、prompt、权限和工具一致。随机化 arm 顺序，保存原始输出，再按 `rubrics.jsonl` 评分。每次运行向 `runs/task-results.jsonl` 追加一条符合 `schemas/run-record.schema.json` 的记录。

不要把 expected observable、hard failure 或另一组输出放进测试代理上下文。

## description 触发协议

只向被测模型提供 Skill 的 `name`、`description` 和一个查询，不加载正文。每条查询、每个模型独立运行三次，并将记录写入 `runs/trigger-results.jsonl`。

- `train` 用于修改 description。
- `test` 只用于修改完成后的独立验收。
- 不得根据 test 逐条堆触发词。

## 开始一次运行

1. 复制 `runs/pending-run.json` 为新的 run manifest。
2. 填入实际模型 ID、provider、参数和完整命令。
3. 确认 Skill hash 与 manifest 一致。
4. 在新上下文中执行，不向测试代理泄漏 rubric。
5. 保存原始输出并写 JSONL 记录。
6. 运行：

```text
python3 validate_assets.py
```

`pending-run.json` 的 `status` 固定为 `pending`。没有实际模型输出时，不得创建分数、触发结果或完成状态。

## 当前 smoke 证据

`runs/task-results.jsonl` 保存了独立新上下文中的首轮 smoke，不代表 `pending-run.json` 规划的完整多模型矩阵已经完成：

- 3 个 case 都完成了 Skill arm。
- `bundler-boundary` 和 `runtime-seeded` 完成了同模型 baseline arm。
- `static-string` 又使用最终 Skill hash 重跑一次；运行后审计确认先直接读目标源码到 EOF，之后才读取 `first-pass.md`，且没有读取其他 reference。
- 原始回答保存在 `runs/2026-07-23-smoke/outputs/`。
- 两个成对 case 中，Skill arm 都在第一次语义改写前停到用户决策点；baseline 已直接给出改写结果。
- 当前部署没有暴露精确模型 ID，因此记录为 `codex-session-default`。
- description 的 180 次计划触发运行和 small/medium/large 完整矩阵仍保持 pending。

每条 run record 保存实际运行时的 Skill hash；后续修改不能回填覆盖旧 hash。
