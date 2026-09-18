# Slice 7：审核判定如何保存

输入合同JudgmentRequest包含rubric_version、reviewer及逐项judgments。
每项包含criterion_id、outcome、reason、fact_ids、evidence。
同一请求不允许重复判定项；明确支持、不支持或不适用必须有事实与证据。
证据不足与冲突可以弃答，但不能省略原因；缺失不是不合格。

关键代码：domain/judgment.py定义合同；scoring/judgments.py核对事实快照和引用。
score judgments读取保存的readiness，检查原处理run/哈希，并核对当前已批准事实。
变更过或过期的快照拒绝执行，其他项目或不属于本维度的事实拒绝引用。
原文必须存在于所引用事实的Parsed文档版本/页码/字符位置，不能仅贴一段无来源文字。

输出是不可变JSON artifact和evaluated run，保存原readiness快照、草案哈希及完整人工输入。
相同输入重复提交复用；修改输入产生新历史artifact，不覆盖旧记录。
未审核的判定项明确列出。尚未实现评分结果数据库表，不生成质量分或正式事实。
审核人仍是本机输入声明，引用存在也不能自动证明语义正确。

旧系统主要保存汇总分；参考存档项目帮助文档版本设计，但不提供本审核协议。
CATchain保留原JSON交换方式并增加明确Schema和证据验证，无新依赖或Agent框架。
对应知识是Structured Output、Schema Validation、Evidence Grounding和可复现快照。
面试可能问：只有一项审核完成能给总分吗？不能。保留部分结果、列出未审项目，按后续批准规则判断可评范围。
