# CATchain 生产存储边界

当前代码把存储分成两层：PostgreSQL 保存可查询的身份、哈希、版本、状态和处理关系；Raw、Parsed 与抽取产物保存到对象存储。数据库中不保存 30G 原文件的二进制内容。

## 环境约束

开发和离线验证可以使用 `sqlite+pysqlite` 与 `file://` 对象目录。生产环境必须设置：

```bash
export CATCHAIN_ENVIRONMENT=production
export CATCHAIN_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST:5432/catchain'
export CATCHAIN_OBJECT_STORE_URI='s3://BUCKET/catchain'
```

`RuntimeConfig.require_production_safe()` 会在启动阶段拒绝 SQLite 或本地对象目录。密码只放在部署环境的 Secret 中，不写入仓库或聊天。

## 迁移与对象键

在 PostgreSQL 上使用 Alembic 执行迁移。`0006_production_storage` 新增 `stored_objects`，用于记录对象键、SHA-256、字节数、内容类型和写入时间。文件内容写入对象存储后，只有校验通过的不可变对象才应写入这张表。

文档对象键由 `document_object_key()` 生成：

```text
registry/project/document_type/document_version/sha256
```

因此同一内容的路径变化不会伪造出新的内容版本，版本和证据仍可从数据库回溯到对象。

## 当前边界

`LocalObjectStore` 是开发和测试实现，生产 S3-compatible adapter 仍需在部署环境完成凭证、生命周期、加密、备份恢复和权限 smoke test 后才能把 `production_storage` 证据标记为 `true`。当前代码不会把本地测试当作生产就绪。

