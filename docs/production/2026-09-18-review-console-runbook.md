# CATchain Review API

`create_app()` 提供三个最小运行入口：`GET /health`、`GET /review/queue` 和 `POST /review/decisions`。API 只调用现有 review queue projection 与 `decide()`，不在 HTTP 层复制 canonical 写入规则。

每个请求必须带 `X-Actor` 与 `X-Actor-Role`。读取队列支持 reviewer、lead、admin；批准候选需要 lead 或 admin，且 reviewer 字段必须和 actor 一致。过期的 `expected_current_fact_id`、证据缺失和日期冲突由领域层返回 409，不应被前端吞掉。

当前 header actor 是本地部署的身份边界，尚未接入企业 SSO/JWT；正式上线前必须由反向代理注入经过验证的身份，并保留 request ID、actor、时间和决策 payload 审计记录。

