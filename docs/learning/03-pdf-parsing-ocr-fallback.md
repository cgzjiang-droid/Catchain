# 第三课：PDF解析、质量分流与OCR Fallback

## 这一步解决什么问题

Raw层已经保存了原始PDF和Hash，但业务字段抽取不能直接依赖文件字节。
Parsed层把某个明确的`DocumentVersion`转换为逐页文字，并记录使用了哪个
Parser、哪些页面使用OCR，以及每页的质量数据。

```text
DocumentVersion
  → PyMuPDF原生文字
  → 页面质量判断
  → 有视觉内容的低质量页执行OCR
  → 真空白页保持为空
  → ParsedDocument入库
```

## 为什么不对整份PDF执行OCR

原生PDF文字通常更快、更准确，也保留更稳定的字符内容。对所有页面执行OCR会
增加时间和计算成本，还可能把清晰原文识别错。因此CATchain先使用PyMuPDF，
只把未达到确定性质量条件的页面列为候选。

当前文字规则检查：

- 非空白字符数量是否低于下限；
- Unicode乱码替换字符比例是否超过上限。

这里的阈值衡量页面文字质量，不是LLM置信度。

## 为什么文字为零不一定需要OCR

文字为零可能表示扫描图片，也可能表示PDF中的真正空白页。真实数据验证发现
32个低文字量页面中有3个真空白页。如果全部送入OCR，系统会浪费资源，甚至从
噪声中生成不存在的文字。

系统因此只对低文字候选页做一次小尺寸灰度渲染，计算非白色像素比例：

- 有足够视觉内容：调用OCR；
- 没有视觉内容：保留空白，并写入warning。

这仍是启发式规则。它能稳定分流，但不能证明所有有视觉内容的页面都包含文字。

## OCR adapter为什么是独立接口

解析服务依赖`OcrAdapter`，而不是直接把Tesseract命令写进业务流程。测试可以使用
fake adapter精确验证调用了哪一页；生产环境使用`TesseractOcrAdapter`。以后如果
更换OCR工具，Parsed合同和上层提取逻辑不需要一起重写。

Tesseract adapter会：

1. 把指定的一页渲染为临时PNG；
2. 使用参数列表调用本地Tesseract CLI；
3. 获取标准输出中的文字；
4. 删除临时图片；
5. 对工具缺失、超时、非零退出和空结果返回明确失败。

## 为什么Parsed结果需要配置Hash

同一PDF使用不同文字阈值、页面渲染规则、Parser版本或OCR设置时，可能得到不同
结果。数据库使用`DocumentVersion ID + configuration_hash`识别一次可复现解析。
同一配置再次运行时复用已有记录，不创建重复artifact。

每个Parsed结果保存：

- 文档版本ID；
- Parser名称和版本；
- OCR名称和版本；
- 每页文字、页码、质量和`used_ocr`；
- warning；
- 创建时间和配置Hash。

## CLI如何形成完整流程

先导入Raw文件，再使用返回或数据库中的DocumentVersion UUID解析：

```bash
catchain parse raw DOCUMENT_VERSION_UUID \
  --database data/catchain.sqlite \
  --raw-root data/raw
```

命令返回JSON，包括`stored`或`reused`状态、Parsed ID、配置Hash、总页数、OCR
页数和warning。找不到文档版本、缺少Raw文件、PDF损坏或OCR工具不可用时，返回
结构化`error_code`和`message`。

## 产品经理需要掌握的边界

- Parsed文字是可复现的机器读取结果，不等于业务事实。
- OCR成功不代表文字完全正确；后续字段仍需要Evidence和人工Gold Standard。
- 页面质量阈值与字段置信度是两套不同指标。
- 解析失败必须保留明确原因，不能输出空字符串冒充成功。
- 字段提取和12维评分在后续Slice完成，不能混入解析阶段。

## 当前验证结果

- 真实数据：11份PDF、527页全部可由PyMuPDF打开。
- 质量分流：29页为有视觉内容的OCR候选，3页为空白跳过。
- 真实CLI：GS1003的6页报告完成Raw导入、Parsed生成和6页数据库持久化。
- 本机未安装Tesseract；缺失路径已验证返回`OcrToolUnavailableError`。
