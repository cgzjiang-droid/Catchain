# CATchain 使用说明

## 当前能做什么

当前已实现本地PDF导入、SHA-256去重、文档版本、逐页解析、OCR分流、Regex候选
抽取与12维关键词Baseline。SQLite保存文档与Parsed页面；抽取/评分候选和成功
run记录保存为不可变JSON。真实LLM、调用缓存、显式费用控制和同页候选比较已接入；
机械候选验证与审核分流也已接入；跨字段/语义规则、正式事实库、最终评分、审核台与联网抓取待开发。
完整进度见 [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md)。

## 安装与检查

需要Python 3.12或更新版本及uv。先进入仓库根目录：

```bash
export UV_PROJECT_ENVIRONMENT=venv
uv sync --dev
venv/bin/python -m pytest -q
venv/bin/ruff check .
venv/bin/catchain --help
```

OCR需要在系统单独安装Tesseract及相应语言数据，不是Python依赖。没有OCR工具
时，需OCR的页面会明确报错；不应把错误解释为没有文档或成功提取。

## 1. 导入一份自己的PDF

```bash
venv/bin/catchain ingest local ./project.pdf \
  --registry verra \
  --project-id VCS-1234 \
  --source-url https://真实来源地址/文件.pdf \
  --document-type project_description
```

Registry允许acr、gold_standard、verra。来源地址必须替换成真实地址，项目ID
应与来源一致。document-type还支持monitoring_report、validation_report、
verification_report、registry_export、other。不要把占位示例当认证来源。

默认数据库为data/catchain.sqlite，原文件按Hash存入data/raw。重复相同内容
复用版本。复制输出里的Document version ID用于下一步，不需要手动查询数据库。

## 2. 逐页解析

```bash
venv/bin/catchain parse raw DOCUMENT_VERSION_UUID
```

把DOCUMENT_VERSION_UUID替换为上一步ID。输出JSON里复制parsed_document_id。
原生文字质量不足且页面有内容时会调用OCR，真空白页保留并记录warning。
可通过--tesseract-executable指定工具路径，--ocr-language指定语言。
开发时降低文字量阈值只是对比设置，不等于完成OCR质量验证。

## 3. 抽取候选与关键词评分

```bash
venv/bin/catchain extract baseline PARSED_UUID \
  --project-id VCS-1234 --registry verra
venv/bin/catchain score keywords PARSED_UUID
```

替换PARSED_UUID；项目/Registry必须与导入时一致。输出artifact_path指向JSON
文件，包含result与run。抽取结果保存原值、标准化值、单位、原文页码/片段/位置、
缺失原因和unvalidated状态。同字段不同候选保留，不能当已裁决答案。
关键词分数和keyword_score_ratio只用于Baseline对比，不是项目质量或准确率。

重复运行会返回reused，原文件与原run ID保留。损坏或冲突文件会返回失败，
不会自动覆盖。请先调查原因，不要删除错误证据来让命令通过。

## 自定义存储位置

导入与解析支持--database和--raw-root，抽取与评分支持--database和--output-dir。
同一流程的数据库路径和Raw路径必须一致。数据库、Raw PDF、private候选输出、
个人数据和凭证不上传GitHub；仓库只包含代码、小型测试和文档。

## 当前已知边界

- 55个观察字段的合同不代表Regex已覆盖55字段；没有规则与未命中分别说明原因。
- 原文可定位不代表事实语义、单位或日期已经正确；机械验证已接入，语义/业务规则和人工裁决仍待后续Task。
- 开发pilot的3个来源为明确占位、Gold样本少1项目、OCR工具未安装；不能宣称MVP已通过。
- 成功run在结果JSON里，失败run完整持久化和Canonical数据库表还未实现。

后续按进度表进入真实LLM抽取→验证→事实存储→评估→审核台，保持普通Workflow。

## 4. DeepSeek单次开发抽取

先设置DEEPSEEK_API_KEY环境变量，或在项目根目录.env保存该键（本机已配置，
Git忽略、权限600）。环境变量优先；--config-file可指定本地配置。密钥不发聊天，
不写进代码或提交记录。没有额外dotenv依赖，也不会执行.env内容。

