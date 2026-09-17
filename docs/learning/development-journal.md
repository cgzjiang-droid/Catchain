# CATchain Development Learning Journal

这份日志按开发顺序记录实际讲解、命令结果、失败原因和修正。它是原始学习轨迹；每个 Slice 完成后，会再整理成主题学习笔记。

## 2026-09-09 — Slice 1 / Task 1：项目骨架

### 1. Git worktree 是什么

同一个 Git 仓库可以有多个独立工作目录。`main` 可以理解为已经确认的正式稿，而 worktree 是一张隔离的工作台。当前开发位置和分支是：

```text
目录：worktrees/slice-1-domain-foundation
分支：codex/slice-1-domain-foundation
```

这样做的原因是：未完成的代码、失败测试和实验提交不会直接进入 `main`。它不是复制一个新仓库；两个工作目录共享 Git 历史，但各自有独立的检出文件和分支。

### 2. uv、虚拟环境和锁文件

`uv` 负责解析项目依赖、创建隔离环境并运行项目命令。本机安装后观察到：

```text
uv 0.12.11
```

`pyproject.toml` 描述项目允许使用的 Python 和依赖版本范围；`uv.lock` 记录一次解析得到的精确依赖版本。可以把前者理解为“采购规则”，后者理解为“本次实际采购清单”。

`uv sync --dev` 在当前 worktree 创建 `.venv`，并安装运行与开发依赖。该环境最终选择了 Python 3.12.7，满足项目规定的 Python 3.12+。这也说明终端里看到的全局 Python 版本不一定等于项目实际运行的版本，必须以测试输出中的解释器为准。

### 3. TDD 的 RED、GREEN、REFACTOR

TDD 的顺序是：

```text
RED：先写一个描述期望行为的测试，并确认它因为功能缺失而失败
GREEN：只写足够让测试通过的最小实现
REFACTOR：在测试保持通过的前提下改善结构
```

本任务的行为要求是：

```python
import catchain
assert catchain.__version__ == "0.1.0"
```

如果删除 `src/catchain/__init__.py`，或者不再提供 `__version__`，这个测试应当失败。

### 4. ERROR 和 FAIL 的区别

第一次直接在测试文件顶部 `import catchain`，pytest 在收集测试时就发生：

```text
ModuleNotFoundError: No module named 'catchain'
collected 0 items / 1 error
```

这说明测试函数还没有真正执行，因此状态是 `ERROR`。我们把导入放进测试行为中，并把模块缺失转换成明确失败。修正后的 RED 是：

```text
collected 1 item
FAILED tests/unit/test_package.py::test_package_exposes_version
catchain package is not importable
```

这是更好的 RED，因为测试已经执行，并清楚说明缺少什么产品行为。

### 5. GREEN 的实际结果

创建最小包文件并同步依赖后运行：

```bash
uv run pytest tests/unit/test_package.py -v
uv run ruff check .
```

观察结果：

```text
1 passed
All checks passed!
```

pytest 验证可观察行为，Ruff 检查代码中的静态问题和风格规则。两者解决的问题不同，不能互相替代。

### 6. 本次环境排障

第一次运行 Homebrew 时，安装过程在自动更新阶段产生了并发等待，且受运行环境权限限制。我们没有把“长时间无输出”猜成成功，而是检查进程和锁，确认安装状态，再验证：

```bash
command -v uv
uv --version
```

最终得到 `/opt/homebrew/bin/uv` 和明确版本号。工程上的原则是：命令是否成功要依据退出状态和可验证输出，而不是依据等待时间或主观感觉。

随后又出现了一个更隐蔽的问题：macOS 给隐藏目录的后代文件传播 `UF_HIDDEN` 标志，而 Python 会跳过带该标志的 `.pth` 文件。最初的 worktree 位于 `.worktrees/`，所以 uv 的 editable-install 路径文件没有生效。证据是 Python 启动日志明确显示：

```text
Skipping hidden .pth file: .../_editable_impl_catchain.pth
```

