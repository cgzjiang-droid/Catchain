# Slice 4：旧版抽取与评分基线审计

日期：2026-09-17。范围：老师最终版 ACM0002 包；只读审计，不修改旧文件。

## 来源与实际调用链

来源目录：`/Users/jiangchunlin/Desktop/桌面 - 蒋春林的MacBook Pro/用所选项目新建的文件夹/5900/老师提交_最终_ACM0002_我们Table标准`。

| 文件 | SHA-256 |
| --- | --- |
| main.py | 7673f05eb0f62a033d20611df5763f47ca68dc9c9170dce5090c378c9bed83d9 |
| field_mapping_acm0002_master.json | d95eeab4a7fc5b25d2dad3c754bc2f0b52c4017716b2d643699b3d5880d28edb |
| method_table_acm0002_independent.json | a3cdda07aae2e1abbb9a0911645d5befb0df90bc4592e0be8a870795a8adb4fa |

`main` → 查找 PDF 文件夹 → `extract_text_from_project` → `extract_pdf_text`
合并页文字 → `extract_project_data_light` 与 `score_dimension` → JSON/CSV。
字段清单和 Method Table 的判定文字没有驱动这两段核心函数。
没有 LLM、Agent 或检索调用。

## 已运行验证

- 字段清单：12 个维度、47 个唯一字段。
- `extract_project_data_light`：23 个输出键。与 47 字段同名的只有
  `project_name`、`technology_type`、`validator_name`、`verifier_name`。
  同名不代表有效：前者实际使用文件夹 ID，技术类型恒为空。
- 合成输入 `Host country: Brazil`、`Installed capacity: 12.5 MW`、
  `Verifier: Example Audit`、`ER: 1,234.5` 能分别提取对应值。
- 空文字评分为 0；每维最高 3 分，总分最高 36。
- 反例：`This project is not grid-connected. Project boundary is undefined
  and applicability is not established.` 在 D01 得 3 分，三个 high 关键词均命中。
  这证明关键词命中无法判断否定语义和证据充分性。

这里测试的是旧代码行为，不是实际项目抽取准确率。尚无冻结人工标签，
不能声称正确率、precision、recall 或 F1 达标。

## 迁移决定

| 旧行为 | Slice 4 处理 |
| --- | --- |
| 12 维关键词、大小写忽略、按模式计数 | 保留版本化 keyword baseline；同一模式多次出现只计一次 |
| high≥3→3；high≥1 或 mid≥2→2；mid≥1→1；否则0 | 保留计算，明确属于关键词基线，非最终质量判定 |
| score/36 称 coverage_ratio | 改为 keyword_score_ratio；字段提取覆盖率单独统计 |
| PDF 页合并后无法定位 | 复用 ParsedDocument，逐页匹配，原文切片形成 EvidenceRef |
| 只选第一个匹配值 | 保留可比较的首命中视图，同时保留不同候选与证据；不裁决冲突 |
| 缺关键词就输出 false | 未找到证据返回 missing；不推断业务上的 false |
| 第一处 MW、ER 等数字 | 作为未验证候选；保留宽泛规则局限和 matched unit，不进入正式结果 |
| 第一处年份作为 vintage_year | 不映射为 ef_vintage_year，年份语义不成立 |
| 文件夹 ID 作为 project_name | project_id 作为输入上下文；真实名称无规则则 missing |
| calibration 关键词即合格 | 不映射为校准合格状态；只保留关键词证据 |
| 提取异常返回空值 | 解析失败沿用 Slice 3 typed failure，抽取不能伪造成功 |
| 老版 0–5、11 规则和最终版 0–3、12 维并存 | 本次只迁移最终版 12 维；不混合总分和权重 |

首批可映射规则：host_country→country、capacity_mw→installed_capacity_mw、
connection_type→grid_connection_status、methodology_claimed→methodology_name、
validator_name、verifier_name、er_claimed→er_reported_tco2e、
be_calculated→be_value_tco2e、pe_calculated→pe_value_tco2e、
le_calculated→le_value_tco2e。数字字段目标单位只是合同定义；未出现原文单位
不能伪装成已经验证或换算成功。developer/owner/operator 等额外旧输出保留在
比较报告中，不擅自增加本轮正式提取字段。

47 字段全部进入共享合同，没有可用规则的字段明确 `unsupported_by_baseline`。
已有规则未匹配为 `not_found`。数据频率、日期、额外性结论等不靠通用关键词
猜测。项目起始日期与计入期尚未进入已审计 47 字段，继续列为范围缺口。

## 验收与学习位置

检查合同验证、原文定位、规则兼容和缺失原因；真实 11 PDF 输出仅用于开发
错误分析。后续人工标注才计算准确率。小样本的匹配多寡不能替代质量评价。

学习重点：baseline 是用来比较的起点；提取覆盖率表示有多少目标字段获得
候选值，准确率需要答案核对，评分高低又是另一件事。
低置信度转人工、草稿错误定位、负责人、修改前后值和 unresolved 都继续
保留在 Slice 6–8 的计划里；本轮合同只承载候选与证据，不实现审核台。

下一步：按 `docs/superpowers/plans/2026-09-17-slice-4-baselines.md`
Task 1 建立共享抽取合同。
