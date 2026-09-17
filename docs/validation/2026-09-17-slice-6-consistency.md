# Slice 6 Task 2：一致性检查与使用

解决问题：单字段格式正确，仍可能出现开始日期晚于结束日期、单位不同、不同来源给出不同装机容量。
旧关键词评分不能识别这些关系。参考存档项目的文档版本与哈希思想，本实现独立保存候选差异报告，未复制其代码。

执行示例（在项目根目录；文件路径替换为自己的验证报告）：

```sh
venv/bin/catchain validate project validation-a.json validation-b.json --database data/parsed/project.sqlite --output-dir data/extracted/consistency
```

输入必须是validate extraction产生的成功报告，并属于同一Registry项目。
输出含原验证报告、文件SHA-256、来源文档ID、声明版本、获取时间及问题关联的候选索引。
重复相同输入复用报告，不调用模型，不写入正式事实。

日期检查不跨核证周期拼接起止日期；项目名、国家、容量、方法学及公司角色等才参与项目层比较。
拒绝的候选不会参与比较，但仍保留在报告中。不同值或单位只提示裁决，不自动换算或挑选新版。
没有可比较的项目层字段时，cross_document_comparison为not_possible。
methodology_scope_unconfirmed表示ACM0002适用范围缺少明确候选支持，不表示原项目无效。

真实ACR125单文档试跑：1项方法学范围待确认，0模型调用，0正式事实写入。
多文档和版本差异仅经离线测试样例验证。权威来源矩阵、完整ACM0002公式以及正式事实数据库仍需后续任务。

学习：这是确定性Workflow验证层。引用存在、格式正确与业务正确是三个不同验收条件。
面试可以解释：系统保存差异和每个候选的来源，人工按字段与文档权威性裁决；获取时间不能替代权威性。
