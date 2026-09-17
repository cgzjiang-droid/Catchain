# CATchain 最终交付包与新架构对照

## 事实来源

主业务资产来源：`/Users/jiangchunlin/Desktop/最终交付_ACM0002_20260513 5`。
此前历史包审计仍有效，但只描述其自身版本，不能当成最终交付包的全量功能。

已读最终交付README、脚本说明、核心提取函数和ZIP批处理入口。
`01_样例提取与评分主脚本.py` SHA-256：
`f65f4e26fb069992717108bf9df6d5211c7c4ecb55f030467460113b11d2c98b`。

已运行核心函数的合成输入：真实标题 `Example Wind Project` 与7年计入期都能
提取；输出28个顶层键，包含嵌套company_info。该版本不能描述为“23键且标题
恒为文件夹ID”。同名technology_type仍为空，关键词评分仍是0–3。
字段映射仍为47个唯一字段，不等于实际已覆盖47字段。

逐行读取项目JSONL并成功解码：ACR 3、GOLD 541、VCS 741，共1285条记录。
这证明历史结果存在且JSON可读，不证明字段正确、证据完整或项目唯一性。
未重写历史结果，未复制大规模源数据。

## 调用链和迁移边界

批处理脚本读取ZIP、按registry/project分组、筛选方法学、提取项目文字，
调用基础提取和12维评估，再写JSONL和运行索引。整理脚本按公司归并结果，
Excel是展示层。优先复用数据、URL/定位经验、字段和规则，不搬旧交易架构。

批处理脚本仍 `from main import ...`，交付目录把对应文件改成中文名；README
命令也指向旧目录。目录可独立执行与否尚未验证，不会声称旧交付可直接运行。

## 参考仓库如何落到CATchain

参考：https://github.com/Doerp/carbon-methodology-archive，2026-09-17核对README。
README展示methodology文档目录、metadata.json、版本URL、hash与同步时间。
定时Actions、抓取器与AI能力须看代码验证，不能从README直接声称已成熟。

| 参考思想 | CATchain落地与状态 |
| --- | --- |
| 文档与独立metadata | SourceDocument和DocumentVersion已实现，SQLite保存metadata，不强制机械复制每文档JSON |
| SHA-256和版本追踪 | Raw内容寻址、不可变文件、去重已实现 |
| 源文件与派生数据分开 | Raw、Parsed已实现；本轮开始Extracted候选 |
| 来源URL、Registry上下文 | 来源模型已实现；联网下载与registry adapter尚未实现 |
| 定时增量同步 | 先可靠导入，再做幂等下载/重试；现在不创建定时任务 |
| structured taxonomy | 只作参考；CATchain的LLM合同、证据验证与评估自行实现 |

## 当前决定与差距

保持已批准的Python模块化单体、Pydantic、SQLite、普通Workflow和九个Slice。
基础Regex迁移只覆盖已审计的标量规则，不能宣称已迁移完整最终交付。

在Slice 4增加最终交付资产迁移检查点：项目标题、company角色与候选列表、
location、计入期及日期字段；逐项确定合同字段及证据表示后实施，保留版本化
baseline，缺失或歧义不造值。原47字段是评分输入基础，不是完整业务字段清单。

新增Ingestion检查点：审计已有抓取代码的实际URL、分页、文档定位和下载行为；
再设计registry-specific adapter与可重试增量下载，不用历史README当可用性证明。
LLM候选与Evidence必须关联处理run；当前ProjectExtraction尚未包含run_id，
需要在进入持久化/LLM阶段前补齐，不声称已经端到端可追溯。

Structured Database目前只有文档/Parsed表；事实、证据、评分和运行成本存储
尚未全部实现。Schema验证也不是业务正确性或证据grounding验证。

学习继续面向Agent产品经理：围绕输入、输出、证据、失败状态和验收指标解释；
代码由Codex实现。面试可问：重复下载如何避免重复版本？同字段两份PDF冲突
如何保存？关键词baseline为什么不能直接决定证据评分？
