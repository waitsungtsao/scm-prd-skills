# 供应链 PRD 智能生产技能集 / SCM PRD Skills

一套 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 自定义技能（Custom Skills），用于供应链领域的业务知识沉淀和产品需求文档（PRD）智能生产。

## 技能简介

### 1. scm-knowledge-curator（知识管家）

通过"记者式"结构化访谈，将散落的业务知识系统化沉淀为可复用的知识库。

- **触发方式**：描述知识梳理意图，如"帮我梳理一下 OMS 业务"、"把这些文档整理成知识库"
- **产出**：`knowledge-base/` 目录下的结构化知识卡片集合
- **适用场景**：项目启动摸底、新业务域接入、流程变更后知识更新

### 2. scm-prd-workflow（PRD 工作台）

从需求到 PRD 的四阶段全流程生产线。

| 阶段 | 名称 | 产出 |
|------|------|------|
| Phase 1 | 需求录入 | `intake.md` |
| Phase 2 | 需求澄清 | `clarification.md` |
| Phase 3 | 方案输出 | `PRD-{名称}.md` / `.docx` |
| Phase 4 | 自检审查 | `review-report.md` |

- **触发方式**：描述 PRD 需求，如"帮我写一个 PRD"、"这个需求要怎么设计"
- **产出**：`requirements/REQ-{日期}-{简称}/` 目录下的完整文档集
- **适用场景**：OMS、WMS、TMS、BMS、数据看板等供应链系统的需求文档编写

## 安装

将技能目录添加到你的 Claude Code 项目中：

```bash
# 在你的项目根目录下
mkdir -p .claude/skills

# 方式一：复制技能目录
cp -r path/to/scm-prd-skills/scm-knowledge-curator .claude/skills/
cp -r path/to/scm-prd-skills/scm-prd-workflow .claude/skills/

# 方式二：使用符号链接（推荐，便于更新）
ln -s path/to/scm-prd-skills/scm-knowledge-curator .claude/skills/scm-knowledge-curator
ln -s path/to/scm-prd-skills/scm-prd-workflow .claude/skills/scm-prd-workflow
```

安装后在 Claude Code 中描述相关意图即可自动触发对应技能。

## 项目结构

```
scm-prd-skills/
├── ARCHITECTURE.md                    # 架构设计文档
├── scm-knowledge-curator/             # Skill 1: 知识管家
│   ├── SKILL.md                       # 技能定义
│   ├── references/                    # 参考资料
│   │   ├── interview-framework.md     #   访谈框架
│   │   └── knowledge-schema.md        #   知识结构定义
│   └── templates/                     # 输出模板
│       ├── knowledge-card.md          #   知识卡片模板
│       └── knowledge-index.md         #   知识索引模板
└── scm-prd-workflow/                  # Skill 2: PRD 工作台
    ├── SKILL.md                       # 技能定义
    ├── references/                    # 参考资料
    │   ├── phase1-intake.md           #   Phase 1 指引
    │   ├── phase2-clarify.md          #   Phase 2 指引
    │   ├── phase3-write.md            #   Phase 3 指引
    │   ├── phase4-review.md           #   Phase 4 指引
    │   └── diagram-patterns.md        #   流程图绘制规范
    ├── templates/                     # 输出模板
    │   ├── prd-template.md            #   PRD 模板
    │   └── requirement-brief.md       #   需求摘要模板
    └── scripts/
        └── init_workspace.sh          # 工作区初始化脚本
```

运行时产出（`knowledge-base/`、`requirements/`）由 `.gitignore` 排除，不纳入版本管理。

## 详细架构

参见 [ARCHITECTURE.md](ARCHITECTURE.md)，包含系统架构图、技能拆分策略、工作空间约定和核心设计原则。

## 版本策略

本项目采用 CalVer（`YYYY.MM.PATCH`）版本号，如 `v2026.03.0`。

## License

MIT
