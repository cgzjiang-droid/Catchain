# CATchain 项目与学习进度

更新时间：2026-09-18

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
| 5 | Provider-neutral 与真实 LLM 结构化抽取 | 开发闭环完成 | 真实DeepSeek、缓存/运行记录、同页Regex比较；未认证准确率 |
| 6 | Evidence、领域、冲突验证和 Canonicalization | 开发闭环完成 | Task 1–4：验证、差异、候选/证据库、明确人工裁决；业务权威矩阵与Gold验收仍待补充 |
| 7 | 12 维评估、人工作答对比 | 工程闭环完成 | 评估合同、证据门、策略激活门、冻结Gold评估和数据集聚合已完成；正式规则与真实Gold是上线前准入条件 |
| 8 | 审核台、反馈、产品指标 | 工程闭环完成 | CLI/JSON审核队列、草稿纠错、修改前后值、证据定位和指标快照已完成；独立前端仍非MVP必需 |
| 9 | Review Agent | 未开始 | 仅在前置质量条件满足后进入 |

## 已完成工作

### Slice 7：判定结果合同与保存入口

新增JudgmentRequest合同和score judgments CLI，核对草案criterion_id、当前正式事实及引用位置。
支持部分审核并列出未审核项，不将弃答当失败；明确结论必须有事实与证据。
保存readiness快照、完整人工输入、草案哈希和处理run；相同输入复用，修改追加历史。
这部分属于Task 3的输入/理由/证据保存基础；EvaluationResult合同在入库前校验D01-D12覆盖、状态分区和空分值；artifact按D01-D12保存审核覆盖和逐项判定摘要，新增evaluation_results表保存项目、rubric哈希、状态和完整payload，仍无分值计算。
正式业务规则仍待确认，但工程边界已关闭：没有approved策略时，结果明确保持pending_policy和空总分。
锁文件临时环境验证126项测试通过，包含此前两版规则草案测试；原开发环境未替换。
真实ACR125离线试跑保存1项明确标注为Codex测试的insufficient记录，35项未审核，重复复用成功；总分null，模型调用0。

### Slice 7 Task 4：Gold 样本合同基础

新增GoldSample和GoldFieldLabel合同，区分confirmed、unknown、conflicting；confirmed必须有值和原文证据。
样本只有在两名审核员、组长裁决、冻结时间齐全且没有未裁决冲突时才能标记frozen；未知可以保留为unknown，不转成错误或0分。
新增gold-sample.schema.json和两项冻结规则测试。当前没有把Codex离线试跑或模型输出冒充真实Gold，Task 4仍未完成独立样本集和指标计算。
新增frozen Gold离线比较函数和`evaluate gold` CLI，输出字段级agreement、confirmed_accuracy和unknown_abstention_rate；没有配置数值容差，证据只检查候选是否携带引用，尚未接入真实人工数据。
新增GoldDataset清单合同，校验版本、样本ID和项目级split隔离；真实样本数量与分层仍待人工确认。
新增`evaluate dataset`聚合CLI，要求选定split的报告完整覆盖，按字段计数汇总accuracy，暂不把不完整样本集当作指标。

### Slice 7 工程闭环验收

Slice 7 的代码、Schema、不可变artifact、数据库索引、冻结Gold比较和数据集聚合均已完成。
`135 passed`，源仓库与GitHub发布快照逐文件一致；没有把个人数据目录上传到GitHub。
正式权重、方法学适用条款、0–3业务含义和真实人工Gold仍是外部准入输入，不能由代码自动生成或冒充确认。
因此当前系统可以完整评估“是否可评分”和“抽取/人工答案如何对比”，但在这些输入到位前不会生成正式质量总分。
验收记录见`docs/validation/2026-09-18-slice-7-closeout.md`；下一步进入Slice 8审核台。

### Slice 8：审核队列与反馈指标

