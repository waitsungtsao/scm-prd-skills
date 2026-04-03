# 供应链 PRD 智能生产技能集 / SCM PRD Skills

一套 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 自定义技能（Custom Skills），用于供应链领域的业务知识沉淀和产品需求文档（PRD）智能生产。

## 技能简介

### 1. scm-knowledge-curator（知识管家）

通过"记者式"结构化访谈，将散落的业务知识系统化沉淀为可复用的知识库。

- **触发方式**：描述知识梳理意图，如"帮我梳理一下 OMS 业务"、"把这些文档整理成知识库"
- **产出**：`knowledge-base/` 目录下的结构化知识卡片集合
- **适用场景**：项目启动摸底、新业务域接入、流程变更后知识更新

### 2. scm-prd-workflow（PRD 工作台）

从需求到 PRD 的全流程生产线，支持三种工作模式 + 修订模式。Skill 触发后会通过模式确认门控让用户选择模式。

- **触发方式**：描述 PRD 需求，如"帮我写一个 PRD"、"快速出一份 PRD"、"这个需求要怎么设计"
- **产出**：`requirements/REQ-{日期}-{简称}/` 目录下的完整文档集
- **适用场景**：OMS、WMS、TMS、BMS、数据看板等供应链系统的需求文档编写

#### 三模式对比

| 维度 | 交互模式 | 自主模式（默认） | 轻量模式 |
|------|---------|----------------|---------|
| 适用场景 | 高精度需求、关键系统变更 | 需求较完整、快速出初稿 | 简单需求、常规改动、团队有共识 |
| 用户交互 | 18-33 轮 | 5-9 轮 | 2-5 轮 |
| PRD 章节 | 10 章 | 10 章 | 7 章 |
| 产出文件 | intake + clarification + PRD + review-report | 同左 | 仅 PRD（+ 可选 Mermaid 图） |
| 标记体系 | `[建议]` 需逐条确认 | `[推断]` + `[待确认]` 三级体系 | 仅 `[待确认]`（每项+2复杂度分） |
| 澄清维度 | 9 个维度逐一讨论 | 9 个维度 AI 推断 | 无独立澄清 |
| 自检 | CK-0~CK-9（50+ 项） | CK-0~CK-9（55+ 项） | CK-L1~CK-L5（5 项） |
| 图表格式 | Mermaid + YAML→draw.io | 同左 | 仅 Mermaid |
| Word 输出 | 默认提供 | 默认提供 | 不提供（可主动要求） |
| 复杂度判断 | — | Stage A 复杂度信号检测 | 加权复杂度评分（≥8分升级） |

#### 修订模式

对已交付的 PRD 进行版本升级（V1→V2），支持评审返工、需求追加、上游变更三种修订场景。

- **快速修订**：≤2 章节的小改动折叠为单次通过
- **完整修订**（RV-A~D）：读取理解 → 增量规划 → 增量撰写 → 修订审查
- 可选"交付后效果追踪"：记录原 PRD 偏差，沉淀经验反馈

#### 原型集成（可选）

PRD 完成后，可选生成可交互原型（React + shadcn/ui 单文件 HTML）。需求 UI 复杂度高时，叙事规划阶段还可输出"快速线框"提前验证交互假设。

#### 模式切换

三种模式可随时切换，切换时保留已有产出内容。轻量模式加权复杂度超标时自动建议升级。

## 安装

### 推荐方式：全局安装

```bash
# 1. 克隆仓库到本地
git clone git@github.com:waitsungtsao/scm-prd-skills.git ~/scm-prd-skills

# 2. 创建全局技能目录并链接
mkdir -p ~/.claude/skills
ln -s ~/scm-prd-skills/scm-knowledge-curator ~/.claude/skills/scm-knowledge-curator
ln -s ~/scm-prd-skills/scm-prd-workflow ~/.claude/skills/scm-prd-workflow

# 3. (可选) 安装脚本依赖以获得完整功能
cd ~/scm-prd-skills/scm-prd-workflow/scripts
npm install          # Word 生成（docx 库）
pip install pyyaml   # YAML 图表转换
```

全局安装后，在任意目录启动 Claude Code 均可使用。更新：`cd ~/scm-prd-skills && git pull`。

### 备选方式：项目级安装

```bash
mkdir -p .claude/skills
ln -s /path/to/scm-prd-skills/scm-knowledge-curator .claude/skills/scm-knowledge-curator
ln -s /path/to/scm-prd-skills/scm-prd-workflow .claude/skills/scm-prd-workflow
```

## 使用方式

安装完成后，在工作目录中启动 Claude Code，描述意图即可自动触发对应技能。

```bash
mkdir my-project && cd my-project && claude

# PRD: "帮我写一个 OMS 退货流程的 PRD"
# 知识梳理: "帮我梳理一下 WMS 入库业务"
```

产出文件示例：

