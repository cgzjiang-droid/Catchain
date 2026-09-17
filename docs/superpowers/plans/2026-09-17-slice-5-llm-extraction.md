# Slice 5：LLM 结构化抽取实施计划

基于已批准重构规格，保留Slice 4基线，按小步实现并测试。用户选择DeepSeek作为
首个真实provider候选；不引入RAG、Agent或新的编排框架。

- [x] Task 1：provider-neutral响应合同、显式页面选择、字符/页数预算和引用定位检查。
  - 模型只返回字段和值/页码/原文；版本、Parsed和run身份由系统填充。
  - 精确覆盖请求字段，允许同字段多个候选。JSON/Pydantic失败即拒绝。
  - 引用必须在选中页唯一出现；不猜位置，不静默截断页面。
  - 候选保留unvalidated和语义待验证；不进入正式事实库。
- [x] Task 2：版本化prompt、离线fake adapter及DeepSeek JSON Output adapter。
  - API空content、截断、网络/鉴权错误明确区分；密钥只读环境变量。
  - Protocol返回原始JSON，解析/验证由独立workflow负责。
- [x] Task 3：调用前缓存、run/call记录、tokens/延迟/成本和有界retry。
  - 缓存身份包括文档、选中页、prompt/schema版本和model。
  - 成本须基于明确价格配置；未知费用不得写成0。失败记录也要持久化。
- [x] Task 4：CLI接入、数据库来源身份检查、真实小样本调用及与Regex的逐字段对比。
  - 没有人工gold不能报告准确率；保存失败/缺失/冲突，保留旧Regex输出。
  - 真实调用成功以前，不能把fake fixture或网络连通标为真实LLM完成。

## Task 1验收

运行：`venv/bin/python -m pytest tests/unit/extraction/test_llm_contract.py -q`。
6项测试通过，覆盖可信身份/字符位置、假引用、未选页、重复位置、额外身份字段、
请求字段覆盖、弃答和预算。不需要联网或API密钥。

## 已验证 / 未验证

2026-09-17：本机访问api.deepseek.com收到HTTP 401，参考GitHub页面HTTP 200。
这仅证明两个站点网络可达，不代表Registry全部可达、API账号有余额或模型调用成功。
本地.env已保存DEEPSEEK_API_KEY，Git忽略、权限600；GET /models鉴权成功。
返回deepseek-flash、deepseek-v4-pro。已完成一次生成抽取及llm-once CLI；Token/延迟与成功/失败run记录已落盘。
调用前缓存、显式价格与费用上限和固定同页样本对比已实现。

## Task 2验收

75测试、Ruff、wheel构建通过。真实ACR125第1页四字段请求成功，2候选/2弃答。
见`docs/validation/2026-09-17-slice-5-first-real-call.md`。Task 4的CLI部分提前完成，
但完整对比验收未完成。llm-once每次调用可能计费，零自动retry，不是批量入口。

## Task 3验收

缓存键绑定文档版本/Parsed内容、选页、字段、Prompt、Schema、模型、输出上限和
费用配置。相同已成功输入直接复用完成的JSON，不调用模型；同键进行中会停止，避免
并发重复计费。失败不缓存，保留失败run供人工调查。每次新调用最多一次、零自动retry。

价格不是内置常量：只有调用者明确给出输入/输出每百万Token的USD价格时，才记录
实际估算费用。设置`--max-estimated-cost-usd`必须同时给出两项价格；系统用输入字节
上界和最大输出Token计算保守上限，并在请求前阻止超额调用。未知价格保持null。

## Task 4验收

`compare extraction LLM_ARTIFACT`从原始started记录读取选页/字段，验证成功run、
Parsed内容哈希、数据库项目身份和引用后，再让Regex读取同样页面。保留原PDF页码；
生成候选差异、缺失原因、单位、证据和冲突，不把一致率当准确率。

复用ACR125已保存的真实DeepSeek响应，固定第1页/四字段：2个llm_only、2个both_missing。
本次没有新增API调用。重复比较复用不可变报告和原run；详见同页比较验证报告。
Slice 5开发范围完成，不代表模型质量、正式事实库或MVP验收完成。
