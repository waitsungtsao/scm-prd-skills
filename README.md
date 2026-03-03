# 供应链 PRD 智能生产技能集 / SCM PRD Skills

一套 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 自定义技能（Custom Skills），用于供应链领域的业务知识沉淀和产品需求文档（PRD）智能生产。

## 技能简介

### 1. scm-knowledge-curator（知识管家）

通过"记者式"结构化访谈，将散落的业务知识系统化沉淀为可复用的知识库。

- **触发方式**：描述知识梳理意图，如"帮我梳理一下 OMS 业务"、"把这些文档整理成知识库"
- **产出**：`knowledge-base/` 目录下的结构化知识卡片集合
- **适用场景**：项目启动摸底、新业务域接入、流程变更后知识更新

### 2. scm-prd-workflow（PRD 工作台）

从需求到 PRD 的全流程生产线，支持三种工作模式。Skill 触发后会通过模式确认门控让用户选择模式。

#### 三模式对比

| 维度 | 交互模式 | 自主模式（默认） | 轻量模式 |
|------|---------|----------------|---------|
| 适用场景 | 高精度需求、关键系统变更 | 需求较完整、快速出初稿 | 简单需求、常规改动、团队有共识 |
| 用户交互 | 10-20+ 轮 | 2-3 轮 | 0-1 轮 |
| PRD 章节 | 15 章 | 15 章 | **7 章** |
| 产出文件 | intake + clarification + PRD + review-report | 同左 | **仅 PRD**（+ 可选 Mermaid 图） |
| 标记体系 | `[建议]` 需确认 | `[推断]` + `[待确认]` | **仅 `[待确认]`，上限 3 个** |
| 澄清维度 | 9 个维度逐一讨论 | 9 个维度 AI 推断 | **无独立澄清** |
| 自检 | CK-1 ~ CK-7（42+ 项） | CK-1 ~ CK-8（48+ 项） | **CK-L1 ~ CK-L3（3 项）** |
| 图表格式 | Mermaid + YAML→drawio | 同左 | **仅 Mermaid** |
| Word 输出 | 默认提供 | 默认提供 | 不提供（可主动要求） |

#### 自主模式（默认）

提供需求背景后，AI 一次性生成完整 PRD，用户集中审阅修改。适合快速出初稿。

| 阶段 | 名称 | 核心动作 |
|------|------|---------|
| Stage A | 压缩录入 | 1-2 轮对话收集关键信息 |
| Stage B | 自主生成 | 一次性生成 `intake.md` + `clarification.md` + `PRD` + `review-report.md` |
| Stage C | 审阅迭代 | 用户审阅假设总览表，批量确认/修改，AI 迭代更新 |

自主模式使用三级标记体系区分 AI 生成内容的确认程度：

| 标记 | 含义 | 审阅方式 |
|------|------|---------|
| （无标记） | 已确认事实 | 无需处理 |
| `[推断]` | 行业标准做法、专业推断 | 无异议则默认确认 |
| `[待确认]` | 需用户决策的业务问题 | 必须明确确认或修改 |

#### 交互模式

逐阶段 Q&A 确认，适合高精度需求、需要逐步把关的场景。

| 阶段 | 名称 | 产出 |
|------|------|------|
| Phase 1 | 需求录入 | `intake.md` |
| Phase 2 | 需求澄清 | `clarification.md` |
| Phase 3 | 方案输出 | `PRD-{名称}.md` / `.docx` |
| Phase 4 | 自检审查 | `review-report.md` |

#### 轻量模式

适合简单需求和常规改动，直接生成 7 章精简版 PRD，"快进快出"。

| 阶段 | 名称 | 核心动作 |
|------|------|---------|
| Stage L1 | 快速录入 | 0-1 轮对话，确认"改什么"+"改成什么样" |
| Stage L2 | 直接生成 | 一次性生成 7 章精简 PRD（+ 可选 Mermaid 图） |
| Stage L3 | 快速审阅 | 用户确认或小改，最多 2 轮迭代 |

轻量模式的 7 章结构：文档信息 → 需求概述 → 业务变更点 → 功能说明 → 流程与交互（可选） → 验收标准 → 备注。

#### 模式切换

三种模式可随时切换，切换时保留已有产出内容。

| 方向 | 触发方式 | 行为 |
|------|---------|------|
| 任意 → 轻量 | 用户说"够了，出精简版就行" | 基于已有信息生成精简 PRD |
| 轻量 → 自主 | 复杂度升级 / 用户要求"补充完整版" | 保留内容，扩展为 15 章 |
| 轻量 → 交互 | 用户要求"逐步讨论" | 保留内容，进入 Phase 2 |
| 自主 ↔ 交互 | 用户主动切换 / AI 建议切换 | 保留已有产出文件 |

#### 轻量模式复杂度升级

当轻量模式发现需求超出其覆盖范围时，AI 会建议升级模式：

| 触发条件 | 说明 | 建议方向 |
|---------|------|---------|
| `[待确认]` 超过 3 个 | 业务歧义太多 | → 自主模式 |
| 变更点超过 5 个 | 变更范围大 | → 自主模式 |
| 需跨系统接口变更 | 集成复杂度高 | → 自主/交互模式 |
| 需要数据迁移 | 风险高 | → 自主模式 |
| 连续 2 轮审阅大改 | 需更深入讨论 | → 交互模式 |

