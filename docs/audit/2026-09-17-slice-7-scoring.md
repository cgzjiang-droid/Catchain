# Slice 7 Task 1：旧评分业务依据与新输入边界

只读来源：旧最终ACM0002包的main.py、field_mapping_acm0002_master.json、method_table_acm0002_independent.json。
三个文件哈希已重新核对，与Slice 4审计相符；记录于scoring/acm0002-readiness-v1.json。
旧Method Table是本项目历史业务资料，不是已核实的官方方法学条款。
本步复用旧业务字段/定义，新增准备度逻辑；未复制参考存档项目代码。

旧score_dimension只计算high/mid关键词命中，main把12个分值直接求和，总上限36。
没有明确权重字段，算术上等权不代表业务权重获得批准；本轮权重全部null。
旧业务Rubric的“充分”“正确”“可复现”不能由字段出现或关键词命中直接证明。

| 维度 | 旧业务关注 | 后续需要确认的验证/判断 |
| --- | --- | --- |
| D01 | 并网适用性 | 方法学版本、并网证明、项目边界；人工判断适用范围 |
| D02 | 技术适用性 | 技术/资源/容量、跨来源一致性；适用技术清单待确认 |
| D03 | 基准线完整性 | 基准线场景、公式、假设与审定结论，出现公式不等于正确 |
| D04 | 电网排放因子链 | 数值、单位、年份、工具/来源及计算材料，单位标准待明确 |
| D05 | 计量质量 | 周期相同的发电/上网计量、校准证明、原始日志；calibration不等于合格 |
| D06 | 项目排放处理 | 适用条件、数值、计算和核证依据，false不能自动当排放0 |
| D07 | 泄漏处理 | 适用理由或量化结果，未提及不是不适用 |
| D08 | 减排量复现 | 同周期BE/PE/LE/ER、适用公式及容差；不能混周期相减 |
| D09 | 额外性 | 使用工具、投资/障碍/普遍实践分析与结论，需业务专家判断 |
| D10 | 监测体系 | 参数、QA/QC、缺数处理和归档，文本存在不等于程序充分 |
| D11 | 审核与周期一致性 | 审定/核证机构及报告、周期、历史事件；不能把机构名当核证合格 |
| D12 | 登记与版本过渡 | 方法学版本、登记/签发历史、变更说明；新版不自动权威 |

目录保存旧定义和旧0–3 Rubric供业务确认，当前scoring_rule_status全部pending_business_confirmation。
初始47字段清单不是完整评分所需证明材料清单。旧别名、来源优先级也不是自动权威规则。
例如GS把crediting period start映为verification start的别名需要重新核验，不直接用于周期合并。

新score readiness只读取canonical_heads当前正式事实；拒绝/未知/未审核候选均不计入。
每条事实保留批准decision、原candidate、两个run、提取方法、Parsed、文件哈希和修订原文证据。
逐维missing_inputs或rubric_pending，score与total_score保持null；accuracy也为null，无人工Gold。
准备度报告是不可变JSON+成功evaluated run，尚未加入评分结果数据库表。
下一步先落实周期标识、适用版本与可执行业务规则，再计算可解释的分值。
