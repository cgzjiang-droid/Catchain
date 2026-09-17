# Slice 6：验证与正式事实边界

沿用旧ACM0002字段、现有Parsed/Evidence/ProjectExtraction合同和SQLite。
不新增模型调用或编排依赖，不把机械检查成功解释为事实已被认可。

- [x] Task 1：候选机械验证与CLI。
  - 核对文档/run/项目身份、字段类型、数值、完整ISO日期、单位、原页码和字符位置。
  - 返回missing、rejected或needs_review，保留原候选及具体问题，不删除证据。
  - 同字段冲突、模糊日期、低于0.8置信度转审核；null置信度不能当高置信度。
  - 未确认语义支持的候选保持needs_review，没有自动Canonical写入。
- [x] Task 2：跨字段日期/单位/方法学规则、跨文档与版本冲突。
  - 权威来源优先级必须字段化、版本化；新文档不能仅因更新就覆盖旧正式值。
- [x] Task 3：Canonical候选/证据/验证/审核决策数据库和迁移。
  - 只有显式通过规则或审核决策的值才成为正式事实；保留所有候选和拒绝理由。
- [x] Task 4：审核裁决输入、修改前后值、审核人/理由/证据和幂等性验收。
  - 无法裁决时UNRESOLVED；格式错误保留草稿并指出位置。审核台UI仍在Slice 8。

Task 1只做可检查的软件规则。引用存在不等于语义正确；财务/法规/方法学政策不凭空设定。
0.8是已讨论的产品分流阈值，并非经Gold校准的概率或上线标准。

## Task 1验收

validate extraction接受Regex/LLM候选artifact，从SQLite核对来源/run/Parsed身份，
输出不可变验证报告，重复运行复用报告与run。保留原值和原证据；所有候选仍不自动入库。
字段类型只限定已明确的文本、数值、整数、布尔和日期；语义/类型尚未定义的业务字段
返回field_contract_pending，避免根据名字编造合同。除容量/整数的明确范围外，其他
负计量值先要求字段化业务规则审核，不直接断言原文件错误。

真实ACR125已保存响应：2项待审核、2项缺失、0项Canonical写入、0次模型调用。
8个JSON Schema中新增ExtractionValidationReport，旧候选合同保持不变。

## Task 2验收与边界

新增validate project：接收同项目的验证报告，从SQLite核对来源，保存独立不可变一致性报告。
日期先后只在同份报告内检查，跨文档比较仅限项目层字段；核证周期与计量值不视作项目常量。
差异保留全部候选、页码证据、来源哈希和处理run，状态为unresolved。
权威策略manual-unresolved-v1明确不自动挑选新版本；完整字段权威矩阵需业务确认后版本化。
ACM0002未确认时阻止假定业务适用范围；暂不实现未核实的公式或评分规则。
真实ACR125单文档离线验证发现methodology_scope_unconfirmed，0次模型调用、0次正式值写入。
跨文档/跨版本行为目前由测试样例验证，尚未完成真实多文档验收。
新增第9个Schema ProjectConsistencyReport。下一步Task 3：结构化数据库。

Task 3已建立6张独立表和Alembic 0003，提供store validation原抽取+验证报告的原子导入。
保留原抽取方法/版本、两个run、候选、问题与证据，重复复用、变更拒绝、失败回滚。
正式事实与审核表仅定义，写入入口留给Task 4。跨文档一致性报告继续保存JSON，不混入单抽取验证表。
真实ACR125：4条候选（含缺失）/2条证据/0正式事实/0模型调用；下一步Task 4。

Task 4新增ReviewRequest第10个Schema、review candidates/decide CLI、完整输入审计与正式历史指针。
批准重新机械检查；拒绝/未知不改正式值；同ID复用/冲突拒绝；旧正式ID提交拒绝；失败回滚。
草稿保留原输入与错误位置。真实试跑仅unresolved，无人工批准或新增模型调用。
策略manual-reviewed-v1依赖可信操作员确认语义与权威，不具备身份认证或自动权威矩阵。
Slice 6软件闭环完成，完整业务规则与真实批准验收仍待后续验证；下一步Slice 7。