```bash
venv/bin/catchain extract llm-once PARSED_UUID \
  --page 1 --field project_name --field country \
  --database data/catchain.sqlite
```

替换PARSED_UUID。--page、--field可重复指定；字段使用共享合同中的名称。
项目和Registry直接从数据库来源读取。默认deepseek-flash，可用--model选择
明确支持的deepseek-v4-pro。默认输出上限1024 Token，--max-output-tokens最大4096。
选页最多8页/24000字符，页面完整保留；超限失败，不悄悄截断。

相同的已成功输入会复用缓存，不再调用模型；缓存键包含文档版本/Parsed内容、选页、
字段、Prompt、Schema、模型、输出上限和费用配置。任一项改变会产生新调用。每次新
调用最多一次、零自动retry；同键调用正在进行时会停止，避免并发重复计费。API空响应、
截断、非法JSON或假引用会失败，并保留失败记录；失败结果不缓存。
输出artifact_path指向私有cache目录中的不可变结果。runs/<run-id>/started.json和response.json保存
输入身份/配置哈希、模型原始响应、tokens和延迟；失败保存failed.json。
结果仍unvalidated，不写Canonical事实，不生成最终业务评分。

默认estimated_cost_usd为null，表示价格没有由调用者明确配置，不是免费。不要把
当前价格硬编码到项目里；使用当日确认的供应商价格运行，例如：

```bash
venv/bin/catchain extract llm-once PARSED_UUID --page 1 --field project_name \
  --input-cost-per-million-usd 当日输入价格 \
  --output-cost-per-million-usd 当日输出价格 \
  --max-estimated-cost-usd 本次最多金额
```

只有输入和输出价格同时提供时，系统才按真实返回Token记录estimated_cost_usd。
设置金额上限时价格是必填项；系统在请求前按输入字节上界和最大输出Token做保守估算，
超过上限就不联网。Token是模型计量单位，字符/字节上界不是精确输入Token数。
首次真实调用验证见docs/validation/2026-09-17-slice-5-first-real-call.md。

离线测试不会联网或计费：

```bash
venv/bin/python -m pytest tests/unit/extraction tests/integration/test_llm_cli.py -q
```

## 5. 在同一输入上比较Regex与LLM

```bash
venv/bin/catchain compare extraction LLM_ARTIFACT \
  --database data/catchain.sqlite
```

LLM_ARTIFACT替换为llm-once的artifact_path，也支持保留完整started记录的旧真实run。
比较只读取已有结果，不联网、不请求模型。它从原始处理记录读取选页与字段，校验
文档/来源/run/哈希/证据后，让Regex读取相同页面，保留原PDF页码。

输出报告包括same_values、different_values、llm_only、regex_only和both_missing；
每项保留双方原值、单位、缺失原因、证据和冲突。same_values按值与单位精确比较，
不是事实裁决；both_missing也不是答对。没有人工Gold时accuracy=null。
重复比较复用不可变报告和原run，--output-dir可自定义私有报告目录。

## 6. 验证候选并查看待审核原因

```bash
venv/bin/catchain validate extraction EXTRACTION_ARTIFACT \
  --database data/catchain.sqlite
```

EXTRACTION_ARTIFACT替换为Regex或llm-once的artifact_path。程序核对数据库来源、
成功抽取run与内容哈希，输出私有验证报告；不联网、不请求模型、不写Canonical。
报告checks保留每条原候选及其索引、原页码/原文/位置、问题code和message。

missing表示明确弃答；rejected表示机械错误，原值仍保留；needs_review表示需要
裁决，不能当正式事实。完整ISO日期与存在的引用也不会跳过语义审核。
默认confidence-threshold为0.8，可显式配置；没有置信度不等于高置信度，阈值未做Gold校准。
未定义的业务类型返回field_contract_pending，不凭字段名猜合同。

报告run的succeeded仅代表验证处理已完成，不代表每个候选通过或允许上线。
重复执行复用不可变报告与run，--output-dir可以自定义私有位置。

## 7. 跨字段与来源差异检查

```bash
venv/bin/catchain validate project VALIDATION_A VALIDATION_B --database data/catchain.sqlite
```

