# 第5课：先建立LLM抽取边界

本次解决的是：怎么让模型的回答进入一个可检查流程。旧CATchain依赖Regex；
参考归档项目提供来源/版本工程思路，没有我们所需的完整AI抽取流水线。
新方案沿用ProjectExtraction，使Regex和LLM候选可以比较。

关键代码：`src/catchain/extraction/llm/contract.py`。
`select_pages`输入Parsed和明确页码，输出完整页面；超过8页或24000字符则失败。
字符预算只是初步输入大小边界，不是精确Token预算，后续调用还需控制输出和费用。
模型Context Window限制一次能看到的信息；选页漏掉的事实不能当全文不存在。

`ModelResponse`是Structured Output的合同：字段名、原值、标准化值、单位、
页码与原文，或明确弃答。Pydantic检查类型和结构；格式合法不等于事实正确。
DeepSeek JSON Output支持合法JSON，不等同于服务端严格遵守我们的完整Schema：
https://api-docs.deepseek.com/zh-cn/guides/json_mode/

`ground_response`要求引用逐字存在于选中页，并计算字符位置。身份由系统补上，
模型不能自己声明来自哪个版本或run。重复原文无法唯一定位时要求更长引用。
这个Evidence Grounding检查证明引用存在，不证明引用支持值；例如引用写12MW、
回答99MW仍需Slice 6语义/领域检查。所以状态保留unvalidated，confidence不伪造。

产品经理验收：假引用必须失败；失败不能变成0分或“未找到”；仅选页的not_found
不能被解释为全文没有。面试可问：“JSON正确为何还不能入事实库？”回答应区分
结构、引用存在、语义支持和业务规则四层验证。

Hello-Agents中的LLM、Prompt和Context Window在这里对应真实输入边界；当前仍是
普通Workflow。API把文档文字交给模型，不要求模型自主浏览国外Registry。