我们先在 `/tmp` 的非隐藏环境验证相同包可以导入，然后把 worktree 移到非隐藏的 `worktrees/`，并把 uv 环境改为非隐藏的 `venv/`。迁移虚拟环境后，pytest 一度仍使用旧绝对路径；这是因为虚拟环境命令的 shebang 保存创建时路径。虚拟环境是可再生构建产物，因此在新位置重新运行 `uv sync`，而不是继续修补旧环境。

最终验证同时满足：

```text
venv flags=-
_editable_impl_catchain.pth flags=-
Python executable=worktrees/slice-1-domain-foundation/venv/bin/python
catchain module=worktrees/slice-1-domain-foundation/src/catchain/__init__.py
```

这个排障展示了系统化 Debug 的顺序：读取错误、稳定复现、收集每一层证据、提出单一假设、做最小实验，然后修复根因。不能用 `PYTHONPATH=src` 让测试表面通过，因为那会掩盖真实安装失败。

### 7. 当前应能回答的问题

1. 为什么不直接在 `main` 上开发？
2. `pyproject.toml` 和 `uv.lock` 分别解决什么问题？
3. 为什么必须亲眼看到测试先失败？
4. pytest 的 `ERROR` 与 `FAIL` 有什么区别？
5. 删除 `src/catchain/__init__.py` 后，哪个行为会被破坏？

## 2026-09-09 — Slice 1 / Task 2：SourceDocument 与 DocumentVersion

### 1. 什么是领域模型

领域模型是“业务世界里的概念”在代码中的明确表示。CATchain 现在定义的不是随意字典，而是碳数据系统真正需要区分的对象：

```text
SourceDocument：Registry 上发现的逻辑文档
DocumentVersion：某个时间实际下载到的具体内容版本
```

两者关系可以理解为：一本书的书目记录对应多个不同版次。URL 可能不变，但服务器上的 PDF 内容可以更新，所以 URL 不能唯一证明评分使用了哪份内容。

### 2. 输入与输出

`SourceDocument` 的输入包括 Registry、Registry 项目编号、来源 URL、文档类型、标题和发现时间。输出是一个通过验证且不可变的对象，并自动获得 UUID。

`DocumentVersion` 的输入包括所属逻辑文档 UUID、SHA-256、获取时间、媒体类型、文件名、字节数和可选版本说明。输出代表一份具体内容版本。

### 3. 为什么使用枚举

`Registry` 和 `DocumentType` 使用 `StrEnum`。这能把允许值收敛为统一词表，例如代码统一存储 `verra`，而不是同时出现 `VCS`、`Verra`、`verra ` 等不同拼写。字符串枚举仍然容易序列化为 JSON 和数据库文本。

### 4. Pydantic 在这里做什么

- `HttpUrl` 检查来源 URL 的结构。
- `AwareDatetime` 要求时间带时区，避免同一个 `08:00` 无法判断属于哪个时区。
- `Field(min_length=1)` 拒绝空业务标识。
- `Field(gt=0)` 拒绝零字节或负数文件大小。
- `Annotated[str, Field(pattern=...)]` 把 SHA-256 限制为 64 位小写十六进制字符串。
- `extra="forbid"` 拒绝拼错或未声明的字段。
- `frozen=True` 防止对象创建后被原地篡改。

Pydantic 只能证明输入满足这些结构约束。它不能证明 URL 一定存在，也不能证明给出的 SHA-256 真由某份 PDF 计算而来。

### 5. 为什么不用普通字典

普通字典允许字段拼写错误、类型错误和未声明字段悄悄进入系统。领域模型把错误拦在数据边界，避免错误继续流入抽取、数据库和评分。

如果删除 `extra="forbid"`，例如 `invented_field` 可能被静默忽略，让调用方误以为字段已保存；如果删除 `frozen=True`，同一个版本对象可能在评分后被原地修改，破坏审计一致性。

### 6. TDD 观察结果

实现前，5 个测试都运行并因缺少 `SourceDocument` 或 `DocumentVersion` 而失败。实现后结果为：

```text
5 passed
All checks passed!
```

测试分别保护：有效来源身份、未知字段拒绝、大写 SHA-256 拒绝、非正文件大小拒绝和对象不可变性。我们把 SHA 格式与文件大小拆成两个测试，避免一个校验掩盖另一个校验缺失。

