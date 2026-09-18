# CATchain Processing Worker

`processing_jobs` 把每个阶段绑定到 `kind + input_identity`。相同文档版本和相同阶段重复入队时复用原 Job，避免 30G 重跑产生重复解析或重复 LLM 调用。

Job 经过 `pending → running → succeeded`，临时错误进入 `retry`，超过上限或命中 `invalid_pdf`、`schema_invalid`、`evidence_missing`、`permission_denied` 时进入 `dead_letter`。每次失败保存错误码、消息和下一次重试时间。

当前 `JobStore` 是数据库持久化边界，开发环境使用 SQLite，生产环境由 PostgreSQL 迁移承载。它还没有把具体 Parse/Extract handler 绑定到进程，也没有替代真正的队列调度器；接入 Worker 时必须保持领取条件、幂等键和失败状态不变，并为每个文档设置超时与限流。

