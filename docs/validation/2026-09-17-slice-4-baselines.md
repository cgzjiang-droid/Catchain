# Slice 4 / Task 2 开发验证

状态：基础标量Regex已实现；完整最终交付baseline、关键词评分和CLI尚未完成。

输入为原有11份开发PDF，共527页。只读原文件，使用PyMuPDF原生文字；本次
不重新执行OCR。输出在忽略目录 `data/extracted/pilot-2026-09-17/`，包含11份
候选JSON与summary.json。没有把历史1285项目全量搬入新库。

972个候选，逐份PDF匹配1–8个不同字段；当前规则仅支持10个字段。
所有已输出EvidenceRef都验证原文页内切片与quote相等。这个检查证明可定位，
不证明候选语义正确。未冻结人工答案，不报告accuracy/precision/recall/F1。

与指定最终交付脚本比较容量和ER/BE/PE/LE五个首命中值：55项比较中50项一致，
包括双方均无值的情况。5项不同均因旧规则第一个数字capture为逗号，旧函数
返回None，新实现跳过非法capture后继续找候选；均非跨页匹配差异。
这些结果保留为行为差异，不能将50/55当正确率。

故障与局限：短缩写正则可命中无关文本，数字单位尚未验证，关键词并网候选
不处理否定语义。candidate issues已标记broad_numeric_rule、unit_not_verified、
keyword_presence_not_business_status；不允许进入Canonical数据。
质量screen与低文字页面仍见Slice 3 pilot，不声称OCR后完整召回。

开发pilot使用从源文件Hash派生的临时version UUID，不是SQLite导入生成的版本。
Parsed ID与抽取器版本保留在输出，真实run和入库身份链待CLI/持久化阶段补齐。
这些JSON不能作为正式评估或生产数据。

验证：`venv/bin/python -m pytest -q`：56 passed；
`venv/bin/ruff check .`：通过。新测试覆盖不同页容量候选、48个字段名、缺失
原因、未知置信度与证据切片。原文文件和旧交付结果均未修改。

## Task 2B subtask: explicit business fields

Same 11 PDFs, 527 pages; source SHA-256 values rechecked. Original v1 outputs kept;
new ignored output: data/extracted/pilot-2026-09-17-v2/.
New-rule candidate counts: title 0, owner 0, developer 1, participant 2, operator 0,
crediting years 2, start date 1, end date 0. This is not precision or recall.
One numeric date flagged ambiguous; all emitted page slices match their quotes.

Synthetic title and crediting values match the specified final-delivery function.
ISO date test exposed truncation of 2020-03-04 to 2020; now the full string survives,
with a numeric boundary guard. Dates remain date_not_validated.

Each output has caller-supplied pipeline_run_id and a paired PipelineRun JSON:
Parsed input hash, rule/schema config hash, successful status and times.
No database run table is populated; development document-version IDs remain synthetic.
Old schema 1.0.0 loads without invented identity; schema 1.1.0 rejects missing run ID.
57 tests passed and Ruff passed. Generic companies, location, URL audit and CLI remain open.

## Task 3：关键词baseline

规则JSON逐项对照最终交付DIMENSION_RULES与源文件Hash，完全一致。3组合成输入
逐一比较12维score/high/mid计数，共36个维度对比通过。可运行单测试覆盖0–3
分阈值、大小写、重复/跨文档只计一次、页级切片、空输入和否定语义局限。

11份开发PDF、527页重新读取原生文字，源Hash核对通过；每份12维分数与high/mid
计数均与旧代码一致，原文证据切片通过。输出忽略目录：
data/extracted/keyword-pilot-2026-09-17/。分数依次为ACR125 25、ACR129 18、
ACR177 31、ACR191 32、ACR224 32、GS1003 15、GS1012 29、VCS1 26、VCS6 29、
VCS7 29、VCS10 29；最高36。这些不是经过验证的项目质量评分。

keyword_score_ratio直接计算total/36，不沿用旧coverage_ratio命名和四位舍入。
无跨页正则匹配，合成project/另一页boundary不产生project boundary高关键词。
原生文本开发pilot未重做OCR，版本身份仍是开发UUID。关键词输出未写业务库，
处理run与正式身份将在Task 4 CLI/持久化边界接入。

规则放包内而非仓库根目录configs，使用stdlib importlib.resources读取。
uv build --wheel成功，wheel在/tmp导入及12维JSON读取检查通过，没有新依赖。

## Task 4：CLI与正式导入身份

开发数据库data/parsed/slice4-cli-pilot.sqlite存11份Raw版本和Parsed页面，Raw
复用内容寻址目录，不修改原PDF。extract baseline/score keywords读取这些身份，
不是之前开发UUID；每个产物把result和对应成功PipelineRun原子保存于同一个JSON。
所有候选仍unvalidated。事实与评分尚未写入Canonical数据库表。

11 PDF、527页的CLI抽取与评分均成功，重复调用文件字节与run ID复用；提取
证据切片检查通过。匹配字段数1–10/55；不同值的candidate_conflict_fields数1–6，
只是候选冲突提示，不代表已裁决。关键词分数与旧版逐维计数仍一致。
旧版五个数字首值比较与完整company等额外输出保存在忽略目录的legacy-comparison.json。
5处历史非法逗号capture差异仍保留；结果一致不等于正确率。

8份通过旧索引匹配document URL，另3份（GS1003、GS1012、VCS10）未找到对应
历史URL，使用example.invalid/local-development的明确开发占位，不宣称真实来源。
本地tesseract不可用，原生文字比较显式min-non-whitespace=0，不替代默认OCR
分流验证。Gold Standard仍仅2项目，MVP要求至少3，缺口未解决。

输出data/extracted/cli-pilot-2026-09-17含22份不可变result/run bundle、summary.json
与legacy-comparison.json。输入、输出路径不进入Git。损坏结果测试拒绝覆盖；
未知Parsed与项目身份不符测试验证结构化失败。fsync后hardlink发布沿用Raw存储模式。
失败运行只返回CLI错误，失败run持久化仍是后续需求，不能声称所有运行都有日志。

实际终端复用ACR125得到matched_fields=6、missing_fields=49、候选冲突字段2，
keyword分数25/36；这些是运行和覆盖观察，不是准确率或业务评分结论。
60 tests passed，Ruff通过，7 Schema逐字节稳定再生成。现有迁移测试随全套运行通过。
