# CATchain 项目与学习进度

更新时间：2026-09-17

本文件把正式产品计划、已经实现的代码、真实数据验证和产品经理学习放在
同一条进度线上。详细架构以
`docs/superpowers/specs/2026-09-09-catchain-redesign.md` 为准。

## 总体进度

| Slice | 目标 | 状态 | 当前成果 |
| --- | --- | --- | --- |
| 1 | 项目基础、领域模型、Schema、测试 | 已完成 | SourceDocument、DocumentVersion、EvidenceRef、PipelineRun、JSON Schema |
| 2 | Raw 导入、SHA-256、去重、版本、SQLite | 已完成 | 不可变原文件存储、本地导入服务、数据库、CLI |
| 3 | Parsed 层、页面质量、OCR fallback | 已完成 | Parsed合同、原生解析、OCR分流、持久化和CLI |
| 4 | 迁移 Regex 抽取和关键词评分基线 | 基线闭环完成 | 合同、逐页Regex、标签规则、独立关键词评分与CLI；补充旧资产仍有backlog |
| 5 | Provider-neutral 与真实 LLM 结构化抽取 | 进行中 | Task 2真实DeepSeek单次抽取完成；调用前缓存/费用控制待实施 |
| 6 | Evidence、领域、冲突验证和 Canonicalization | 未开始 | 已收集产品规则，待实现 |
| 7 | 12 维评估、人工作答对比 | 未开始 | 已确定 Gold Standard 原则 |
| 8 | 审核台、反馈、产品指标 | 未开始 | 已确定人工介入和审计要求 |
| 9 | Review Agent | 未开始 | 仅在前置质量条件满足后进入 |

## 已完成工作

### Slice 1：Domain Foundation

- 创建 Python 项目、锁定依赖并建立测试与 Ruff 检查。
- 区分逻辑来源文档与实际内容版本。
- 使用 SHA-256、版本身份和不可变模型保证可追溯性。
- 建立页码、原文片段和字符位置 EvidenceRef。
- 建立 PipelineRun 生命周期和结构化失败记录。
- 自动生成稳定 JSON Schema。
- 写入第一阶段项目学习资料。

### Slice 2：Raw Ingestion

- 按内容 Hash 保存不可变 Raw 文件并自动去重。
- 使用 SQLite、SQLAlchemy 和 Alembic 保存文档与版本元数据。
- 建立本地文件导入服务。
- 提供 `catchain ingest local` 命令。
- 验证重复导入不会产生重复版本。
- 写入 Raw、版本和幂等性学习资料。

### Slice 3：已完成部分

- Task 1 已完成：`TextQuality`、`ParsedPage`、`ParsedDocument`。
- Task 2 已完成：PyMuPDF 逐页原生文字解析、质量指标和解析器版本记录。
- Task 3 已完成：确定性质量规则、空白页识别和 Tesseract OCR adapter。
- Task 4 已完成：Parsed数据库表、repository、`parse raw` CLI和结构化失败。
- 真实数据检查点已完成：11 个项目、11 份核心 PDF、527 页全部成功解析。
- 发现 32 个低文字量页面；其中 3 页经渲染确认是真空白页。
- 产品规则因此修正为三路分流：保留原生文字、执行 OCR、记录空白页。

## 当前准确位置

当前分支：`codex/slice-3-parsing-ocr`

当前任务：Slice 5 Task 2已完成，并接入llm-once CLI；下一步Task 3缓存和费用控制。

Slice 4 已完成：

- 审计旧版实际调用链：23个输出键，不等于47字段全部已提取。
- 验证关键词评分不理解否定语义，记录反例和源文件Hash。
- 完成四任务实施计划：`docs/superpowers/plans/2026-09-17-slice-4-baselines.md`。
- Task 1：实现FieldObservation、ProjectExtraction和两个生成Schema。
- 合同支持47字段及country上下文；候选值必须有证据，缺失必须说明原因。
- 原文是否真实匹配、业务字段类型、日期与单位正确性仍由Slice 6验证。
- Task 2：基础逐页Regex已输出11 PDF开发候选；原文切片检查通过。
- 指定最终交付包已核对：28个顶层输出键，含公司/标题/计入期；历史23键结论不能套用。
- 历史项目JSONL已逐行解码：ACR 3、GOLD 541、VCS 741，共1285条，正确性未认证。
- 真实LLM、完整事实库、最终评估和审核台尚未实现，不宣称已完成重构。

