# CATchain 文档版本重审

新 PDF 版本的正确处理顺序固定为 `Parse → Extract → Validate → Review`。旧版本的 Canonical fact 和 evidence 永远保留；新版本只有在四个阶段全部完成、且人工批准后，才可以创建新的 fact 并更新 canonical head。

`canonical_fact_sources` 保存每个正式 fact 对应的 `document_version_id`、`parsed_document_id` 和 `validation_run_id`。因此“当前值”可以回溯到具体版本和处理运行，修改前值不会因 head 更新而消失。

如果阶段未完成、证据冲突或两名审核员无法裁决，状态保持待审核或 unresolved，不写入新的正式事实。