### 7. 面试时至少应能解释

> CATchain 把逻辑来源文档与实际内容版本分开。逻辑文档保存 Registry 身份和 URL，版本保存下载时间、文件信息和 SHA-256。这样即使 URL 内容更新，每条 Evidence 和评分仍能追溯到具体字节版本。Pydantic 负责结构验证和不可变约束，但真实性还需要后续下载、Hash 和 Evidence Validation 验证。

## 2026-09-09 — Slice 1 / Task 3：Evidence 与 Pipeline 生命周期

### 1. EvidenceRef 是什么

`EvidenceRef` 是从未来的抽取事实返回原文的引用。它包含：

```text
document_version_id：具体哪一版文档
page_number：用户看到的页码，从 1 开始
quote：支持该字段的原文
char_start / char_end：可选的页面文本字符区间
```

只存字段值而不存 Evidence，会让系统无法区分“来自原文的事实”和“模型生成的合理猜测”。不过当前 `EvidenceRef` 只是结构化引用，尚未验证 quote 是否真的存在；Evidence Validation 会在后续 Slice 实现。

### 2. 为什么页码从 1 开始

Python 列表通常从 0 开始，但 PDF 阅读器和人工审核通常把第一页叫作第 1 页。`EvidenceRef` 是面向审核者的外部引用，所以选择 one-based page，避免 UI 显示和内部值相差一页。

### 3. 为什么字符位置必须成对

我们使用半开区间：

```text
[char_start, char_end)
```

`start=10, end=20` 表示包含第 10 个字符但不包含第 20 个字符。如果只提供一端，或者 `end <= start`，就无法表示有效文本范围，所以模型拒绝该输入。

### 4. PipelineRun 是什么

`PipelineRun` 把一次阶段执行变成可查询数据。它记录阶段、状态、输入 hash、配置 hash、开始时间、结束时间和失败详情。后续可以回答：

- 哪个阶段失败？
- 处理的是哪份输入？
- 使用哪版配置？
- 是否值得重试？
- 失败和字段缺失是否被错误混淆？

### 5. 生命周期不变量

```text
RUNNING：不能已有 finished_at
SUCCEEDED / FAILED / SKIPPED：必须有 finished_at
FAILED：必须有 error_code 和 error_message
非 FAILED：不能携带错误详情
任何状态：finished_at 不能早于 started_at
```

这些约束通过 `@model_validator(mode="after")` 实现，因为它们需要同时观察多个字段。单字段 `Field(...)` 无法判断“status 和 finished_at 是否互相一致”。

### 6. TDD 与代码覆盖审查

第一轮 Task 3 从 9 个 RED 变成 9 个 GREEN。但代码复查发现另外三条生命周期分支没有测试。我们没有接受“目前测试都绿了”，而是先删除未受保护的实现，再写三个测试，观察：

```text
3 passed
3 failed with DID NOT RAISE ValidationError
```

随后只恢复对应判断，得到：

```text
Pipeline focused tests: 6 passed
Full regression suite: 18 passed
Ruff: All checks passed!
```

`DID NOT RAISE` 表示非法输入被错误接受。这个例子说明，测试的目标不是追求绿色数量，而是让每个重要错误分支都有能抓住它的行为测试。

### 7. 面试时至少应能解释

> EvidenceRef 把抽取事实关联到具体文档版本、页码和原文区间，但结构合法不等于证据真实，后续仍要验证 quote。PipelineRun 把处理过程本身建模为数据，并通过跨字段 validator 保证状态、结束时间和错误详情一致。这样失败不会被压成空字符串，也能支持审计、重试和幂等处理。

### 8. 学习者复述与修正

学习者的原始理解是：

> source 是来源，document 才是文件主体，要把来源和主体分开来。

这个方向正确，说明已经意识到来源信息和实际文件内容不能混成一个对象。更精确的模型是：`SourceDocument` 表示 Registry 上一份逻辑文档的身份，不只是来源网站；`DocumentVersion` 表示某次下载得到的具体文件内容。来源 URL 不变时，具体内容、SHA-256 和下载时间仍可能改变，因此一个 `SourceDocument` 可以关联多个 `DocumentVersion`。

