# Slice 6 Task 1：机械验证验收

新增候选级ValidationIssue/检查状态与不可变报告，以及validate extraction CLI。
输入来源、成功抽取run、Parsed身份与内容哈希经数据库核对；原候选完整保留。
错误/审核状态指向observation_index和原始字段、证据页/片段/字符位置。

94项pytest通过、Ruff通过、wheel构建成功。JSON Schema从7个增至8个；
新增ExtractionValidationReport，旧7合同不修改。

自动验证包括严格数值类型（True/字符串不能冒充容量）、负容量、无效日历日期、
模糊日期、正确闰日、低/高/未知置信度、缺单位、不同候选冲突、伪造证据、
文档身份错误、未知业务合同的待审核，以及CLI报告复用和0次额外模型调用。

真实pilot复用ACR125已保存的LLM run 411589fa-148c-4599-a5cd-fc51f17371b8：
项目名/国家均needs_review，两项公司角色missing，rejected=0，canonical_writes=0。
原文可定位仍有semantic_support_pending与confidence_unknown；不凭空设高置信度。
私有输出：data/extracted/slice6-validation-pilot；重复reused，保留同一报告与run。

Task 1没有语义裁决器、跨字段/文档规则、权威来源选择或Canonical事实表。
0.8是产品分流参数，未做Gold校准。负计量值（除容量/整数明确范围）要求字段化
业务规则审核；没有机械检查失败就自动通过事实审核的通道。
