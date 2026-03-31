# Changelog

本文件记录项目的所有重要变更，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

版本号采用 [CalVer](https://calver.org/)（`YYYY.MM.PATCH`）。

## [2026.03.9] - 2026-03-31

### Added

- **CK-9 多角色审查**（phase4-review.md）：架构师/QA/安全/BA 四角色交叉审查，12 个检查项，支持顺序/并行(Agent)两种执行模式
- **决策日志**（decision-log-template.md）：DL-XXX 编号体系，记录方案比选过程，PRD 正文轻量引用
- **版本变更记录**（prd-changelog-template.md）：语义级变更追踪，含影响传播分析，每轮修改自动持久化
- **数据模型/ER 图**（prd-template.md Ch.7 重构）：新增 §7.2 数据模型（ER 图+实体说明表）、§7.3 数据变更规格（字段变更清单+影响分析），原 §7.2-7.6 重编号为 §7.4-7.8
- **ER 图支持**（diagram-patterns.md, diagram-yaml-schema.md, yaml2drawio.py）：Mermaid erDiagram + YAML type:er → draw.io，含实体表格渲染和 FK/PK 校验
- **yaml2svg.py**：YAML DSL → SVG 矢量图渲染器，复用 yaml2drawio.py 布局引擎，支持泳道图/流程图/ER图
- **export-diagrams.py**：批量导出 diagrams/ 下所有图表为 PNG（.diagram.yaml 经 yaml2svg，.mermaid 经 mermaid.ink API），支持增量导出
- **md2docx.py**：PRD Markdown → Word 转换，自动嵌入 diagrams/*.png 图片，支持表格/引用/代码块/内联格式
- **图表导出自动化**（SKILL.md）：初始化检测 cairosvg/python-docx/mermaid.ink 可用性，环境允许时自动导出 PNG 和生成 Word
- **PRD 简洁性规范**（phase3-write.md）：禁止同义反复/填充句/过度解释/无信息修饰词，单句≤40字
- **CK-5.6~5.9 冗余检测**（phase4-review.md）：检查同义反复、填充句、过度解释、无信息修饰词
- **check-prd-consistency.py 扩展**：新增冗余用语/填充句自动扫描、ER 图一致性检查、DL-XXX 交叉引用校验

### Changed

- **SKILL.md 精简**：从 730 行压缩至 ~450 行（-40%），删除与 reference 文件重复的 Phase 1-4 详细流程和自主/轻量模式操作步骤
- **Word 输出默认行为**：python-docx 可用时默认同时输出 Markdown + Word（含嵌入图片），不再每次询问格式
- **语言打磨**：全面精简 phase3-write.md/phase4-review.md/autonomous-mode.md/lite-mode.md/phase1-intake.md/phase2-clarify.md 中的冗余解释和括号同义描述

## [2026.03.8] - 2026-03-31

### Added

- **需求类型识别（MT-01）**（SKILL.md）：模式确认后新增需求类型问题（功能新增/功能优化/不确定），驱动按需生成章节策略
- **变更范围声明（A.2.5）**（phase1-intake.md）：update 类需求在 intake 阶段声明哪些方面涉及变更，未选中 = 沿用现有
- **系统公约模板**（templates/system-conventions-template.md）：7 个 section 覆盖 UI 模式、通用组件、交互规范、权限模型、接口公约、数据公约、非功能默认值，作为 AI 判断"标准行为无需描述"的参考
- **按需生成章节规则**（phase3-write.md）：update 类需求只生成有实质内容的章节，无内容方面不独立成节，PRD 尾部一段话统一说明
- **尾部汇总 section**（prd-template.md §10.7, lite-prd-template.md §7.3）：模板中明确"本次未涉及的方面"占位
- **假设影响等级 rubric**（autonomous-mode.md）：定义高/中/低影响判断标准（核心业务→次要流程→展示体验）
- **knowledge-discoveries.md 格式规范**（SKILL.md）：定义知识发现清单的结构和 curator 导入方式
- **交互ID速查表**（SKILL.md）：汇总 MC/MT/SL/SC/P4/CK 全部交互ID的定义位置和触发时机
- **需求类型变更协议**（SKILL.md）：允许中途变更 requirement_type，明确处理规则
- **轻量→完整转换规则总表**（autonomous-mode.md）：6 行表格明确每个章节的转换方式，标注唯一需结构重写的 Ch.4→Ch.6
- **check-skill-consistency.py**（scripts/）：Skill 定义文件自检脚本，6 类检查（文件引用、字段对齐、交互ID、章节引用、术语一致、模式覆盖）

### Changed

- **撰写原则**（SKILL.md）：新增"按需生成章节"原则，update 需求不生成空壳章节
- **禁止事项**（SKILL.md）：轻量模式从"直接省略"改为"未涉及的方面不生成独立章节，由 PRD 尾部统一说明"
- **Phase 1 确认流程**（phase1-intake.md）：5 次 AskUserQuestion 精简为 1 次合并确认
- **CK-1.1 完整性检查**（phase4-review.md）：update 需求允许按需跳过章节，不视为缺失
- **check-prd-consistency.py**（scripts/）：新增 PRD 模式检测（lite/full）和 requirement_type 感知，lite 模式跳过 IF/BR 检查，update 模式未引用 ID 降级为信息级别
- **conventions 检测**（SKILL.md）：初始化时检测 system-conventions.md，作为 AI 内部参考（不在 PRD 中引用）
- **变更范围过滤**（phase2-clarify.md）：update 需求跳过未涉及维度的详细澄清
- **scope 推断**（autonomous-mode.md Stage A, lite-mode.md Stage L1）：自主/轻量模式自动推导变更范围

### Fixed

- **yaml2drawio.py**：新增 YAML 内容类型校验，非 dict 类型给出明确错误而非 AttributeError
- **init_workspace.sh**：新增 system-conventions.md 存在性提示

## [2026.03.7] - 2026-03-29

### Added

- **glossary-template.yaml**（scm-knowledge-curator/templates/）：术语表模板，包含完整字段定义和 3 个示例条目，解决两技能间的"幽灵依赖"
- **glossary 优雅降级**（SKILL.md）：PRD Workflow 启动时检测 glossary.yaml，不存在时跳过术语校验而非报错
- **check-prd-consistency.py 流程集成**（autonomous-mode.md, phase3-write.md）：PRD 撰写后自动执行一致性扫描，发现关键问题先修复再进入自检
- **BR-XXX 分段规划**（autonomous-mode.md）：PRD 大纲确认中新增业务规则分段规划表
- **Reference 按需加载策略**（SKILL.md）：新增文件读取时机表，避免初始化时一次性加载全部 reference 文件
- **Knowledge Curator 恢复检测**（scm-knowledge-curator/SKILL.md）：Step 0 检测未完成领域，支持跨会话继续
- **Knowledge Curator 进度摘要与中断点**（scm-knowledge-curator/SKILL.md）：Step 3 增加终止条件、进度输出和显式中断协议
- **访谈框架 Module D/E/G 扩展**（interview-framework.md）���TMS 新增承运商管理/路径优化/末端配送（D5-D7），BMS 新增客户计费策略/争议对账/账期管理（E3-E5），报表新增 KPI 定义/预警监控（G3-G4）
- **轻量模式单项短路规则**（lite-mode.md）：单个变更点复杂度 ≥4 即建议升级，SL-02 展示评分明细
- **模式切换 before/after 示例**（autonomous-mode.md）：轻量→自主 Ch.4→Ch.6 转换示例
- **并行约束说明**（SKILL.md）：明确多会话并行生产同系统域 PRD 的限制
- **未完成 PRD 检测**（SKILL.md）：启动初始化增强，检测 PRD 章节不足/缺少 review-report 等中断场景
- **Mermaid 节点超限策略**（lite-mode.md）：轻量模式流程节点 >12 时建议拆分子图或升级

### Changed

- **CK-2.6a 交叉引用完整性**（phase4-review.md）：严重性从"警告"提升为"关键"
- **SC-01 假设审阅方式**（autonomous-mode.md, phase4-review.md）："带例外批量确认"改为 multiSelect 勾选需改项，降低认知负担
- **Stage C 静默确认机制前置**（autonomous-mode.md）：将 `[推断]` 默认确认规则提升为审阅核心交互原则
- **模式选择场景示例**（SKILL.md, lite-mode.md）：MC-01 三个模式增加具体使用场景示例
- **Word 输出策���**（phase3-write.md）：明确 python-docx 依赖，增加 pandoc 回退和"不阻断交付"原则
- **Knowledge Curator Step 6 质量检查**（scm-knowledge-curator/SKILL.md）：从泛泛建议改为四类具体可操作后续建议
- **Knowledge Curator 模板一致性**（knowledge-schema.md, knowledge-card.md, SKILL.md）：统一 Section 6-8 命名、sources.type 枚举值、confirmed 字段语义

### Fixed

- **yaml2drawio.py 警告/错误分离**：标签超长和节点超 20 个从 error 降为 warning，不再阻断转换
- **yaml2drawio.py 菱形节点宽度**：decision 节点宽度 ×1.4 补偿可用文字区域
- **yaml2drawio.py 画布尺寸**：pageWidth/pageHeight 根据图表实际尺寸动态计算
- **check-prd-consistency.py 模糊词误报**：增加排除词表（"及时性""一般纳税人""一般贸易"等不再误报）

## [2026.03.6] - 2026-03-18

### Added

- **CK-0 需求回溯检查**（phase4-review.md）：新增检查项，逐条核对 intake.md 痛点和目标在 PRD 中是否有对应解决方案 (Q-1)
- **CK-5.5 操作步骤合理性检查**（phase4-review.md）：单功能点超 10 步时审视是否可简化 (Q-2)
- **CK-L4/CK-L5 轻量模式自检**（lite-mode.md）：新增业务规则无歧义检查和变更点-验收标准一一对应检查 (Q-3)
- **PRD 大纲确认步骤**（autonomous-mode.md, phase3-write.md）：Stage B 正式撰写前先输出功能/接口/图表/详略大纲供用户确认 (U-3)
- **已有文档导入能力**（SKILL.md）：MC-01 模式确认后可选导入已有 PRD 草稿/需求文档 (U-4)
- **变更摘要输出**（autonomous-mode.md, phase4-review.md）：每轮修改后先输出具体改动点列表 (U-6)
- **假设变更审计日志**（phase4-review.md）：review-report.md 新增章节记录假设从原始→变更→原因的完整过程 (Q-4)
- **知识发现清单**（SKILL.md）：PRD 过程中发现的新业务知识自动记录到 `knowledge-discoveries.md` (A-3)
- **跨需求一致性扫描**（SKILL.md）：启动时扫描已有 PRD 提取关键规则和接口定义作为约束输入 (A-4)
- **clarification-template.md**（templates/）：新增独立的澄清记录模板，交互/自主模式共用 (A-6)
- **check-prd-consistency.py**（scripts/）：PRD 一致性扫描脚本，验证 ID 引用完整性、术语一致性、变更点覆盖 (T-7)
- **ID 分配规划指引**（phase3-write.md）：撰写前先规划 G/C/F/IF/BR 编号方案，避免引用断裂 (Q-6)

### Changed

- **假设分层呈现**（autonomous-mode.md）：Stage C 假设总览按影响程度分两层呈现，每个假设附加"若判断有误的影响"说明 (U-2)
- **带例外批量确认**（autonomous-mode.md, phase4-review.md）：SC-01 新增审阅选项"默认全部确认，仅指出需修改的项" (U-2)
- **真实交互轮次预期**（SKILL.md, lite-mode.md, ARCHITECTURE.md）：MC-01 模式描述更新为包含实际预估轮次和时间 (U-1)
- **CK 严重性三级分类**（phase4-review.md）：原"需修正"拆分为"关键"（业务逻辑/数据安全）和"一般"（文档结构/格式），新增严重性分级说明 (Q-5)
- **加权复杂度评分**（lite-mode.md）：轻量模式复杂度判断从简单计数改为加权评分（变更点×影响系统数×规则复杂度），阈值 ≥8 触发升级 (A-1)
- **升级章节映射说明**（lite-mode.md）：轻量→完整升级时标注每个章节的处理方式（直接复用 vs 结构重写） (A-2)
- **yaml2drawio.py 增强**：
  - 新增循环依赖检测，环上节点报错而非静默放到 level 0 (T-1)
  - 节点标签长度感知，长中文标签自动加宽节点避免溢出 (T-2)
  - 节点数超过 20 时输出警告建议拆分 (T-3)
- **init_workspace.sh**：新增 Python 环境检测逻辑，检测结果写入 `.scm-prd-config.yaml` (T-4)
- **Mermaid 回退路径明确**（phase3-write.md）：Python 不可用时 AI 直接生成 Mermaid 格式而非 YAML 自动转换 (T-5)
- **步骤-规则表拆分指引**（phase3-write.md）：单步骤关联 >2 条规则时拆为子步骤 (Q-7)
- **输入文件格式校验**（phase2-clarify.md, SKILL.md）：每个阶段开始前对上游产出文件做基本格式检查 (A-5)
- **ARCHITECTURE.md**：更新模式描述、产出文件列表、设计原则

## [2026.03.4] - 2026-03-18

### Changed

- **PRD模板结构重构**：15章 → 10章（scm-prd-workflow）
  - 合并重复内容：Ch.2+3+4 → 新Ch.2（需求概述），Ch.9+10+11 → 新Ch.7（接口与数据集成），Ch.14+15 → 新Ch.10（待定事项与附录）
  - 引入交叉引用 ID 体系：G-XXX（目标）、C-XXX（变更项）、F-XXX（功能）、IF-XXX（接口）、BR-XXX（业务规则），每个事实只写一次
  - Ch.4 业务变更总览：AS-IS 简化为一行摘要，回指 Ch.2§2.2，消除重复叙述
  - Ch.5 业务流程：去掉步骤表，流程图节点标注 F-XXX，步骤详情统一在 Ch.6
  - Ch.6 功能与规则明细：引入统一步骤-规则表（操作步骤+业务规则+异常处理合一），替代原来分离的叙述+表格
  - Ch.9 验收标准：新增"关联目标 G-XXX"和"关联功能 F-XXX"列
- **phase3-write.md**：各章节撰写指引从15章改为10章，新增 ID 编号规范和交叉引用体系说明
- **phase4-review.md**：CK-1.1 更新为10章检查，CK-2.6 增加交叉引用完整性检查（CK-2.6a），CK-8.2 更新假设总览表位置引用
- **autonomous-mode.md**：更新轻量→完整升级映射表、质疑文档化位置（§2.6）、章节引用
- **SKILL.md**：模式表格、章节列表、Stage B 描述、示例引用全部更新为10章结构
- **lite-mode.md**：更新7章PRD结构表的"对应完整PRD章节"映射、升级映射表、模式描述
- **lite-prd-template.md**：升级提示从"15章"改为"10章"
- **README.md**：PRD章节数、模板描述、模式切换说明更新
- **ARCHITECTURE.md**：技能产出描述更新

## [2026.03.3] - 2026-03-03

### Added

- **交互选项化**（scm-prd-workflow）
  - SKILL.md 新增"交互规范"章节，定义 A/B/C/D 四类交互类型及 `AskUserQuestion` 使用原则
  - 新增 4 个交互点：B组话题选择（P1-04）、批量建议处理（P3-01）、审阅方式选择（P4-01）、维度完成确认（P2-04）
  - Phase 2 新增 14 个维度内领域专属选项（P2-D 系列），覆盖业务边界、数据流、系统交互、异常处理、状态流转、权限控制、非功能性需求、数据迁移等维度

### Changed

- **phase1-intake.md**：系统模块问题改为 multiSelect 选项（P1-02），摘要确认改为4问题并发选项（P1-05），新增B组话题选择和阶段推进选项（P1-04, P1-06）
- **phase2-clarify.md**：维度排序改为选项（P2-01），逐项状态标记选项化（P2-02），矛盾处理增加 markdown 对比（P2-03），维度完成确认和阶段推进选项化（P2-04, P2-05）
- **phase3-write.md**：`[建议]` 处理增加批量/逐条选项（P3-01, P3-02），输出格式选项化（P3-03）
- **phase4-review.md**：修改与重检流程重构为选项化（P4-01~P4-04），最终交付改为2问题并发选项（P4-05），新增 Stage C 审阅选项化规范（SC-01~SC-06）
- **autonomous-mode.md**：结构化提问中系统模块改为 multiSelect（SA-02），信息不足时增加决策选项（SA-04），Stage C 审阅迭代全流程选项化（SC-01~SC-06），最终交付选项化（SC-06）
- **SKILL.md**：Phase 1-4 和 Stage A-C 描述段落增加选项化交互提示

## [2026.03.2] - 2026-03-03

### Added

- **自主生成模式**（scm-prd-workflow）
  - 新增自主模式作为默认工作模式，支持一次性生成完整PRD
  - 三阶段流程：压缩录入（Stage A）→ 自主生成（Stage B）→ 审阅迭代（Stage C）
  - 三级标记体系：无标记（已确认事实）、`[推断]`（专业推断）、`[待确认]`（需用户确认）
  - 假设总览表：汇总所有AI假设，支持批量审阅和确认
  - 模式可随时切换：自主↔交互，切换时保留已有产出
  - 新增操作指引 `references/autonomous-mode.md`
  - 新增压缩录入模板 `templates/autonomous-intake-brief.md`
  - 新增 CK-8 假设质量检查（自主模式专用）
  - PRD模板增加 `mode` 字段和假设总览表格式

### Changed

- **SKILL.md**：核心行为准则适配双模式，新增工作模式选择、自主生成模式章节、标记体系章节、自主模式特别约束
- **phase3-write.md**：新增自主模式撰写调整章节
- **phase4-review.md**：新增自主模式审查调整章节和CK-8检查项

## [2026.03.1] - 2026-03-03

### Fixed

- **输出目录错误**：技能通过符号链接安装到用户项目后，产出文件（`requirements/`、`knowledge-base/`）会错误地创建在技能安装目录而非用户项目根目录。两个 SKILL.md 中新增"工作目录约定"章节，明确区分技能资源路径（只读）与产出文件路径（读写）。
- **PRD 偶尔输出英文**：SKILL.md 中缺少明确的语言指令，导致 Claude 默认行为不稳定。两个 SKILL.md 的"重要约束"章节中新增"输出语言"子章节，默认使用简体中文撰写所有产出文件。

## [2026.03.0] - 2026-03-03

### Added

- **scm-knowledge-curator**（知识管家）技能
  - 结构化访谈框架（`references/interview-framework.md`）
  - 知识结构定义（`references/knowledge-schema.md`）
  - 知识卡片模板（`templates/knowledge-card.md`）
  - 知识索引模板（`templates/knowledge-index.md`）
  - 6 步工作流：初始化 → 确认范围 → 文档分析 → 结构化访谈 → 知识卡片生成 → 质量检查
- **scm-prd-workflow**（PRD 工作台）技能
  - 4 阶段流程：需求录入 → 需求澄清 → 方案输出 → 自检审查
  - 各阶段详细指引（`references/phase1-4`）
  - 流程图绘制规范（`references/diagram-patterns.md`）
  - PRD 模板（`templates/prd-template.md`）
  - 需求摘要模板（`templates/requirement-brief.md`）
  - 工作区初始化脚本（`scripts/init_workspace.sh`）
- **架构文档**（`ARCHITECTURE.md`）
  - 系统架构图
  - 技能拆分策略
  - 工作空间约定
  - 阶段间状态传递机制
  - 核心设计原则
