# CATchain 完整生产系统实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Each task ends with an independently testable acceptance gate.

**Goal:** 将现有 CATchain 基础工程继续实现为可部署、可追溯、可审核、可处理大规模碳信用文档的生产系统，而不是停留在本地 MVP。

**Architecture:** Registry Adapter 负责发现和下载；不可变对象存储保存 Raw/Parsed/Artifact；PostgreSQL 保存元数据、版本、运行、候选、Evidence、审核和指标；数据库任务表驱动普通 Workflow worker。LLM 只负责结构化候选，所有候选必须经过 Schema、Evidence、业务规则和人工审核边界后才能进入 Canonical 或评分。

**Tech Stack:** Python 3.12、Pydantic、SQLAlchemy/Alembic、PostgreSQL、S3-compatible object storage、PyMuPDF、Tesseract OCR、DeepSeek provider、FastAPI JSON API、最小审核 Web UI、pytest、Ruff、Docker Compose。

**Spec:** `docs/superpowers/specs/2026-09-09-catchain-redesign.md`、旧 CATchain 审计记录和 `docs/validation/2026-09-18-slice-8-closeout.md`。

## Global Constraints

- 旧 CATchain 是业务需求、历史数据、ACM0002 规则和已验证 URL 的事实来源；参考项目只用于架构实践。
- 不 Fork、改名或复制 `carbon-methodology-archive` 的代码。
- 任何 Raw、Parsed、Extraction、Evidence、Review、Scoring 结果都必须能回溯到文档版本、页码、原文片段和 processing run。
- 不把关键词出现次数当成正式质量评分；旧 Regex/Keyword 只能作为 Baseline。
- 没有人工批准的评分策略时，`total_score=null`；没有冻结 Gold 时，`accuracy=null`。
- 30G 原始数据不进入 GitHub；`data/raw`、`data/parsed`、`data/extracted`、`data/review` 永远由 Git 忽略。
- 所有写入都必须幂等；相同输入复用，内容变化创建新版本，不能覆盖旧证据。
- 先完成可观测的普通 Workflow；只有真实需求证明需要状态循环或工具自主选择时才考虑 Agent/LangGraph。
- 每个任务都必须有代码、测试、运行命令和验收证据；文档不算代码完成。

## 当前真实状态

已完成：Slice 1–8 的本地工程基础、解析/OCR、Baseline、DeepSeek 抽取、验证、Canonical 历史、Gold 评估框架和 CLI/JSON 审核队列。

尚未完成：30G 数据正式导入、Registry 在线同步、生产存储/API/UI、任务调度、权限、监控、部署、官方评分策略确认和真实人工 Gold 验收。因此当前标签是“生产重构进行中”。

## 生产完成定义

只有同时满足以下条件才可以标记 Production Ready：

1. 30G 数据具有 manifest、SHA-256、来源、版本和可重放导入记录；抽样覆盖 ACR、Gold Standard、Verra。
2. Registry adapter 能发现、下载、去重、记录失败并定时增量同步。
3. Raw、Parsed、Candidate、Evidence、Review、Canonical、Scoring、ProcessingRun 在生产数据库和对象存储中分层保存。
4. 大文件处理有任务队列、重试、限流、断点、失败重跑和成本记录。
5. 重要字段能定位 PDF、页码、quote、字符区间、提取方法和处理 run。
6. 审核员能查看问题位置、原值、Evidence、当前正式值，并保存修改前后值、负责人、理由和裁决状态。
7. 正式评分策略和 Gold 由人工批准；真实测试集产生可复核指标。
8. API/UI 有认证、角色、审计日志、错误追踪、备份恢复和部署手册。
9. 生产验收脚本在干净环境通过，且没有私有数据进入 Git。

---

### Task 0：生产差距冻结与基线清单

**Files:**
- Create: `docs/production/2026-09-18-production-gap-register.md`
- Modify: `docs/PROJECT_PROGRESS.md`
- Test: `tests/production/test_production_checklist.py`

**Interfaces:**
- Consumes: 当前 `src/catchain`、旧 CATchain 路径、Slice 7–8 closeout。
- Produces: 可执行差距清单、生产状态命令和基线指标。

- [ ] **Step 1: 写失败验收测试**