已完成第一版可审计审核入口：`review queue`按问题严重度、证据完整度和审核状态生成可排序队列，默认隐藏已批准候选；`review metrics`统计待审核量、审核结果、Evidence覆盖率、字段覆盖率、返工数和审核延迟。
队列和指标均以内容哈希保存为不可变JSON，并由Pydantic Schema校验；没有把审核指标包装成模型accuracy或正式总分。
CLI/JSON工作流已经完成Slice 8 MVP验收；独立前端和批量操作可作为后续产品迭代，不阻塞当前主链。
验收记录见`docs/validation/2026-09-18-slice-8-closeout.md`。

### Slice 7 Task 2：评分策略激活门

新增ScoringPolicy合同和Schema：draft可保留空权重；approved必须包含D01-D12全部权重、权重和为1、权威来源、审核人和日期。
这只是防误激活的工程门，不代表任何官方规则或业务权重已经确认，正式策略仍需人工批准。

### Slice 7 Task 2：36个可追溯判定项

规则草案v2新增12维共36个稳定criterion_id，区分支持、不支持、证据不足、冲突、不适用。
每项要求理由、正式fact_ids与原文证据；程序检查和人工语义判断分开。
各项关键程度、分值映射与完整官方条件仍待确认，不自动按supported数量打分。
保留v1，v2未启用；下一步建立判定结果合同与保存入口。

### Slice 7 Task 2：2026-09-18业务规则草案

新增12维证据要求、内部0–3判分提案及审核输出清单，位于scoring/acm0002-quality-rubric-draft-v1.json。
状态draft_not_executable，权重未确定，现有评分命令不加载，正式总分仍null。
核对UNFCCC版本目录和Verra过渡说明，确认不能只凭方法学名称/版本证明Registry适用。
ACR/GS适用规则、全文条款/工具审核、具体判定项、容差和真实样本业务确认仍待完成。
本次无模型调用，无正式事实或评分写入。Task 2仍在进行，下一步细化具体判定项与适用证据。

### Slice 7 当前检查点：Task 2技术检查

新增AssessmentContext合同，绑定具体方法学及版本的正式fact_id、人工确认的周期、计量事实ID和原文证据。
score checks核对准备度run/哈希与当前正式快照，旧快照或修改过的报告拒绝执行。
BE/PE/LE/ER齐全、事实ID正确、周期有明确绑定且单位均tCO2e后，才输出历史BE-PE-LE算术诊断。
不省略PE/LE，不把缺失当0，不自动换算，不设未经确认的容差；报告ER为0时误差百分比为null。
context权威/周期语义是可信操作员声明；程序只核查引用存在及位置，不具有自动官方版本认证。
真实ACR125：方法学范围未确认、版本缺失、上下文缺失，复算blocked，总分null，0模型调用。
122项测试通过；测试样例算术复算通过不等于真实项目合规或业务准确率达标。
Task 2正式业务规则部分仍进行中：下一步补充逐维证据要求与适用版本，再落实0–3判定。

### Slice 7 当前检查点：Task 1

重新核验旧12维Method Table、47字段映射和实际关键词评分调用链。
新增acm0002-readiness-v1目录和score readiness CLI，仅读取当前已批准事实，保留完整来源与裁决链。
逐维列出已具备/缺失输入；字段齐全仍为rubric_pending，权重、分值和总分均未确定。
真实ACR125：0已批准事实、12维不可评分、总分null、0模型调用，重复复用成功。
116项测试通过；真实Gold、业务充分性、方法学版本与周期规则尚未认证。
下一步Task 2：落实业务判定与周期/适用版本输入，逐维评估，不直接照搬关键词分数。

### Slice 6 当前检查点：Task 4

