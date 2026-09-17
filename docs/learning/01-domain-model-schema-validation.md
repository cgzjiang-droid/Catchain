# 第一课：领域模型、Schema 与 Validation

## 这节课解决什么问题

CATchain 以后会接收 Registry metadata、PDF、Regex 结果和 LLM 结果。如果没有统一契约，不同模块就可能传递字段缺失、拼写错误、类型错误或无法追溯的普通字典。

Slice 1 先不读取 PDF，也不调用 LLM，而是建立四个基础概念：

```text
SourceDocument  → Registry 上一份逻辑文档
DocumentVersion → 某次下载得到的具体内容版本
EvidenceRef     → 某个事实对应的版本、页码和原文
PipelineRun     → 某个处理阶段的输入、配置、状态和错误
```

## 1. 领域模型是什么

领域模型是业务概念在代码中的明确表示。它不只是“给字典加类型”，而是在代码中固定我们对业务对象的理解。

例如：

```python
class SourceDocument(ImmutableDomainModel):
    registry: Registry
    registry_project_id: str
    source_url: HttpUrl
    document_type: DocumentType
    discovered_at: AwareDatetime
```

这段代码说明，一份来源文档必须属于某个 Registry，必须关联 Registry 项目编号和 URL，还要记录文档类型及发现时间。

对应实现：

- `src/catchain/domain/common.py`
- `src/catchain/domain/documents.py`
- `src/catchain/domain/evidence.py`
- `src/catchain/domain/pipeline.py`

## 2. 大白话怎么理解

可以把 Registry 想象成图书馆：

- `SourceDocument` 是目录中的书目记录；
- `DocumentVersion` 是某个具体版次；
- SHA-256 是这一本具体版次的数字指纹；
- `EvidenceRef` 是论文脚注，指出结论来自哪一版、第几页、哪段话；
- `PipelineRun` 是加工工单，记录哪一步成功或失败。

学习者最初把它理解为“source 是来源，document 是文件主体，需要分开”。这个方向正确；进一步需要记住：`SourceDocument` 本身代表一份逻辑文档，而不只是来源网站，具体文件内容由 `DocumentVersion` 表示。

## 3. CATchain 为什么需要它

同一个 URL 上的 PDF 可能被替换。如果只保存 URL，系统无法证明评分使用的是旧版还是新版。把逻辑文档和具体版本分开后，可以表达：

```text
一个 SourceDocument
    ├── DocumentVersion A：sha256=aaa...，2026-01-01 下载
    └── DocumentVersion B：sha256=bbb...，2026-03-01 下载
```

以后 Evidence 必须指向 `DocumentVersion`，不能只指向 URL。

## 4. 哪段代码实现了什么

### `ImmutableDomainModel`

```python
model_config = ConfigDict(extra="forbid", frozen=True)
```

- `extra="forbid"`：调用方提供未知字段时立即报错；
- `frozen=True`：模型创建后不能原地修改。

### `Sha256`

```python
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
```

它只接受 64 位小写十六进制字符串。

### `EvidenceRef`

```python
class EvidenceRef(ImmutableDomainModel):
    document_version_id: UUID
    page_number: int = Field(ge=1)
    quote: str = Field(min_length=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=1)
```

`model_validator` 进一步保证字符位置成对出现并且 `end > start`。

### `PipelineRun`

它把执行状态建模为数据，并保证：

- `RUNNING` 不能已经结束；
- 完成状态必须有结束时间；
- `FAILED` 必须有错误代码和消息；
- 非失败状态不能携带错误详情；
- 结束时间不能早于开始时间。

## 5. 输入是什么

模型输入是未经信任的 Python 或 JSON 数据，例如：

```python
version = DocumentVersion(
    source_document_id=source_id,
    sha256="a" * 64,
    retrieved_at=retrieved_at,
    content_type="application/pdf",
    file_name="pdd.pdf",
    byte_size=2048,
)
```

数据以后可能来自 Registry Adapter、数据库、CLI、API、Regex 或 LLM。

## 6. 输出是什么

合法输入产生不可变 Pydantic 对象，可继续序列化、存储或传给下一阶段。非法输入产生结构化 `ValidationError`，而不是空字符串。

Schema 导出命令：

```bash
catchain schema export --output-dir schemas/generated
```

会生成：

- `document-version.schema.json`
- `evidence-ref.schema.json`
- `pipeline-run.schema.json`
- `source-document.schema.json`