```python
def test_production_checklist_rejects_missing_external_gates():
    report = production_checklist(real_gold=False, approved_policy=False, registry_sync=False)
    assert report.status == "blocked"
    assert {"real_gold", "approved_policy", "registry_sync"} <= set(report.blockers)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `venv/bin/pytest tests/production/test_production_checklist.py -q`

- [ ] **Step 3: 实现 `src/catchain/production/checklist.py`**

实现 `production_checklist(...) -> ProductionChecklist`，输出 code、status、evidence 和 blockers；不得把“代码存在”当作“生产可用”。

- [ ] **Step 4: 运行测试并保存基线**

Run: `venv/bin/pytest tests/production/test_production_checklist.py -q` 和 `venv/bin/catchain production check`。

- [ ] **Step 5: Commit**

```bash
git add docs/production tests/production src/catchain/production docs/PROJECT_PROGRESS.md
git commit -m "Add production readiness checklist"
```

### Task 1：30G 数据 Manifest 与安全抽样导入

**Files:**
- Create: `src/catchain/dataset/manifest.py`
- Create: `src/catchain/dataset/sampling.py`
- Create: `src/catchain/cli_dataset.py`
- Modify: `src/catchain/cli.py`
- Test: `tests/unit/dataset/test_manifest.py`
- Test: `tests/integration/dataset/test_dataset_cli.py`
- Docs: `docs/production/2026-09-18-dataset-runbook.md`

**Interfaces:**
- `build_manifest(root: Path, output: Path) -> DatasetManifest`
- `sample_manifest(manifest: DatasetManifest, strata: dict[str, int], seed: int) -> DatasetManifest`
- `ingest_manifest(manifest: DatasetManifest, raw_root: Path, database: Path) -> IngestReport`

- [ ] Manifest rows必须包含 `path`、`size_bytes`、`sha256`、`registry`、`document_type`、`source_url`、`declared_version`、`sample_split`。
- [ ] 30G数据只读扫描，不一次性加载内存；复制使用临时文件、fsync、原子 rename。
- [ ] 同一 hash 复用 Raw；路径变化不产生新内容版本。
- [ ] 抽样先做 development/validation/test 三组，项目不能跨 split。
- [ ] 测试包含损坏文件、重复 hash、断点重跑、未知 Registry 和超大文件。

**Acceptance:** 先用本机小样本证明闭环，再由用户从手机复制抽样文件；全量 30G 处理必须可暂停和重跑。

### Task 2：生产对象存储与 PostgreSQL 元数据层

**Files:**
- Create: `src/catchain/storage/object_store.py`
- Create: `src/catchain/storage/postgres.py`
- Create: `migrations/versions/0006_production_storage.py`
- Modify: `src/catchain/storage/database.py`
- Modify: `src/catchain/config.py`
- Test: `tests/integration/storage/test_postgres_storage.py`
- Test: `tests/integration/storage/test_object_store.py`
- Docs: `docs/production/2026-09-18-storage-runbook.md`

**Interfaces:**
- `ObjectStore.put_immutable(key: str, source: BinaryIO, sha256: str) -> StoredObject`
- `ObjectStore.open(key: str) -> BinaryIO`
- `ProductionDatabase.create_session() -> Session`

- [ ] SQLite 保留为开发/离线模式；生产配置必须拒绝 SQLite。
- [ ] Raw/Parsed/Artifact 文件进入对象存储；PostgreSQL 只保存身份、hash、版本、路径和状态。
- [ ] 对象 key 按 `registry/project/document_type/document_version/sha256` 组织。
- [ ] 重复 hash、断点写入、权限错误和对象缺失都有测试。

### Task 3：Registry Adapter 与增量同步

**Files:**
- Create: `src/catchain/registries/base.py`
- Create: `src/catchain/registries/acr.py`
- Create: `src/catchain/registries/gold_standard.py`
- Create: `src/catchain/registries/verra.py`
- Create: `src/catchain/sync/service.py`
- Modify: `src/catchain/cli.py`
- Test: `tests/contract/registries/test_adapter_contract.py`
- Test: `tests/integration/sync/test_incremental_sync.py`
- Docs: `docs/production/2026-09-18-registry-sync-runbook.md`

**Interfaces:**
- `RegistryAdapter.discover_projects(cursor: str | None) -> DiscoveryPage`
- `RegistryAdapter.list_documents(project_id: str) -> tuple[RemoteDocument, ...]`
- `RegistryAdapter.download(document: RemoteDocument, destination: BinaryIO) -> DownloadReceipt`
- `SyncService.run(adapter: RegistryAdapter, checkpoint: SyncCheckpoint) -> SyncReport`

- [ ] Adapter 必须记录 URL、抓取时间、HTTP 状态、内容 hash、版本和失败原因。
- [ ] 连接超时、429、5xx、HTML 错页和文件 hash 变化必须区分。
- [ ] 同步 checkpoint 可重跑；不删除旧版本。
- [ ] 使用真实 URL 做小规模 smoke test；没有网络凭证时使用录制 fixture，不伪造成功。

### Task 4：任务队列与大文件 Processing Worker

**Files:**
- Create: `src/catchain/jobs/models.py`
- Create: `src/catchain/jobs/worker.py`
- Create: `src/catchain/jobs/retry.py`
- Modify: `src/catchain/parsing/service.py`
- Modify: `src/catchain/extraction/llm_provider.py`
- Test: `tests/integration/jobs/test_worker_idempotency.py`
- Test: `tests/integration/jobs/test_retry_and_resume.py`
- Docs: `docs/production/2026-09-18-worker-runbook.md`

**Interfaces:**
- `JobStore.enqueue(kind: JobKind, input_identity: str) -> Job`
- `Worker.run_once() -> JobResult`
- `RetryPolicy.next_attempt(error: ProcessingError) -> RetryDecision`

- [ ] 每个 job 绑定 document_version、parsed_document、config hash 和 provider/model。
- [ ] 失败保存结构化 code、attempt、last_error、next_retry_at；不无限 retry。
- [ ] 30G 数据按文档和页分块处理，单文档失败不阻塞整批。
- [ ] LLM 请求有并发、token、费用和供应商限流。

### Task 5：生产 LLM Extraction 与 Evidence Grounding

**Files:**
- Modify: `src/catchain/extraction/llm_provider.py`
- Create: `src/catchain/extraction/production_run.py`
- Create: `src/catchain/extraction/retry_policy.py`
- Modify: `src/catchain/domain/extraction.py`
- Test: `tests/integration/extraction/test_production_llm_run.py`
- Test: `tests/unit/extraction/test_retry_policy.py`

**Interfaces:**
- `run_structured_extraction(document: ParsedDocument, fields: tuple[str, ...], provider: LLMProvider) -> ExtractionArtifact`
- `validate_grounding(artifact: ExtractionArtifact, parsed: ParsedDocument) -> GroundingReport`

- [ ] LLM 只能返回 Pydantic/JSON Schema 合同，不能直接写 Canonical 或总分。
- [ ] 每个重要字段保存 value、unit、confidence、Evidence、method、model、prompt hash 和 run。
- [ ] 非法 JSON、截断、无引用、引用不匹配和超预算必须失败并可重跑。
- [ ] 同输入缓存命中不重复计费；模型版本或 prompt 变化产生新 run。

### Task 6：Production Validation、Canonical 与版本重审

**Files:**
- Modify: `src/catchain/validation/extraction.py`
- Modify: `src/catchain/storage/review_repository.py`
- Create: `src/catchain/validation/production_gates.py`
- Test: `tests/integration/validation/test_production_gates.py`
- Test: `tests/integration/review/test_version_reprocess.py`

- [ ] 低置信度、Evidence 缺失、冲突、日期/单位错误进入人工队列。
- [ ] 新 PDF 版本必须重新 Parse → Extract → Validate → Review；旧 Canonical 不被覆盖。
- [ ] 批量决策失败时保留草稿和错误位置，不写入半个事务。
- [ ] 两名审核员冲突交给组长；无法确定写入 `unresolved`。

### Task 7：正式 ACM0002 Policy 与真实 Gold 验收

**Files:**
- Create: `src/catchain/scoring/approved_policy_loader.py`
- Create: `src/catchain/evaluation/acceptance.py`
- Modify: `src/catchain/domain/policy.py`
- Modify: `src/catchain/extraction/gold_evaluation.py`
- Test: `tests/integration/scoring/test_approved_policy.py`
- Test: `tests/integration/evaluation/test_real_gold_gate.py`
- Docs: `docs/production/2026-09-18-scoring-acceptance.md`

- [ ] 只有权威来源、审核人、日期、D01–D12权重和业务判定全部存在时才能加载 approved policy。
- [ ] Gold 必须由两名审核员和组长冻结；development/validation/test 项目隔离。
- [ ] 计算字段级 exact match、correct abstention、evidence coverage、conflict rate 和分层结果。
- [ ] 没有 approved policy 或 frozen Gold 时，生产检查失败而不是输出伪造分数。

### Task 8：审核 API 与最小生产审核台

**Files:**
- Create: `src/catchain/api/app.py`
- Create: `src/catchain/api/auth.py`
- Create: `src/catchain/api/review_routes.py`
- Create: `web/review-console/src/`
- Modify: `src/catchain/review_queue.py`
- Test: `tests/integration/api/test_review_api.py`
- Test: `tests/e2e/test_review_console.py`
- Docs: `docs/production/2026-09-18-review-console-runbook.md`

- [ ] API 提供 queue、candidate detail、evidence、draft、decide、history、metrics。
- [ ] 角色至少包含 reviewer、lead、admin；每次写操作记录 actor、时间和 request id。
- [ ] UI 首屏直接显示错误位置、原文 Evidence、修改前后值和提交原因。
- [ ] API 不允许前端绕过 Pydantic、Evidence 和 stale-current-fact 检查。

### Task 9：运行保障、权限、审计和部署

**Files:**
- Create: `docker-compose.production.yml`
- Create: `deploy/healthcheck.sh`
- Create: `deploy/backup.sh`
- Create: `src/catchain/observability/metrics.py`
- Create: `src/catchain/observability/logging.py`
- Create: `tests/e2e/test_production_deployment.py`
- Docs: `docs/production/2026-09-18-deployment-runbook.md`
- Docs: `docs/production/2026-09-18-operations-runbook.md`

- [ ] Postgres、object storage、API、worker和scheduler能在干净环境启动。
- [ ] 健康检查区分数据库、对象存储、队列、LLM provider 和 OCR 工具故障。
- [ ] 日志不包含 API key、原始 PDF 或敏感全文；每条日志带 run/job/request identity。
- [ ] 备份可恢复；部署前后执行 schema migration 和 smoke test。
- [ ] 告警覆盖连续失败、队列堆积、费用上限、磁盘和对象存储错误。

### Task 10：真实数据灰度与 Production Readiness Review

**Files:**
- Create: `docs/production/2026-09-18-gray-release-plan.md`
- Create: `tests/e2e/test_gray_release.py`
- Modify: `docs/PROJECT_PROGRESS.md`

- [ ] 使用 development split 做影子运行，不写正式结果。
- [ ] 通过人工 Gold 后从 5% → 10% → 30% 灰度；每级保留停止条件。
- [ ] 低于业务阈值、Evidence 缺失、连续同类错误或成本超限立即暂停并回退。
- [ ] 每次灰度保存输入 hash、代码版本、policy hash、模型、指标和人工结论。
- [ ] 只有本任务通过后，项目状态才能改为 Production Ready。

## 今日执行顺序

今天能立即完成的是：Task 0 生产差距冻结、Task 1 的 Manifest/抽样工具、Task 2 的生产存储接口骨架、Task 3 的 Adapter 合同和 Task 4 的 Worker 身份模型；这些可以在没有 30G 全量文件和正式 Gold 的情况下完成并测试。

今天不能凭代码伪造完成的是：30G 全量处理、权威规则批准、真实人工 Gold、真实 Registry 全量同步和 Production Readiness Review。这些需要你的文件、审核人、来源权限或生产环境。

## 最终交付清单

- `docker compose -f docker-compose.production.yml up` 可启动生产依赖。
- `catchain dataset manifest`、`catchain sync registry`、`catchain worker run`、`catchain review queue`、`catchain review decide`、`catchain score`、`catchain metrics` 有可复现命令。
- 数据库、对象存储、任务、Evidence、审核、评分和指标都有迁移、Schema、测试和运行手册。
- 生产环境不依赖开发机 `.env`、本地 SQLite 或人工修改 JSON 才能工作。
- 真实 Gold、正式 policy、灰度指标和回滚记录可由负责人复核。

**Plan status:** 本计划完成后才允许将 CATchain 标记为完整生产系统；在此之前只能标记为“生产重构进行中”。

