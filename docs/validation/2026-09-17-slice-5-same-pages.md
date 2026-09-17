# Slice 5：固定同页Regex/LLM比较

复用已保存的真实DeepSeek run 411589fa-148c-4599-a5cd-fc51f17371b8。
文档ACR125，Parsed身份37898e91-6bd4-4657-a7dc-679db7b41a04；仅原PDF第1页，
project_name、country、project_owner、verifier_name四字段。

| 字段 | Regex | 真实LLM | 差异 |
| --- | --- | --- | --- |
| project_name | 未找到 | THE SEESA PV PROJECT IN EL SALVADOR | llm_only |
| country | 未找到 | El Salvador | llm_only |
| project_owner | 未找到 | 未找到 | both_missing |
| verifier_name | 未找到 | 未找到 | both_missing |

LLM与Regex使用同一页文字，引用全部可定位。没有新增模型调用；没有人工Gold，
accuracy=null。单样本、四字段不代表全文、所有Registry或生产质量。

比较结果存入忽略目录data/extracted/slice5-same-pages；第一次stored，重复reused，
同一报告字节与processing run保持不变。报告保存源PDF SHA256、Parsed和文档版本、
LLM run、原页码/选页哈希、Regex规则哈希/版本、双方候选/缺失原因和引用。

自动检查覆盖第2页的原页码、选页之外的容量不参与比较、多个候选冲突、双方弃答、
伪造证据/选页/文档身份/输入哈希的拒绝，以及CLI重复比较不触发模型。
缓存复用也新增候选Schema、run/配置/输入身份与引用位置检查。损坏缓存保留并报错，
不会自动覆盖或为了修复缓存重发付费请求。

Slice 5四任务开发范围完成；下一步Slice 6验证引用是否支持值、字段类型、单位、
日期和冲突。完整事实库、人工Gold、准确率评估、审核台及上线验收还未完成。
