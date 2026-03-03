# Changelog

本文件记录项目的所有重要变更，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

版本号采用 [CalVer](https://calver.org/)（`YYYY.MM.PATCH`）。

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