## 2026-09-09 — Slice 1 / Task 4：JSON Schema 与 CLI

### 1. JSON Schema 是什么

Pydantic 模型是 Python 程序运行时使用的“验收表”，JSON Schema 是可以提供给其他程序、API 或 LLM Provider 的机器可读“字段说明书”。本任务从四个 Pydantic 模型生成四份 Schema，避免同时手写 Python 模型和另一套容易漂移的 Schema。

### 2. 输入与输出

`generate_json_schemas(output_dir)` 的输入是输出目录；它内部读取固定的公共模型清单。输出是按名称排序的四个 `Path`，以及对应的四份 JSON 文件：

```text
document-version.schema.json
evidence-ref.schema.json
pipeline-run.schema.json
source-document.schema.json
```

CLI 命令只是薄入口：

```bash
catchain schema export --output-dir schemas/generated
```

真正逻辑仍在 `generate_json_schemas()`，所以未来 API、测试或构建脚本都能复用它。

### 3. 生成结果怎么读

`source-document.schema.json` 中：

- `$defs` 保存可复用的 `Registry` 和 `DocumentType` 枚举定义。
- `properties` 描述字段及类型。
- `required` 指出必须提供的字段。
- `additionalProperties: false` 来自 `extra="forbid"`。
- `format: uuid`、`date-time` 和 `uri` 描述标准格式。

不同 JSON Schema 消费者对 `format` 的强制程度可能不同，因此生产系统仍要在自己的入口执行 Pydantic Validation。

### 4. JSON Schema 没有表达什么

生成的 `evidence-ref.schema.json` 包含 `page_number >= 1`、字符位置下限和 quote 非空，但没有自动表达：

```text
char_start 与 char_end 必须同时出现
char_end 必须大于 char_start
```

原因是这两条是 Pydantic `model_validator` 中的跨字段 Python 逻辑，不会自动转换成标准 JSON Schema 条件。这证明“有 JSON Schema”不等于“所有业务验证都能跨语言表达”。

### 5. 确定性输出

生成函数使用稳定的模型名称排序、JSON key 排序、固定缩进和结尾换行。连续运行两次后，四份文件的 SHA-256 完全一致。这让 Schema 可以安全进入 Git：只有模型契约真正变化时才出现 diff。

### 6. Ruff 发现的 REFACTOR

第一版 CLI 行为测试全部通过，但 Ruff B008 指出 `typer.Option(...)` 不应直接作为函数默认值执行。我们使用 `Annotated[Path, typer.Option(...)]` 保存 CLI 元数据，普通 `Path` 保存默认值。修改前后同一组 3 个行为测试都通过，说明这是保持行为不变的重构。

### 7. TDD 结果

```text
实现前：3 failed，缺少 schema_export 和 cli 模块
实现后：3 passed
Ruff：All checks passed!
Schema 连续生成：四份 SHA-256 前后一致
```

### 8. 面试时至少应能解释

> CATchain 使用 Pydantic 模型作为 Python 内部契约，并从同一模型生成 JSON Schema 给 CLI、API 或 LLM Structured Output 使用。Schema 可以表达字段、类型、枚举和部分范围，但复杂跨字段验证仍由 Pydantic model validator 完成。导出过程保持确定性，使 Schema 变化可以通过 Git 审查。

## 2026-09-14 — Slice 2 / Task 1：Raw 文件存储与去重

### 1. 这次完成的产品能力

CATchain 现在可以把一个本地源文件保存到 Raw 层。系统根据文件真实字节计算 SHA-256，并使用哈希值作为存储路径。同一内容即使文件名不同，再次导入时也会复用已经保存的文件，不产生第二份副本。

当前实现还没有写入 SQLite，也没有解析 PDF。它只负责最基础的一件事：可靠保存进入系统的原始证据。

### 2. 输入、输出和失败

输入是本地文件路径和 Raw 根目录。输出包含：

- 文件内容的 SHA-256；
- 文件大小；
- Raw 层保存路径；
- 本次是否新建文件。

缺失路径、目录和空文件会被明确拒绝。文件内容不会因重名而覆盖，原始证据也不会被后续解析或 LLM 输出改写。