输入同一项目的机械验证报告。保留差异候选和来源版本，状态为unresolved；不自动选新版。
真实多文档验收尚未完成。完整说明见docs/validation/2026-09-17-slice-6-consistency.md。

## 8. 把验证候选与证据存入数据库

```bash
venv/bin/catchain store validation VALIDATION_ARTIFACT \
  --extraction-artifact EXTRACTION_ARTIFACT --database data/catchain.sqlite
```

VALIDATION_ARTIFACT为validate extraction输出，EXTRACTION_ARTIFACT为对应Regex/LLM原抽取输出。
项目原数据库必须存在，且保存了所引用的Parsed/版本/来源；首次执行添加缺少的新表。
先备份重要数据库。本命令采用create_all添加表，不为旧库自动stamp Alembic版本。
已由Alembic维护的数据库可配置alembic.ini的sqlalchemy.url后执行venv/bin/alembic upgrade head。
旧create_all数据库不要直接运行全量初始迁移；需先核对现有结构并制定迁移基线。

输出candidate_count包括缺失记录。所有原候选、问题和证据保留；每次导入是完整事务。
重复同一run复用；同一run内容变更拒绝。canonical_writes与model_calls均为0。
本步无审核裁决入口，不可直接把候选表当正式事实。数据库及运行artifact不上传GitHub。

以上是Task 3边界；Task 4现已提供以下明确审核入口。

## 9. 人工裁决与正式事实

先获取候选ID、原值/证据和当前正式版本：

```bash
venv/bin/catchain review candidates VALIDATION_RUN_ID --database data/catchain.sqlite
```

VALIDATION_RUN_ID来自store validation输出。创建私有裁决JSON，示例为无法确定：

```json
{
  "decision_id": "替换为新UUID，重试时保留",
  "candidate_id": "替换为候选ID",
  "reviewer": "实际审核人",
  "reason": "证据不足，无法确认权威来源",
  "status": "unresolved",
  "expected_current_fact_id": null
}
```

expected_current_fact_id使用候选查询返回值；已有正式值时必须填对应ID。
decision_id可通过venv/bin/python -c 'import uuid; print(uuid.uuid4())'生成。

```bash
venv/bin/catchain review decide data/review/my-decision.json --database data/catchain.sqlite
```

拒绝候选使用status=rejected。两种状态都不填after，不改已有正式事实。
批准使用status=approved、authority_confirmed=true，并填after为完整FieldObservation。
可复制候选查询的check.observation，人工修正raw_value、normalized_value、unit和对应证据。
evidence必须包含同版本PDF页码、原文quote、char_start/char_end（当前页面中的字符位置），不能只改值而保留无关证据。
修改来自新文档时先对新版本重新解析/抽取/验证/入库，审核新候选；不能拿旧候选冒充新来源。

批准重新检查类型、完整日期、单位和引用位置，并核对已有计入期起止日期顺序。
没有定义的字段合同、单位未确认或模糊日期不能通过本入口强行批准。
语义和来源权威由审核员确认；系统不具备自动权威判断或审核账号认证。
首次批准写入正式历史，修改追加新版本；原候选、旧正式值、理由和修订证据全部保留。
同decision_id同输入重试复用；内容变化需新ID；审核期间正式值已变化则返回stale_current_fact。
格式/证据失败返回status=draft和错误位置，将原输入保存至data/review/drafts，可用--draft-dir修改。
修正草稿后再提交，失败不会留下正式值。所有审核文件和草稿均为私有、被Git忽略。

## 10. 检查12维评分准备度

```bash
venv/bin/catchain score readiness --registry acr --project-id ACR125 \
  --database data/parsed/slice6-facts-pilot-v2.sqlite
```

替换为自己的Registry/项目和数据库。数据库需有Slice 6表结构，本命令不创建或迁移表。
输入只来自当前已批准正式事实，不使用未审核候选；输出私有不可变报告及处理run。
报告每维列出input_fields、available_fields、missing_fields、fact_ids和待定义状态；facts保留证据链。
methodology_scope只有已批准methodology_name严格为ACM0002时标明范围已确认，仍不是官方适用性认证。
没有正式事实时列出缺失，不能把结果当作项目不合格；score/weight/total_score均为null。
字段齐全也只标rubric_pending。此命令是准备度检查，不是最终评分；不联网、不调用模型。
重复当前事实快照复用；新的正式版本产生新的报告，不覆盖旧快照。

