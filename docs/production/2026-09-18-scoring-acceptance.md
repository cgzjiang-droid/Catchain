# CATchain 评分与 Gold 准入

正式评分必须同时加载 `status=approved` 的 12 维 ScoringPolicy 和 `status=frozen` 的人工 GoldDataset。Policy 必须包含 D01–D12、权威来源、批准人、批准日期和权重；Gold 每个样本必须有两名审核员，冲突由组长裁决后才能冻结。

验收报告按 development、validation、test split 隔离，记录 exact match、correct abstention、evidence coverage、conflict rate 和 policy hash。没有这两项冻结输入时，系统返回 blocked，不输出总分或准确率。

