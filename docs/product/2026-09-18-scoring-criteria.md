# 12维判定项草案 v2

新增scoring/acm0002-quality-rubric-draft-v2.json，保留v1历史版本。
12维共36个稳定criterion_id（D01.C1至D12.C3），逐项关联原证据要求。
这些ID是CATchain内部审核项，不是官方方法学条款编号。

每项记录outcome、reason、fact_ids和原文evidence。
supported表示审核认定证据支持；not_supported表示有明确不支持的依据；
insufficient表示证据不足；conflicting表示待裁决；not_applicable必须有适用理由与证据。
未提及或未找到证据不能当作not_applicable，也不能当作不合格。

程序检查事实ID、文档版本和原页定位；人工判断语义、适用性和充分性。
三个项目都supported不自动等于3分，各项的关键程度和分值映射尚未批准。
36项仅为初始证据审核清单，尚未展开完整官方条件，不能替代逐版本方法学/Registry审核。
本步不改变现有score命令，不启用自动评分，不设置权重或容差。

例如D05.C2的校准证明：不能因为出现calibration就supported。
需要审核证书对应哪台仪表、有效期是否覆盖监测周期，以及该仪表是否用于本项目计量。
当前输入清单没有完整仪表/证书结构，结果应保持insufficient，而非编造合格结论。

下一步实现判定结果Schema及保存：强制引用有效criterion_id和事实快照，保留审核理由与证据。
