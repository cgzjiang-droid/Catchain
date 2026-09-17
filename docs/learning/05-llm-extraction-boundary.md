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

## 真实调用已接通：输入、推理与输出

关键代码还包括providers.py、workflow.py和prompt-v1.txt。Workflow先选页，打包
requested_fields、响应Schema和带页码的文字；provider把它发到DeepSeek。模型
Inference是根据这些输入生成回答的过程，当前不是自主浏览或Agent决策。
Prompt在版本控制中，规则明确禁止执行文档内的指令、猜公司角色或给总分。

首次真实ACR125调用选第1页：输入1212、输出223 Token。输入不仅包含PDF文字，
还包含Prompt、字段请求和Schema。模型从无标准字段标签的标题抽出了项目名与
国家，两项角色明确弃答；Regex在这四项上没有候选。一个样本不能证明准确率。

Structured Output执行路径：模型JSON→Pydantic→逐字引用定位→共享候选合同→
私有结果文件。原始响应/失败仍存档，方便判断是模型、结构还是引用出了问题。
保留confidence=null；不把模型自信当可靠概率。

面试可能问：“为什么没有加RAG或Agent？”此样本单页直接输入可以完成抽取，
没有检索需求或模型自主选工具的需求。先解决重复调用成本和评估，再决定是否需要
检索；不根据文件长度猜测模型过载。

## 调用前缓存与费用边界

`workflow.py`现在在调用前计算缓存键。它把文档版本、Parsed内容、选中的原文页、
字段、Prompt哈希、Schema哈希、模型、输出上限和费用配置一起绑定。完全相同的成功
输入直接返回第一次的结果，不再次请求模型；失败不会缓存，因为网络或模型状态可能已变。

这里的产品规则是“同样的输入不重复收费”，而不是“所有旧答案都可以复用”。模型、
Prompt或Schema变了，缓存失效是正确行为，因为抽取方法已经变了。同一键仍在执行时，
系统会停止第二次调用，避免并发重复收费；异常中断留下的锁需要人工调查，不能自动删除。

费用有两个概念。实际估算费用用供应商返回的输入/输出Token乘以调用者明确提供的单价；
没有明确单价就保留null。调用前的“最坏情况”用输入字节上界和最大输出Token做保守估算，
超过`--max-estimated-cost-usd`时不联网。这是预算护栏，不是账单真值。

面试可问：“为什么单价不硬编码？”因为价格会变，且输入/输出价格可能不同。可追溯
系统应记录本次使用的价格和计算方法，并把未确认价格显示为未知。

## 对比实验：公平输入和正确答案是两件事

`extraction/comparison.py`输入已有LLM结果、started记录和数据库Parsed，验证身份与
证据后，让Regex读取相同页。`regex.py`增加可选page_numbers，默认仍读全文；
选择第2页时保持page_number=2，不构造一个假“第1页”。CLI compare extraction不请求模型。

真实ACR125同页四字段对比中，模型有两项候选，双方有两项缺失。这个实验说明方法
输出不同；要知道谁答对，需要独立人工标准答案。候选一致、双方缺失和证据存在都
不能单独证明正确。这对应Evaluation的输入控制和Gold标签边界。

报告把同字段多个容量、角色和原文保存下来供审核，而不是先取第一个值。面试可问：
“为什么不能把模型与Regex一致率当准确率？”两种方法可以同时犯错，必须有独立Gold。
