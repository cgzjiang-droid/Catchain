# Slice 5：首次真实DeepSeek抽取

## 范围与结果

使用已有SQLite pilot中ACR125的Parsed版本，仅第1页，请求project_name、country、
project_owner、verifier_name四字段。模型deepseek-flash，关闭thinking，输出上限1024
Token，仅一次请求、0 retry，不进行批量调用。

实际run：411589fa-148c-4599-a5cd-fc51f17371b8。
输入1212 Token，输出223 Token，耗时约1.60秒。

| 字段 | LLM结果 | 当前状态 |
| --- | --- | --- |
| project_name | THE SEESA PV PROJECT IN EL SALVADOR | 原文可定位、unvalidated |
| country | El Salvador | 原文可定位、unvalidated |
| project_owner | null / not_found | 仅选中页未找到 |
| verifier_name | null / not_found | 仅选中页未找到 |

两条候选引用逐字匹配第1页并具有字符位置。文档身份、项目/Registry和run身份
来自本地数据库和程序，不由模型指定。不是正式事实入库，也不是人工审核完成。

同一Parsed的Regex全篇在这四个字段没有候选，详细比较在忽略的runtime目录。
LLM仅第1页、Regex全篇的输入范围不同；本次是执行通路检查，不是公平准确率评估。
没有冻结人工gold，不报告准确率或业务评分。

## 可追溯记录

私有运行目录：data/extracted/slice5-real-pilot/<run-id>/。
started.json记录处理run、文档/页码身份和prompt/schema/pages哈希；response.json保留
原始模型JSON、模型响应ID、tokens和延迟；result.json包含共享ProjectExtraction合同。
失败调用保存failed.json和可获取的response.json，没有成功result。
密钥、真实PDF及runtime记录均不提交GitHub。

## 自动与手工验证

- 全套pytest 75项通过，Ruff通过；没有新增生产依赖。
- 离线fixture模拟真实API envelope，覆盖JSON模式、Token预算、鉴权失败无retry、
  空content、截断、非法JSON、假引用、配置读取及敏感信息不进入记录。
- CLI集成测试验证import→parse→fake extraction和可信数据库来源身份。
- Wheel构建成功；版本化prompt包含于wheel。
- 真实DeepSeek调用成功，仅一次请求。

## 未完成与已知边界

- Task 3已补充调用前缓存：相同成功输入复用结果，不调用模型；同键进行中阻止第二次
  调用；失败不缓存。首次真实调用来自旧格式，不能拿它作为新缓存格式的命中证明。
- 每次新调用最多一次、0 retry、8页/24000字符、1024默认输出Token（最大4096）；
  字符/字节预算不是精确输入Token或货币预算。
- 价格只有通过CLI明确提供输入/输出每百万Token单价时才计算；否则estimated_cost为null，
  不把未知费用写成0。可设置调用前最坏情况金额上限。
- 异常退出会留下同键锁以避免重复收费，需要人工调查后才能清理；自动恢复策略尚未实现。
- Task 4尚需固定同输入样本的Regex/LLM对比，单次成功不证明生产稳定性。
- 源站可达性、OCR、语义支持、单位、日期和冲突仍需后续验证。