## 7. 底层原理是什么

Pydantic 读取 Python 类型标注和 `Field` 约束，在模型创建时验证输入。`model_validator(mode="after")` 会在单字段初步验证完成后查看整个对象，因此适合跨字段规则。

Pydantic 还能调用 `model_json_schema()` 将可表达的约束转换为 JSON Schema。CATchain 对生成结果排序并使用固定 JSON 格式，所以同样的模型会产生相同字节内容。

## 8. 为什么不用普通字典或只用数据库

普通字典不会自动阻止：

- `registry_projectid` 这种拼错字段；
- `byte_size=0`；
- 没有时区的时间；
- 已成功却携带错误消息的 PipelineRun；
- 页码为 0 的 Evidence。

数据库约束也不能代替领域模型，因为数据在写入数据库前已经需要在多个模块之间传递。验证应该尽量发生在数据进入系统的边界。

## 9. Schema Validation 能证明什么，不能证明什么

能够证明：

- 字段是否存在；
- 类型是否正确；
- 枚举值是否允许；
- 部分长度、范围和格式是否符合约束；
- 是否出现未知字段。

不能证明：

- URL 是否真的可访问；
- SHA-256 是否真的由指定 PDF 计算；
- quote 是否真的出现在那一页；
- LLM 抽取值是否符合原文；
- 项目本身是否高质量。

此外，Pydantic 的 Python 跨字段 `model_validator` 不会自动完整进入 JSON Schema。例如生成的 Evidence Schema 没有表达 `char_end > char_start`。所以 JSON Schema 与业务 Validation 是互补关系。

## 10. 为什么不用其他方法

- 不使用手写 Python Schema 加手写 JSON Schema：两套定义容易漂移；
- 不让 LLM 自己判断输出是否合法：确定性的结构问题应交给代码；
- 不在这一阶段使用数据库：先把业务对象和边界定义清楚，再设计持久化映射；
- 不用 Agent：这里没有动态决策问题，只是确定性建模和验证。

## 11. 面试官可能怎么问

1. 为什么区分逻辑文档和文档版本？
2. 什么是 Pydantic，它和 dataclass 有什么区别？
3. JSON Schema 与 Pydantic Validation 有什么关系？
4. Structured Output 是否可以消除 Hallucination？
5. 为什么 Evidence 要指向 SHA-256 对应的版本？
6. `extra="forbid"` 有什么作用？
7. 为什么模型需要不可变？
8. 单字段 Validator 和跨字段 Validator 如何选择？
9. 为什么错误应该结构化保存？
10. 怎样保证生成 Schema 可重复？

## 12. 你至少应该能够解释到什么程度

建议能够独立说出：

> CATchain 使用不可变 Pydantic 领域模型作为 Python 内部数据契约。SourceDocument 表示 Registry 上的逻辑文档，DocumentVersion 表示由 SHA-256 标识的具体内容，因此同一 URL 更新后仍能保留历史版本。EvidenceRef 指向具体版本、页码和原文，PipelineRun 则记录处理阶段和失败状态。Pydantic 能做运行时结构验证并生成 JSON Schema，但不能证明数据真实，复杂跨字段规则和 Evidence Grounding 仍需要独立 Validation。

## 13. 如果删掉代码会发生什么

- 删除 `common.py`：各模型会失去统一的未知字段拒绝、不可变性和 Hash 格式约束；
- 删除 `documents.py`：系统无法明确区分逻辑文档和内容版本；
- 删除 `evidence.py`：抽取字段无法用统一结构追溯到具体原文；
- 删除 `pipeline.py`：运行失败只能散落在日志或空值里，不能可靠查询和恢复；
- 删除 `schema_export.py`：外部消费者和未来 LLM Structured Output 没有从领域模型同步生成的契约；
- 删除测试：未来改动可能悄悄破坏这些规则而无人知道。

## 14. 自测题

1. 为什么 URL 不能唯一标识项目评分使用的 PDF？
2. SHA-256 是质量评分、数据库 ID，还是内容指纹？
3. 为什么 `EvidenceRef` 关联 `DocumentVersion` 而不是只关联 `SourceDocument`？
4. JSON Schema 为什么不能证明 LLM 没有幻觉？
5. 为什么跨字段生命周期规则使用 `model_validator`？
6. `FAILED` 状态没有错误代码时，系统应该接受还是拒绝？为什么？