## 11. 方法学、周期与算术检查

2026-09-18新增产品规则草案：docs/product/2026-09-18-scoring-rubric-review.md。
对应scoring/acm0002-quality-rubric-draft-v1.json仅供审查，现有命令不会据此自动评分。
后续v2见docs/product/2026-09-18-scoring-criteria.md，新增36个判定项ID与审核输出要求，仍未启用。

```bash
venv/bin/catchain score checks READINESS_ARTIFACT --database data/catchain.sqlite
```

READINESS_ARTIFACT来自score readiness的artifact_path。没有上下文时仍会保存阻止原因报告。
当前正式事实已改变时旧报告会被拒绝，请重新生成readiness；报告被修改也会拒绝。

人工确认后，可用--context-file data/review/assessment-context.json提供上下文。
合同见schemas/generated/assessment-context.schema.json：

- reviewer/reason：实际负责人和明确理由；authority_confirmed：来源权威是否已确认。
- methodology_fact_id/methodology_version_fact_id：准备度facts中对应正式事实的ID。
- period_start/period_end：完整YYYY-MM-DD起止日期，不能颠倒。
- period_fact_ids：把electricity_generated_mwh、electricity_exported_mwh、be_value_tco2e、pe_value_tco2e、le_value_tco2e、er_reported_tco2e中实际要比较的字段映射为其正式fact_id。
- evidence：支持周期与版本/权威判断的EvidenceRef数组，包含原版本、页码、quote和字符位置。

程序验证上下文引用位于本项目当前正式事实的Parsed来源中；引用语义与权威需人工确认。
这是单机可信操作员输入，不是审核账号认证，不是自动官方方法学版本白名单。

减排量诊断要求BE/PE/LE/ER四个正式值都有周期绑定、非负有限数值且单位tCO2e。
输出BE-PE-LE、报告值减复算值、绝对差异/报告值百分比（报告值0时null），只作为历史代数诊断。
不会自动判合规、不会给0–3分、不会写入正式事实。旧Rubric、容差、权重和官方版本仍需确认。
上下文和报告保存私有位置，重复输入复用；--output-dir可设置检查报告目录。

## 12. 保存逐项人工判定

```bash
venv/bin/catchain score judgments READINESS_ARTIFACT \
  --request-file data/review/judgments.json --database data/catchain.sqlite
```

输入示例（实际填写负责人及理由）：

```json
{
  "rubric_version": "acm0002-quality-rubric-draft-v2",
  "reviewer": "实际审核人",
  "judgments": [{
    "criterion_id": "D01.C1",
    "outcome": "insufficient",
    "reason": "当前缺少项目边界证明",
    "fact_ids": [],
    "evidence": []
  }]
}
```

supported/not_supported/not_applicable必须填正式fact_ids及定位evidence，不能空证据下结论。
事实必须属于当前readiness对应项目和该维度；证据必须定位于所引用事实对应原文。
readiness过期或被修改时会拒绝保存，请重新生成并核对人工判断。
输出judgment_count和unreviewed_count；artifact还会按D01-D12列出每个维度的审核覆盖、未审核criterion、逐项判定、status、score和weight。
当前草案的score_status为pending_policy，score、weight和total_score仍可为null，模型调用0；有判定不等于已经得分。
结果保存为私有不可变JSON+run，并在数据库evaluation_results中保存项目、草案哈希、状态和完整payload；重复相同输入复用，改变输入形成新历史artifact。
数据库需要先执行`venv/bin/alembic upgrade head`，输出还会返回evaluation_result_id。
如果是旧版`create_schema`创建且没有`alembic_version`的数据库，确认已有0004表结构后先执行`venv/bin/alembic stamp 0004_review_heads`，再执行upgrade；不要直接从0001重复创建旧表。
结果合同的JSON Schema位于`schemas/generated/evaluation-result.schema.json`，可用`venv/bin/catchain schema export`重新生成全部13个Schema。
本命令保存草案审核意见，不等于正式质量评级，也不会写入Canonical；evaluation_results只保存可追溯的草案结果，不代表正式分数。
