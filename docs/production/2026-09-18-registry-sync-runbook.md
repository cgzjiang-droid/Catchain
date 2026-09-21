# CATchain Registry 同步边界

Registry adapter 只负责把来源差异转换成统一的 `RemoteProject`、`RemoteDocument` 和下载回执。共同流程负责哈希、Raw 存储、版本登记与后续解析。

## 已迁移并离线验证的规则

- ACR：解析项目文档页的相对链接；URL 或显示名称包含 `.pdf` 才进入候选，原始链接仍完整保留。
- Verra/VCS：读取 `documentGroups[].documents[]` 的 `uri`、`documentName`、`version`。
- Gold Standard：读取 `requests[].documents[]` 的文档 ID，再生成官方 download URL。

这些规则来自旧 CATchain 的实际抓取器审计，并通过固定响应 fixture 验证。它们不等于线上端点当前可用。

## 同步语义

`SyncService` 使用 cursor checkpoint 重跑发现流程。项目文档请求异常会进入 `failures`，不会被伪装成“没有文档”；旧版本也不会因为新同步而删除。下一步接入真实 HTTP transport 时必须增加 timeout、429/5xx 分类、临时文件下载、PDF 内容校验和 smoke test。

当前实现还会把每次运行写入 `registry_sync_runs`，把可重放 cursor 写入
`registry_sync_checkpoints`。只要本页有失败，checkpoint 保留在本次运行前，
这样下一次运行会重试整页；成功页才推进 cursor。失败记录包含作用域、稳定错误码和
错误消息，`registry_not_configured`、`timeout` 和 HTTP smoke 错误不会被压成空结果。

没有通过真实端点和授权验证前，不启用定时同步，也不把空响应写成成功证据。
