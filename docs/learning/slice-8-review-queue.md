# Slice 8：审核队列如何把问题交给人工

Slice 7 已经把候选、验证问题、Evidence和审核历史保存下来。Slice 8 不重新抽取，也不让模型自动裁决；它只把这些记录投影成负责人可以按优先级处理的队列。

`review queue`的输入是`fact_candidates`、`candidate_evidence`、`validation_reports`、`review_decisions`和`canonical_heads`。输出保留candidate_id、项目/字段、原值、问题code、错误消息、原文Evidence、当前正式fact_id、审核次数和最新状态。

优先级是操作排序：证据不存在或机械拒绝属于critical，日期/单位/类型风险属于high，低置信度和语义支持待确认属于normal。priority不等于质量分，也不会覆盖人工决定。

`review metrics`统计处理量、approved/unresolved比例、Evidence覆盖率、字段覆盖率、返工数和从验证完成到审核提交的平均延迟。Gold没有冻结时，指标中的`accuracy_eligible=false`；评分策略没有approved时，`total_score_eligible=false`。这是产品指标和模型评估的边界。

这里的技术重点是Projection：数据库保留规范化历史，队列是面向人工的读取视图。它仍是普通Workflow，不需要Agent、RAG或LangGraph。

面试可能问：为什么不让LLM直接决定队列优先级？因为优先级需要可解释、可复现和可审计；问题code和Evidence状态可以用确定性规则排序，语义裁决仍交给人工。

