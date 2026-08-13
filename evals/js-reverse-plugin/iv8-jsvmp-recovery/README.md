# iv8 JSVMP Recovery eval

本目录在 Skill 包外验证一个主命题：模型是否始终把“受控 iv8 原程序 + 声明的原始输入 + 独立实现 + 精确输出等价”作为 VMP 语义恢复的正确性标准。

任务评测检查：

- 能否区分原始输入与预计算派生字段；
- 能否对固定基线、变体集和全输入等价作出范围准确的声明；
- 能否在没有 Trace 时仍从静态容器确定 Record 数量；
- 能否区分 Handler、Opcode、Record、Frame 和源码函数；
- 能否区分服务器接受与本地语义精确等价；
- 能否根据 Trace 提出有边界的机械语义，而不把单次观测扩展为全语义。

## 任务对照

对每个 case 使用两个全新上下文：

- `skill`：显式提供 `iv8-jsvmp-recovery`，只给原始 prompt 和 fixture；
- `baseline`：不提供该 Skill，也不允许读取 rubric。

两组保持模型、参数、prompt、fixture、权限和工具一致。保存原始输出后再根据 `rubrics.jsonl` 评分，不要把期望结论或 hard failure 泄漏给测试模型。

## 触发对照

只向被测模型提供 Skill `name`、`description` 和一条 query。`train` 用于修改 description，`test` 仅在定稿后验收。不要根据 test 查询逐条堆触发词。

## 资产

```text
fixtures/             原始小型案例
prompts/              原始用户请求
cases.jsonl           任务清单
rubrics.jsonl         评分规则，不得提供给测试模型
trigger-queries.jsonl 正负触发集
trigger-set.json      触发集计数声明
runs/                 未来的原始输出和运行记录
validate_assets.py    无第三方依赖的结构校验
```

运行：

```bash
python3 validate_assets.py
```

该命令只验证资产结构，不生成模型分数。没有真实独立模型输出时，不得伪造 eval 结果。