### 3. 产品经理需要理解的概念

`Hash` 是文件内容的指纹，不是正确率或质量分数。两个文件字节完全相同，就得到同一个 SHA-256；只要一个字节变化，哈希通常就不同。因此它能支持去重和版本识别，但不能证明 PDF 内容真实、权威或正确。

`Content-addressed storage` 表示根据内容指纹决定存储位置。CATchain 使用哈希前两位作为子目录，再使用完整哈希作为文件名，避免同一目录堆积过多文件。

`Idempotency` 表示同一输入重复执行不会不断制造重复结果。在这个任务中，相同文件导入两次后只有一个 Raw 文件，第二次返回 `created=False`。

### 4. TDD 观察结果

生产代码出现前，5 个测试因缺少 `catchain.ingestion` 模块而无法收集。这证明测试确实覆盖一个尚不存在的能力。

最小实现完成后：

```text
Raw 存储专项测试：5 passed
完整回归测试：27 passed
```

第一次 Ruff 检查发现测试导入顺序不符合项目规则；自动整理导入后重新验证。这个问题不改变产品行为，但保持代码风格一致，便于后续审查。

### 5. 当前边界和下一步

Raw 文件已经能够安全保存和去重，但文件的 Registry、项目编号、来源 URL、文档类型和版本关系还没有写入数据库。Slice 2 的下一项任务是添加 SQLite 元数据仓库，把 Raw 内容指纹与 `SourceDocument`、`DocumentVersion` 关联起来。

## 2026-09-14 — Slice 2 / Task 2：SQLite 文档元数据

### 1. 这次完成的产品能力

CATchain 现在可以把逻辑文档和每次下载得到的内容版本写入 SQLite。读取时会重新构造经过 Pydantic 验证的 `SourceDocument` 和 `DocumentVersion`，而不是返回没有约束的数据库字典。

同一逻辑文档可以拥有多个内容版本；同一逻辑文档下相同 SHA-256 只允许出现一次。这使版本历史可以保留，同时阻止重复数据进入元数据库。

### 2. 为什么使用 Repository 和 Migration

`Repository` 把“保存和查询文档”的业务接口与 SQL 细节分开。后续管线只需要调用 `add_version` 或 `list_versions`，不需要知道表结构；未来替换数据库时，领域模型和导入流程不必一起改写。

`Migration` 是数据库结构的版本历史。初始迁移可以从空 SQLite 文件创建来源文档表、文档版本表和迁移版本表。以后字段变化通过新迁移升级，不能靠人工随意修改生产数据库。

### 3. 输入、输出与约束

输入是已经通过 Pydantic 验证的文档对象。输出是从数据库还原的同类对象或按下载时间排列的版本列表。

数据库同时执行唯一约束：

```text
(source_document_id, sha256) 必须唯一
```

它表示同一逻辑文档的相同内容不能重复成为新版本。不同逻辑文档即使内容相同，仍可以各自关联同一个内容指纹，因为它们的业务身份不同。

### 4. TDD 观察结果

仓库测试最初因缺少 `catchain.storage` 模块失败；迁移测试最初因缺少 Alembic 配置而失败。实现后，来源往返、版本排序、重复拒绝和空库迁移均通过。

```text
SQLite 专项测试：4 passed
完整回归测试：31 passed
Ruff：All checks passed
```

第一次迁移测试出现 Alembic 路径分隔配置警告，添加明确配置后全量测试不再产生警告。

### 5. 当前边界和下一步

Raw 文件存储和 SQLite 元数据目前是两个独立能力。下一项任务会把它们组合成一个本地导入服务：首次内容创建版本，重复内容复用旧版本，内容变化创建新版本并保留历史。

## 2026-09-14 — Slice 2 / Task 3：本地文档导入服务

### 1. 已完成的数据流

本地导入服务把前两项能力组合为一条可执行流程：

```text
来源文档身份 + 本地文件
→ 核对来源身份是否已存在且一致
→ 将原始字节写入 Raw 内容存储
→ 按来源文档 ID 和 SHA-256 查询已有版本
→ 相同内容复用旧版本
→ 新内容创建 DocumentVersion
```