下一步按现有计划执行：

1. Slice 5先定义provider-neutral抽取输入/输出、页面选择、失败与有界retry。
2. 编写详细实施计划，复用共享合同、Parsed、Evidence和run身份。
3. 实现fake adapter做离线验证，再接一个真实LLM；不能把fake输出称为真实AI。
4. 保留Registry联网adapter、完整公司实体解析与Gold样本缺口，不遗漏也不混入已完成能力。

## 已讨论产品规则在计划中的位置

| 已讨论内容 | 所属计划位置 | 当前状态 |
| --- | --- | --- |
| sensor、observation、environment、action、actuator、performance | Agent 产品经理学习；Slice 9 的概念基础 | 已学习，尚未进入生产 Agent |
| 低置信度转人工 | Slice 6 验证、Slice 8 审核台 | 产品规则已记录，阈值需 Gold Standard 校准 |
| 必填字段、日期格式和 Evidence 必须验证 | Slice 6 | 已形成要求，待实现 |
| 草稿保留并直接标出错误位置 | Slice 8 | 已形成审核台要求，待实现 |
| 保存修改前后值、负责人和证据 | Slice 8 | 已形成审计要求，待实现 |
| 新版本重新走审核、旧版本不覆盖 | Slice 2、6、8 | 版本基础已实现，重审流程待实现 |
| 两名审核员冲突、组长裁决、无法确定则 unresolved | Slice 7、8 | Gold Standard 规则已记录，待实现 |
| 影子测试、准入条件、灰度、暂停与降级 | Slice 7、8 | 上线策略已记录，待评估功能完成后执行 |
| 30GB 手机数据、电脑空间不足 | Dataset Discipline | 全量数据留在手机；当前使用本地只读子集开发 |

具体的 ACM0002 提取范围已经从老师最终版资料中审计出来：12 个维度、
47 个评分输入字段，以及 Registry、国家和字段级证据等上下文。清单见
`docs/product/ACM0002_EXTRACTION_FIELD_INVENTORY.md`。它已在 Slice 4 Task 1 转换为
`ProjectExtraction` 和 `FieldObservation` JSON Schema；基础Regex已完成Task 2。
原47字段只代表评分输入，完整业务的company/location/crediting dates需Task 2B补齐。

## 本次正式重构指令对齐

旧业务主来源为 `/Users/jiangchunlin/Desktop/最终交付_ACM0002_20260513 5`，
其他历史代码继续作为版本化参考。开源参考仍为carbon-methodology-archive，
借鉴来源、hash、metadata和版本设计，不Fork改名、不复制拼接、不改变业务目标。
对照见 `docs/audit/2026-09-17-final-delivery-reconciliation.md`。
真实Registry URL与抓取adapter审计、联网下载、增量同步尚待实现；不得遗漏。

## 数据集状态

- MVP 目标：9–15 个项目，ACR、Gold Standard、VCS 各 3–5 个。
- 本地已发现：ACR 5、Gold Standard 2、VCS 4，共 11 个项目。
- 总项目数满足范围，但 Gold Standard 少 1 个项目；这是明确的数据缺口。
- 手机中的约 30GB 全量数据不需要复制进仓库。等小样本流程稳定后再设计
  手机、移动硬盘或分批导入方案。

## 防止偏离计划的执行规则

每次开始工作先写明 `Slice / Task / Step`。新增发现必须放回当前 Slice 的
真实输入验证或错误分析步骤；如果改变范围，先更新正式计划。只有当前 Slice
达到验证条件后，才进入下一 Slice。

## Task 2B子任务成果（2026-09-17）

- 明确标签的标题、公司角色与计入期已实现；Schema 1.1.0支持55观察字段。
- 候选显式unvalidated，日期不猜月日；修正ISO日期被截为年份的问题。
- 调用者需传入run ID；开发输出附独立PipelineRun JSON，数据库run链待接入。
- 同样11 PDF已运行，新增标签规则覆盖有限，标题0命中；没有强行猜值。
- 57测试与Ruff通过。旧数据、旧baseline、v1开发输出均保留。
- 通用公司识别、location、Registry URL审计尚未完成；Task 2B整体未完成。