```
my-project/
├── knowledge-base/                    # 知识管家产出
│   ├── _index.md
│   ├── glossary.yaml
│   └── domain-wms-inbound.md
└── requirements/                      # PRD 工作台产出
    └── REQ-20260303-退货流程/
        ├── intake.md
        ├── clarification.md
        ├── PRD-退货流程.md / .docx
        ├── review-report.md
        ├── decision-log.md
        ├── knowledge-discoveries.md
        ├── prd-changelog.md
        ├── prototype/bundle.html      # (可选) 可交互原型
        └── diagrams/
            ├── *.mermaid
            ├── *.diagram.yaml
            └── *.drawio
```

## 项目结构

```
scm-prd-skills/
├── CLAUDE.md                              # AI 项目指引
├── CHANGELOG.md                           # 版本变更记录
├── CONTRIBUTING.md                        # 维护者导引
│
├── scm-knowledge-curator/                 # Skill 1: 知识管家
│   ├── SKILL.md                           #   技能定义（系统提示词）
│   ├── references/
│   │   ├── interview-framework.md         #   7模块访谈框架
│   │   └── knowledge-schema.md            #   知识卡片结构定义
│   ├── templates/
│   │   ├── knowledge-card.md
│   │   └── knowledge-index.md
│   └── scripts/
│       └── check-knowledge-consistency.py #   KC-1~KC-5 知识库质检
│
├── scm-prd-workflow/                      # Skill 2: PRD 工作台
│   ├── SKILL.md                           #   技能定义（系统提示词）
│   ├── references/                        #   按需加载的操作指引
│   │   ├── env-setup.md                   #     环境检测
│   │   ├── progress-display.md            #     进度提示规范（5层）
│   │   ├── core-conventions.md            #     交互ID/标记体系/补充约束
│   │   ├── phase1-intake.md               #     交互模式 Phase 1
│   │   ├── phase2-clarify.md              #     交互模式 Phase 2（9维度）
│   │   ├── phase3-write.md                #     撰写指引（NP检查+逐章CK）
│   │   ├── phase4-review.md               #     自检清单（CK-0~CK-9）
│   │   ├── autonomous-mode.md             #     自主模式（含复杂度检测）
│   │   ├── lite-mode.md                   #     轻量模式（含复杂度升级）
│   │   ├── revision-mode.md               #     修订模式（含快速修订+效果追踪）
│   │   ├── diagram-patterns.md            #     图表格式选择+降级策略
│   │   ├── diagram-yaml-schema.md         #     YAML 泳道图 DSL 规范
│   │   └── prototype-planning.md          #     原型触发/精细度/流程
│   ├── templates/                         #   产出模板（13个）
│   │   ├── prd-template.md                #     10章完整版
│   │   ├── lite-prd-template.md           #     7章精简版
│   │   ├── requirement-brief.md
│   │   ├── autonomous-intake-brief.md
│   │   ├── clarification-template.md
│   │   ├── constraints-index-template.yaml
│   │   ├── system-conventions-template.md
│   │   └── ...（共13个模板）
│   └── scripts/                           #   自动化脚本
│       ├── diagram_core.py                #     共享模块：布局/校验/颜色/CJK
│       ├── yaml2drawio.py                 #     YAML → draw.io XML
│       ├── yaml2svg.py                    #     YAML → SVG + PNG
│       ├── export-diagrams.py             #     批量图表导出
│       ├── md2docx.mjs                    #     Markdown → Word（JS，推荐）
│       ├── md2docx.py                     #     Markdown → Word（Python，降级）
│       ├── check-prd-consistency.py       #     PRD ID/术语一致性检查
│       ├── check-skill-consistency.py     #     Skill 文件自检（10类检查）
│       ├── fix-bundle-fileproto.mjs       #     原型 file:// 兼容修复
│       ├── init_workspace.sh              #     工作区初始化
│       └── package.json                   #     Node.js 依赖管理
│
└── tests/                                 # pytest 测试集（41个）
    ├── conftest.py
    ├── test_diagram_core.py
    ├── test_yaml2drawio.py
    ├── test_check_prd.py
    ├── test_check_knowledge.py
    └── fixtures/                          #   测试数据
```

## 自检与质量保障

```bash
# 运行测试
python -m pytest tests/ -v

# Skill 一致性检查（一行摘要）
python3 scm-prd-workflow/scripts/check-skill-consistency.py scm-prd-workflow --short

# Skill 一致性检查（完整报告）
python3 scm-prd-workflow/scripts/check-skill-consistency.py scm-prd-workflow
```

`check-skill-consistency.py` 覆盖 10 类检查：文件引用 / 模板字段 / 交互 ID / 章节引用 / 术语一致 / 横切概念（自动发现） / Gate ID 集成 / 脚本冒烟 / 加载表对齐 / 文档新鲜度。

## 版本策略

CalVer（`YYYY.MM.PATCH`），如 `v2026.04.7`。变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## License

MIT