review candidates列出候选ID、原检查/证据及当前正式值ID；review decide读取人工裁决JSON。
批准需审核人、理由、明确权威确认和完整证据候选，重新通过机械检查后才生成正式事实。
拒绝或unresolved只追加记录；原候选与已有正式值保留。同一decision_id完全重复复用，变更拒绝。
canonical_heads指向当前版本，canonical_facts保留所有已批准历史；expected_current_fact_id防止旧视图覆盖新提交。
新增review_requests保存完整输入、修订证据与策略版本manual-reviewed-v1；Alembic 0004添加两张表。
格式/证据错误保留私有草稿，返回位置和错误code；写入失败整体回滚。
真实ACR125只执行明确标注为Codex离线试跑的unresolved路径，重复复用，0正式写入、0模型调用。
批准与改值目前由测试样例验证，没有冒充真实人工审核或Gold。
这是单机可信操作员MVP，reviewer为输入声明，不是账号认证；多用户权限、完整字段权威矩阵和审核台UI仍待实现。
下一步Slice 7：检查旧12维评分含义/输入/权重，基于已批准事实设计评分与人工作答评估。

### Slice 6 当前检查点：Task 3

新增6张独立表：processing_runs、validation_reports、fact_candidates、candidate_evidence、review_decisions、canonical_facts。
store validation要求原始抽取与验证两个artifact，核对项目/文档/页码/run，事务保存候选、证据与完整原抽取。
同一run完全相同则复用，变更拒绝覆盖；模拟证据写入失败验证整体回滚。
外键启用，Alembic 0003与运行时表定义一致；旧来源记录经升级/降级测试保持。
真实ACR125在原数据库备份上导入4条候选记录（含2条缺失）、2条证据、0条正式事实、0次模型调用。
review_decisions与canonical_facts本步只有表定义，没有审核或正式写入入口。
一致性报告仍保存在独立JSON审计文件，本步数据库导入范围为单抽取的机械验证报告。
下一步Task 4：审核人、理由、原证据、修改前后值、UNRESOLVED、草稿错误位置与幂等性。

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

当前任务：Slice 8审核队列与人工纠错闭环。

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
- 真实LLM已在Slice 5接入；完整事实库、最终评估和审核台尚未实现，不宣称已完成重构。

下一步按Slice 8计划执行：

1. 将低置信度、证据缺失、冲突和日期/格式错误汇总为可排序审核队列。
2. 在审核入口展示错误位置、原文证据、修改前后值和负责人。
3. 记录审核耗时、通过率、未解决率和重复返工原因，为后续灰度准入提供指标。
4. 保留Slice 7的准入边界：没有冻结Gold和approved策略时，不宣称准确率或正式总分。

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
- Prompt、DeepSeek adapter、单次CLI、成功/失败run文件、调用前缓存和费用上限已实现。
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
- Task 3完成：同一成功输入复用缓存；同键进行中阻止重复调用；失败不缓存。价格未明确
  配置时费用仍为null；用户可传入当日输入/输出价格和本次金额上限。

### Slice 5 Task 4验收

- compare extraction完成同页同字段候选比较，保持原PDF页码；核对run/hash/来源/证据。
- 复用真实ACR125第1页响应：2个LLM独有候选、2个双方缺失。没有新增API费用。
- 重复比较复用报告和run。模型缓存读取也验证候选Schema、输入身份与原文位置。
- 验证报告：`docs/validation/2026-09-17-slice-5-same-pages.md`。
- 所有候选仍unvalidated；单样本不认证准确率、生产稳定性或上线资格。

### Slice 6 Task 1：验证报告与审核分流

- 新增ValidationIssue、CandidateValidation、ExtractionValidationReport及第8个Schema。
- validate extraction核对来源/run/内容，检查已定义字段类型、日期、单位、原文位置和冲突。
- 低于0.8分流阈值、缺置信度、模糊日期、未知业务合同与语义支持待确认均保持待审核。
- 原候选与证据完整保留，分别输出missing/rejected/needs_review；没有自动事实写入。
- 真实ACR125候选验证：2待审核、2缺失、0拒绝；重复复用报告；没有新增API请求。
- 跨字段/文档/版本规则、Canonical数据库、审核裁决输入仍待后续Task。
- 94测试、Ruff、wheel构建与8个Schema检查通过；验证报告见
  `docs/validation/2026-09-17-slice-6-mechanical-validation.md`。