## Task 2B资产审计检查点完成

- 实际抓取器与ACR/Verra/GS发现调用链已核对；历史端点线上可用性未验证。
- ACR两份索引各22条，找到22/15文件；Verra30条均找到文件，完整性未认证。
- 旧GS非200→空列表、半文件跳过、分页异常和公司拆分损坏等问题已记录。
- 详细规则、来源行号和backlog见 `docs/audit/2026-09-17-registry-collectors-company-assets.md`。
- 已完成的是资产审计，不是联网下载或完整公司实体解析。下一步按原计划进入Task 3。

## Task 3完成：独立关键词baseline

- 最终交付12维规则与源文件Hash已保存为包内JSON，运行时不导入旧脚本。
- 评分输入为Parsed页面，和事实抽取分离；输出关键词分数、high/mid计数与页级证据。
- keyword_score_ratio不是字段覆盖率或准确率；否定语义与跨页匹配是明确局限。
- 11 PDF、527页的12维分数及计数均与旧代码一致；36项合成维度对比通过。
- 打包wheel在仓库外可读取规则。真实LLM、最终业务评分、联网adapter仍未实现。
- Task 4需要补CLI、正式版本身份和run/产物复用，不将开发JSON当生产评估。

## Task 4完成：可运行的baseline CLI闭环

- extract baseline与score keywords使用真实SQLite Parsed/version/source身份。
- 项目/registry不符、未知Parsed ID、结果损坏与写入失败返回结构化错误。
- 结果和成功PipelineRun存在同一不可变JSON文件，含输入与配置Hash。
- 同样输入复用文件与原run ID；原子发布不覆盖同名结果。复用仍重新计算轻量baseline。
- 11 PDF、527页完整开发CLI已运行；所有抽取证据切片定位、抽取/评分复用通过。
- 8份找到历史来源URL，3份使用明确的example.invalid开发占位地址，不能视为已证实来源。
- OCR工具未安装，本次min-non-whitespace=0只用于原生文本比较；默认OCR路径不因此称完成验证。
- 每份匹配1–10个观察字段（合同共55字段），存在不同候选；未做人工裁决或准确率评估。
- 60测试、Ruff和7 Schema稳定再生成通过。旧版比较和额外company输出保存在忽略目录。
- 失败run的持久化、事实/evidence/最终评分数据库表仍待后续阶段；JSON闭环不等于完整平台完成。

## Slice 5 当前检查点

- 已完成响应合同、显式选页和引用定位检查，6项新离线测试通过。
- 实施计划：`docs/superpowers/plans/2026-09-17-slice-5-llm-extraction.md`。
- 学习资料：`docs/learning/05-llm-extraction-boundary.md`。
- 用户选择DeepSeek；本机API鉴权成功，本地.env已配置（Git忽略、权限600）；已完成一次真实抽取。
- Prompt、DeepSeek adapter、单次CLI和成功/失败run文件已实现；调用前缓存、费用上限仍待实施。
- 所有LLM候选保持unvalidated；Slice 6的语义/业务验证未提前宣称完成。

### DeepSeek API配置检查点

本地.env保存DEEPSEEK_API_KEY（不上传），权限600。GET /models鉴权成功，
返回deepseek-flash、deepseek-v4-pro。随后以deepseek-flash完成一次生成抽取。
llm-once已读取环境变量或本地.env；优先环境变量，不执行配置内容。

### Slice 5 Task 2验收

- DeepSeek真实抽取ACR125第1页，4字段中2候选、2明确弃答，引用均可定位。
- 输入1212、输出223 Token、耗时约1.60秒。结果仍unvalidated，不报告准确率。
- 75项测试、Ruff和wheel构建通过；成功/失败记录与原始响应保留在私有目录。
- 验证报告：`docs/validation/2026-09-17-slice-5-first-real-call.md`。
- Task 3未完成：llm-once无缓存，重复可能计费；费用未知null，尚无货币预算。