这条流程不读取 PDF 内容，也不判断哪个版本更正确。它只保证输入系统的证据不会丢失、覆盖或重复记录。

### 2. 三种产品结果

- 首次导入：保存 Raw 文件并创建第一个文档版本；
- 重复导入：返回已有版本，标记 `duplicate=True`；
- 内容变化：保存新的 Raw 文件并创建第二个版本，旧版本继续保留。

如果调用方使用已经存在的来源文档 ID，却提交不同的 Registry、URL、类型或其他身份信息，服务会拒绝导入并返回来源冲突。这避免两个不同逻辑文档被错误合并。

### 3. 产品经理需要理解的边界

文件名不是可靠身份。同一内容可以有不同文件名，不同内容也可能都叫 `project.pdf`。CATchain 因此同时使用：

- `SourceDocument ID` 标识 Registry 上的逻辑文档；
- `SHA-256` 标识某次取得的具体字节内容；
- `DocumentVersion ID` 标识逻辑文档下的一次版本记录。

这三个身份共同支持去重、版本历史和证据追踪。

### 4. TDD 观察结果

集成测试最初因缺少 `catchain.ingestion.service` 而失败。实现后，两条测试验证了重复内容复用、内容变化保留两版、旧版字节仍可读取，以及来源元数据冲突被拒绝。

```text
导入服务专项测试：2 passed
```

下一步是通过 CLI 暴露这条流程，使用户能够用一条命令导入本地文件，并看到版本、哈希、大小、Raw 路径和是否去重。

## 2026-09-14 — Slice 2 / Task 4：本地导入 CLI

### 1. 用户现在可以做什么

用户可以通过 `catchain ingest local` 提交本地文件及其 Registry、项目编号、来源 URL 和文档类型。命令会创建所需 SQLite 表，执行 Raw 存储与版本登记，并返回新建或复用状态、SHA-256、文件大小和 Raw 路径。

CLI 根据 Registry、项目编号、来源 URL 和文档类型生成稳定的来源文档 ID。同一来源重复执行时能找到之前的来源记录，不会因为每次随机生成新 ID 而破坏去重。

### 2. TDD 观察结果

CLI 测试最初返回退出码 2，因为 `ingest local` 命令尚不存在。实现后，同一输入连续运行两次均成功，第一次报告新版本，第二次报告复用版本；数据库查询确认只有一条版本记录。

```text
CLI 专项测试：1 passed
```

第一次 Ruff 检查发现一行超过项目的 100 字符限制；拆分表达式后行为测试保持通过。

### 3. 产品边界

这个入口只支持已经位于本机的文件。Registry 自动发现、HTTP 下载、PDF 解析、OCR 和字段抽取仍未实现。下一片开发将进入 Parsed 层和 OCR fallback；在此之前，Slice 2 的 Raw 证据与版本基础可以独立验收。

## 2026-09-14 — Slice 3 / Task 1：Parsed 层数据合同

CATchain 新增 `TextQuality`、`ParsedPage` 和 `ParsedDocument`。它们记录每页最终文本、页内字符位置、确定性质量数据、解析器名称和版本，以及页面是否来自 OCR。

页面号必须从 1 连续排列，因为产品界面和 PDF 阅读器都使用一开始的页码。页内字符位置必须完整覆盖该页文本。只要有页面使用 OCR，结果就必须记录 OCR 引擎名称和版本，避免以后无法复现文字来源。

测试先因模型不存在而失败；实现后模型和 Schema 测试共 10 个通过。`ParsedDocument` 也进入 JSON Schema 自动导出，保证后续解析器、数据库和 API 使用同一数据合同。

产品经理需要掌握：Parsed 层不是“PDF 的真相”，而是某个明确解析器版本从特定 Raw 文件版本生成的可重现结果。解析结果仍需质量检查，低质量页面才进入 OCR fallback。

## 2026-09-14 — Slice 3 / Task 2：PyMuPDF 原生文字解析

CATchain 现在能够打开真实 PDF，逐页提取原生文字，并为每页计算字符数、非空白字符数、字母数字比例和乱码替换字符比例。每页保存一开始的页码、页内字符范围和 `used_ocr=False`，同时记录 PyMuPDF 的实际版本。

