# CATchain 使用说明

## 当前能做什么

当前已实现本地PDF导入、SHA-256去重、文档版本、逐页解析、OCR分流、Regex候选
抽取与12维关键词Baseline。SQLite保存文档与Parsed页面；抽取/评分候选和成功
run记录保存为不可变JSON。真实LLM、事实验证、最终评分、审核台与联网抓取待开发。
完整进度见 [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md)。

## 安装与检查

需要Python 3.12或更新版本及uv。先进入仓库根目录：

```bash
export UV_PROJECT_ENVIRONMENT=venv
uv sync --dev
venv/bin/python -m pytest -q
venv/bin/ruff check .
venv/bin/catchain --help
```

OCR需要在系统单独安装Tesseract及相应语言数据，不是Python依赖。没有OCR工具
时，需OCR的页面会明确报错；不应把错误解释为没有文档或成功提取。

## 1. 导入一份自己的PDF

```bash
venv/bin/catchain ingest local ./project.pdf \
  --registry verra \
  --project-id VCS-1234 \
  --source-url https://真实来源地址/文件.pdf \
  --document-type project_description
```

Registry允许acr、gold_standard、verra。来源地址必须替换成真实地址，项目ID
应与来源一致。document-type还支持monitoring_report、validation_report、
verification_report、registry_export、other。不要把占位示例当认证来源。

默认数据库为data/catchain.sqlite，原文件按Hash存入data/raw。重复相同内容
复用版本。复制输出里的Document version ID用于下一步，不需要手动查询数据库。

## 2. 逐页解析

```bash
venv/bin/catchain parse raw DOCUMENT_VERSION_UUID
```

把DOCUMENT_VERSION_UUID替换为上一步ID。输出JSON里复制parsed_document_id。
原生文字质量不足且页面有内容时会调用OCR，真空白页保留并记录warning。
可通过--tesseract-executable指定工具路径，--ocr-language指定语言。
开发时降低文字量阈值只是对比设置，不等于完成OCR质量验证。

## 3. 抽取候选与关键词评分

```bash
venv/bin/catchain extract baseline PARSED_UUID \
  --project-id VCS-1234 --registry verra
venv/bin/catchain score keywords PARSED_UUID
```

替换PARSED_UUID；项目/Registry必须与导入时一致。输出artifact_path指向JSON
文件，包含result与run。抽取结果保存原值、标准化值、单位、原文页码/片段/位置、
缺失原因和unvalidated状态。同字段不同候选保留，不能当已裁决答案。
关键词分数和keyword_score_ratio只用于Baseline对比，不是项目质量或准确率。

重复运行会返回reused，原文件与原run ID保留。损坏或冲突文件会返回失败，
不会自动覆盖。请先调查原因，不要删除错误证据来让命令通过。

## 自定义存储位置

导入与解析支持--database和--raw-root，抽取与评分支持--database和--output-dir。
同一流程的数据库路径和Raw路径必须一致。数据库、Raw PDF、private候选输出、
个人数据和凭证不上传GitHub；仓库只包含代码、小型测试和文档。

## 当前已知边界

- 55个观察字段的合同不代表Regex已覆盖55字段；没有规则与未命中分别说明原因。
- 原文可定位不代表事实语义、单位或日期已经正确，验证和人工审核尚待后续Slice。
- 开发pilot的3个来源为明确占位、Gold样本少1项目、OCR工具未安装；不能宣称MVP已通过。
- 成功run在结果JSON里，失败run完整持久化和Canonical数据库表还未实现。

后续按进度表进入真实LLM抽取→验证→事实存储→评估→审核台，保持普通Workflow。

## Slice 5开发检查点：LLM合同

当前可运行离线边界检查：

```bash
venv/bin/python -m pytest tests/unit/extraction/test_llm_contract.py -q
```

这不是模型抽取命令；目前没有LLM CLI。下一步接入DeepSeek，密钥使用
`DEEPSEEK_API_KEY`环境变量，不能写进代码、文档或聊天。API鉴权和实际小样本
调用待验证。本机连接DeepSeek和GitHub成功，不代表所有Registry都已测试。
详见Slice 5实施计划和第5课；当前页数/字符上限不等于Token或费用上限。