#### 流程图绘制

PRD 中的流程图根据类型和复杂度选择格式：

| 图表类型 | 格式 | 说明 |
|---------|------|------|
| 泳道图（跨角色/跨系统协作） | **YAML → draw.io** | 泳道横向排列为列，流程从上往下，列间有清晰分隔 |
| 复杂流程（>12 节点） | **YAML → draw.io** | 精确布局，避免交叉混乱 |
| 状态流转图 | Mermaid | `stateDiagram-v2` |
| 时序图 | Mermaid | `sequenceDiagram` |
| 数据流向图 / 简单流程 | Mermaid | `graph LR` / `graph TD` |

YAML → draw.io 转换依赖 Python 3 + PyYAML。技能启动时会自动检测环境，不可用时引导用户安装依赖、仅保留 YAML 源文件或回退 Mermaid。

- **触发方式**：描述 PRD 需求，如"帮我写一个 PRD"、"快速出一份 PRD"、"这个需求要怎么设计"
- **产出**：`requirements/REQ-{日期}-{简称}/` 目录下的完整文档集
- **适用场景**：OMS、WMS、TMS、BMS、数据看板等供应链系统的需求文档编写

## 安装

### 推荐方式：全局安装（适用于所有项目）

从 GitHub 克隆仓库到本地固定位置，然后通过符号链接注册为全局技能：

```bash
# 1. 克隆仓库到本地（选择一个固定位置）
git clone git@github.com:waitsungtsao/scm-prd-skills.git ~/scm-prd-skills

# 2. 创建全局技能目录
mkdir -p ~/.claude/skills

# 3. 链接技能到全局目录
ln -s ~/scm-prd-skills/scm-knowledge-curator ~/.claude/skills/scm-knowledge-curator
ln -s ~/scm-prd-skills/scm-prd-workflow ~/.claude/skills/scm-prd-workflow
```

全局安装后，在任意目录启动 Claude Code 均可使用这两个技能，无需逐项目配置。更新时只需 `cd ~/scm-prd-skills && git pull`。

### 备选方式：项目级安装（适用于团队共享或项目隔离）

将技能安装到单个项目的 `.claude/skills/` 目录中，仅在该项目内可用：

```bash
# 在你的项目根目录下
mkdir -p .claude/skills

ln -s /path/to/scm-prd-skills/scm-knowledge-curator .claude/skills/scm-knowledge-curator
ln -s /path/to/scm-prd-skills/scm-prd-workflow .claude/skills/scm-prd-workflow
```

## 使用方式

安装完成后，在工作目录中启动 Claude Code，描述相关意图即可自动触发对应技能。

### PRD 工作台

```bash
# 1. 新建或进入你的项目工作目录
mkdir my-project && cd my-project

# 2. 启动 Claude Code
claude

# 3. 直接描述需求，技能自动触发
#    例如："帮我写一个 OMS 退货流程的 PRD"
```

产出文件生成在当前工作目录下：

```
my-project/
└── requirements/
    └── REQ-20260303-退货流程/
        ├── intake.md              # 需求录入
        ├── clarification.md       # 需求澄清
        ├── PRD-退货流程.md         # PRD 文档
        ├── PRD-退货流程.docx       # Word 版本
        ├── review-report.md       # 自检报告
        └── diagrams/              # 流程图
            ├── *.mermaid          # Mermaid（状态图/时序图/数据流/简单流程）
            ├── *.diagram.yaml     # YAML 泳道图源文件
            └── *.drawio           # draw.io 文件（由脚本从 YAML 转换）
```

### 知识管家

```bash
# 同样在工作目录中启动 Claude Code
cd my-project
claude

# 描述知识梳理意图
# 例如："帮我梳理一下 WMS 入库业务"
```

产出文件生成在当前工作目录下：

```
my-project/
└── knowledge-base/
    ├── _index.md                  # 知识索引
    ├── glossary.yaml              # 术语表
    └── domain-wms-inbound.md      # 知识卡片
```

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
    │   ├── autonomous-mode.md         #   自主模式操作指引
    │   ├── lite-mode.md               #   轻量模式操作指引
    │   ├── diagram-patterns.md        #   流程图绘制规范
    │   └── diagram-yaml-schema.md     #   YAML 图表 DSL 规范
    ├── templates/                     # 输出模板
    │   ├── prd-template.md            #   PRD 模板（15章完整版）
    │   ├── lite-prd-template.md       #   PRD 模板（7章精简版）
    │   ├── requirement-brief.md       #   需求摘要模板
    │   ├── autonomous-intake-brief.md #   自主模式录入模板
    │   └── drawio-swimlane-template.xml # draw.io 泳道图参考模板
    └── scripts/
        ├── init_workspace.sh          # 工作区初始化脚本
        └── yaml2drawio.py             # YAML → draw.io 转换脚本
```

运行时产出（`knowledge-base/`、`requirements/`）由 `.gitignore` 排除，不纳入版本管理。

## 详细架构

参见 [ARCHITECTURE.md](ARCHITECTURE.md)，包含系统架构图、技能拆分策略、工作空间约定和核心设计原则。

## 版本策略

本项目采用 CalVer（`YYYY.MM.PATCH`）版本号，如 `v2026.03.0`。

## License

MIT
