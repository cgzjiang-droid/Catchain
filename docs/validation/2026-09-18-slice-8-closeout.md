# Slice 8 工程闭环验收

日期：2026-09-18

## 结论

Slice 8 已完成 CLI/JSON 形式的审核台 MVP，并保留进入独立前端的演进空间。人工审核仍是显式操作，系统不自动替审核员做语义裁决。

## 已交付

- `review queue`：从候选、验证报告、Evidence、审核历史和当前正式事实生成可排序队列。
- 优先级：证据/机械错误为 critical，日期、单位和类型风险为 high，低置信度和语义待确认为 normal。
- 默认隐藏已批准候选；unresolved 和 rejected 保留在待处理队列，避免问题被静默丢弃。
- 队列项保留原值、问题code、错误消息、原文页码/片段/字符位置、当前正式fact_id、审核次数和最新状态。
- 复用已有 `review decide`：格式和Evidence错误保留草稿并返回错误位置；批准保留修改前后值、负责人、理由和Canonical历史；新文档不会覆盖旧版本。
- `review metrics`：候选状态、已审核/待审核量、审核结果、Evidence覆盖率、字段覆盖率、返工数和平均审核延迟。
- 队列和指标按内容哈希生成不可变JSON；新增三个Schema，完整Schema数量为19。

## 验收证据

- 全量测试：138 passed。
- Ruff：通过。
- 队列和指标CLI的首次写入/重复复用测试通过。
- GitHub同步后，源仓库与发布快照逐文件一致，私有数据目录未被追踪。

## 指标边界

`accuracy_eligible=false`、`total_score_eligible=false`始终写入Slice 8指标快照。审核吞吐和返工指标用于人工运营与灰度准入，不能替代冻结Gold准确率，也不能替代approved评分策略。

## 下一步

进入后续产品迭代：根据真实审核员反馈决定是否需要批量纠错、独立前端或更细的权限控制。Review Agent仍不是当前MVP依赖。

