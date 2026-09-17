# Registry抓取与公司资产审计

日期：2026-09-17。状态：旧代码和本地历史输出已核对，线上接口未验证。
原脚本未执行main，没有下载、修改历史数据或启动浏览器。

## 来源与调用链

旧抓取器：
`/Users/jiangchunlin/Desktop/桌面 - 蒋春林的MacBook Pro/用所选项目新建的文件夹/5900/registry_pdf_scraper.py`。
SHA-256：`cb0d5f0f97e956483c58b0aa6de971d1575054fad1eaaeae8c2d6f6e4d30de39`。

它是1011行的实际抓取脚本，不是仅处理本地PDF的registry pipeline wrapper。
`main`读取CSV→按registry分支发现文档→构造文件名→下载→写index.csv。
另有ACR报告分页路径：Playwright表格定位→TabDocuments链接→requests读取文档页。
CSV路径支持start_offset/max_projects分批；公司整理脚本则只处理已生成JSONL。

## 可保留规则与证据级别

| Registry | 旧代码规则 | 证据 | 待确认 |
| --- | --- | --- | --- |
| ACR | 从ID尾部取数字，构造acr2.apx.com的TabDocuments.asp，id1为项目数字；HTMLParser跟踪Project_ViewFile.asp链接并urljoin | L137–182、L591–607；两份历史索引 | 页面结构、报告参数和线上可用性 |
| Verra/VCS | registry.verra.org/uiapi/resource/resourceSummary/{数字ID}；documentGroups[].documents[]读取uri和documentName | L614–630；30条索引及本地文件 | API字段、分页/截断、当前权限与可用性 |
| Gold Standard | assurance-platform.goldstandard.org/api/public/project-documents/{ID}；requests[].documents[]读取id，再构造api/public/documents/{id}/download | L633–669；假响应离线检查 | 输入ID格式、权限、API字段、浏览器是否必需、完整性 |

ACR链接只有文字或URL含.pdf才收录。因此“Design document”这种无.pdf文字的
ASP链接会被排除。这可能漏文档，不能机械复制该过滤条件。
Verra、Gold函数未实现返回数据的分页；不能推断接口无需分页。
Gold分支有浏览器预热，不能把它当成完整可用性验证或新架构的必需步骤。

文件命名保留FileID或Gold document UUID有助于定位来源，但身份仍使用Hash，
不能把文件名当内容版本。CSV中的registry_docs虽读取，但direct_csv分支仍按
registry规则发现文档；不能声称所有历史URL都已实际使用。

## 历史索引核对

| 索引目录 | 记录数 | doc_url域名 | 找到本地文件 |
| --- | --- | --- | --- |
| downloads | 22 | acr2.apx.com | 22 |
| downloads_acr_renewable | 22 | acr2.apx.com | 15 |
| downloads_vcs_renewable_test | 30 | registry.verra.org | 30 |

路径按原目录名映射回当前旧数据根目录。两份ACR索引可能重叠，不能相加称44份
独立文档；is_file只说明文件存在，未逐一验证PDF内容完整。缺7个文件的原因
尚未确认。索引record在下载之前加入，即使失败仍可能写入，不能当成功清单。
本次定位的索引没有Gold独立index.csv证据；此前GS PDF文件名不等于完整URL记录。

## 失败状态与新方案

旧download_file直接写目标文件，失败可能留下半文件；存在同名文件就跳过，
没有内容Hash、PDF确认或版本比较。Gold下载只有429重试，最多8次，等待60–300秒；
发现接口非200直接返回[]。ACR报告翻页异常直接break，也可能把部分发现当完整。

迁移时保持普通Workflow，按真实registry返回不同发现结果，但下载/Hash/Raw导入
复用共同流程：

1. 保留来源project URL、discovery URL、document URL和原始ID；csv:ACR不能充当
   SourceDocument.source_url中的真实HTTP来源。
2. 区分discovery_failed、discovery_partial、no_documents、download_failed和downloaded；
   HTTP失败不可变成no_documents。
3. 下载到临时文件；校验响应和PDF可读性后，使用已有Raw/版本服务导入。
4. 有界timeout/retry，失败记录项目和文档状态；不靠文件存在判断下载成功。
5. Hash决定内容是否变化，原URL保留来源；同项目多个来源文件各自跟踪版本。
6. 网络adapter实施前核对真实端点与返回字段，再用离线响应测试解析规则；
   未稳定前不安排定时同步，不添加Agent/RAG/新框架。

上述是Ingestion实现backlog，不代表新平台已经实现自动下载。
参考carbon-methodology-archive的metadata/hash/version思想，CATchain自行设计项目
文档来源和状态，不复制它的目录和代码。

## 公司资产：保留什么，不能直接迁移什么

指定最终交付核心脚本有find_company_names、find_known_orgs、split_org_list及
extract_company_info；角色标签、法律后缀和去重经验可保留为baseline资产。
验证/核查候选混入developed by、prepared by及已知机构列表，不能自动认定角色。

`03_按公司整理结果.py`实际调用链：JSONL→clean_company_candidates→法律名称
提取→choose_company首候选→按公司分组。clean_company_name反复剥离Project等
前缀，clean_company_candidates按&、分号和斜杠切分。没有跨registry实体ID或
合并证据，choose_company首个值只是heuristic，不是经过验证的归属关系。

已运行反例：owner_or_developer_clean=["Alpha & Beta Ltd"]得到["Beta Ltd"]。
拆分会损失合法名称的部分。新候选合同保留整段原值与角色/证据，不照搬此拆法。
通用公司发现、法律实体解析、primary-company选择、联系字段和完整location仍为
未迁移资产。后续要有明确输入/输出/证据检查点；不称其已完成，也不删除旧逻辑。

## 离线验证与知识点

通过AST只加载所需旧函数/class，注入假requests/Playwright响应，不执行模块main：

- ACR相对ASP链接正确urljoin；无.pdf的文字被旧规则排除。
- VCS7构造resourceSummary/7，并读取documentGroups中的uri/name。
- GS成功响应构造document UUID下载地址；403响应确实返回[]。
- FileID=42生成PDD_fileid_42.pdf。
- 公司反例确认Alpha & Beta Ltd被破坏性拆分。

当前新代码的57测试与Ruff通过；以上是另外执行的旧逻辑离线检查，不属于57测试。
没有宣称历史端点线上可用，未改变旧业务结果。

产品经理学习：adapter将registry差异限制在发现逻辑；共享下载层统一处理版本、
失败和证据来源。面试可问：“文件已经存在能否跳过下载？”、“403与无文档为何
分开？”、“公司名称相同能否直接归并？”。

结论：Task 2B的剩余资产审计检查点完成。下一步Task 3迁移12维关键词baseline；
更广泛实体解析与联网adapter保持明确backlog，不能混称已实现。