测试使用程序生成的两页非私密 PDF。实现前因解析模块不存在而失败；实现后正确取得两页文本，页码为 1 和 2。无效 PDF 字节会产生明确的 `PdfParseError`，不会被当作空文本成功处理。

```text
PDF 解析专项测试：2 passed
完整回归测试：43 passed
```

测试 PDF 还通过 Poppler 渲染为两张 PNG 并进行视觉检查，两页文字均清晰、没有截断，且页序与解析结果一致。下一步将用质量指标决定哪些页面进入 OCR，而不是对所有 PDF 无差别执行 OCR。

## 2026-09-14 — 真实数据首轮验证：11 个项目

从电脑上现有的 CATchain 数据中选择 ACR 5 个、GS 2 个、VCS 4 个项目，
每个项目读取一份 PDD、Project Plan 或同等核心文档。原文件留在原位置，
系统只读取内容并生成很小的 JSON、CSV 质量报告。

首轮结果为 11 份文档全部成功打开，共 527 页。32 页的原生文本少于 80 个
非空白字符，其中 3 页完全没有文字。把这 3 页渲染后发现它们都是真正的
空白页，不是包含扫描文字的图片页。

这暴露了一个产品规则问题：`文字少于阈值` 不能直接等于 `需要 OCR`。
如果空白页也执行 OCR，不但浪费成本，还可能识别出不存在的噪声文字。
因此 OCR 分流至少要区分三种结果：保留合格原生文字、对有视觉内容的低文字页
执行 OCR、把真正空白页保留为空并记录原因。

这里的 80 是页面文字量诊断阈值，不是模型置信度 80%。这次验证也没有衡量
字段答案正确率；字段正确率必须等抽取、Evidence 和人工 Gold Standard 接通后
再计算。

## 2026-09-14 — Slice 3 / Task 3：确定性 OCR 分流

OCR fallback 现在使用两层确定性判断。第一层检查原生文字量和 Unicode 乱码
替换字符比例；第二层只对第一层未通过的页面做低分辨率灰度渲染，判断页面是否
存在足够的非白色像素。这样不会为了判断空白页而渲染全部文档。

真实样本中的 32 个低文字量页面被分成 29 个有视觉内容的 OCR 候选页和 3 个
空白页。空白页保持为空并写入 warning，不会调用 OCR。集成测试使用 fake OCR
证明：质量合格页的原文不变，只有被选中的页被替换，而且结果记录 OCR 引擎名称
和版本。

Tesseract adapter 会把单页渲染为临时 PNG，调用本地 Tesseract CLI，并在结束后
删除临时图像。本机暂未安装 Tesseract；真实缺失场景返回
`OcrToolUnavailableError`，明确提示安装工具或配置路径。测试还保护超时、非零
退出和空 OCR 文本不会被记录为成功。

## 2026-09-14 — Slice 3 / Task 4：Parsed持久化与CLI

SQLite新增`parsed_documents`和`parsed_pages`。前者保存文档版本、Parser/OCR来源、
warning、创建时间和配置Hash；后者保存逐页文字、页码、质量数据和OCR标记。
Repository可以完整还原`ParsedDocument`，并拒绝同一文档版本和同一配置的重复结果。

`catchain parse raw`根据DocumentVersion UUID从Raw内容寻址目录找到PDF，执行原生
解析和选择性OCR，再返回结构化JSON。相同配置再次执行时返回`reused`，数据库仍
只有一份Parsed artifact。找不到版本、Raw文件缺失、PDF损坏和OCR失败均使用明确
错误代码，不能被记录为空成功。

真实CLI验证使用GS1003的6页报告，完成Raw导入、Parsed生成和6页数据库写入，
没有复制数据到仓库。这个文档的原生文字通过质量门，因此本机没有Tesseract也能
完成处理。

Slice 3最终验证结果：54个测试通过，Ruff通过，Alembic升级、降级和重新升级
通过，5份JSON Schema重新生成后无差异。下一步回到总计划Slice 4，先审计旧版
Regex抽取和关键词评分，再为47字段共享合同编写详细实施计划。
