# Changelog

本文件记录项目的所有重要变更，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

版本号采用 [CalVer](https://calver.org/)（`YYYY.MM.PATCH`）。

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
