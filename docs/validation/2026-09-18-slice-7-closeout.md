# Slice 7 工程闭环验收

日期：2026-09-18

## 结论

Slice 7 已完成工程闭环，进入 Slice 8。这里的“完成”表示评估链路已经有可验证的合同、证据、版本和失败边界，不表示 ACM0002 的正式业务权重或准确率已经获批。

## 已交付

- 12 维准备度检查：正式事实、方法学版本、周期、计量事实和原文证据必须绑定。
- `JudgmentRequest` 与 `EvaluationResult`：支持部分审核、未审核项、冲突/证据不足和不可变评估结果。
- 评分策略激活门：`draft` 可保留空权重；`approved` 必须包含 D01–D12、权重和为 1、权威来源、审核人和日期。
- Gold 样本与数据集合同：区分 confirmed、unknown、conflicting，冻结后才能评估；禁止项目跨 split 泄漏。
- `evaluate gold` 和 `evaluate dataset`：仅离线读取既有artifact，不调用模型；报告覆盖不完整时不计算聚合指标。
- JSON Schema、SQLite `evaluation_results`、幂等 artifact 和运行身份检查。

## 验收证据

- 全量测试：135 passed。
- Ruff：通过。
- 源仓库与 GitHub 发布快照逐文件一致。
- GitHub 发布提交：[af33445](https://github.com/cgzjiang-droid/Catchain/commit/af33445ec92e932c7e60553e74a77a08647fe7ac)。
- 发布仓库未追踪 `data/raw`、`data/parsed`、`data/extracted` 或 `data/review` 私有数据。

## 外部准入条件

以下事项不能由系统替业务方自动确认，暂时保留为上线前门槛：

1. ACM0002 适用Registry、版本、周期和条款的正式确认。
2. 12 个维度的业务分值、权重、容差和“不适用”处理规则。
3. 两名审核员与组长裁决后的真实冻结 Gold 样本及独立测试 split。

在这些输入到位前，系统的正式结果必须保持 `score_status=pending_policy`、`total_score=null` 或 `accuracy=null`；这是一项验收保护，不是失败。

## 下一步

Slice 8 负责把已有候选、验证问题和证据组织成可执行审核队列，并记录草稿纠错、修改前后值、审核人、原因和产品指标。
