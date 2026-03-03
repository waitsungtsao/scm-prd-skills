# 供应链PRD智能生产工作流 — 架构设计

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     SCM PRD 智能生产系统                              │
│                                                                     │
│  ┌──────────────────────┐     ┌──────────────────────────────────┐  │
│  │ Skill 1              │     │ Skill 2                          │  │
│  │ scm-knowledge-curator│     │ scm-prd-workflow                 │  │
│  │                      │     │                                  │  │
│  │ 输入：业务文档/口述  │     │ 三种模式:                        │  │
│  │ 输出：知识库文件集   │────▶│ · 交互 Phase 1-4 (逐步确认)     │  │
│  │                      │     │ · 自主 Stage A-C (先生成后审)    │  │
│  │ 触发：周期性/按需    │     │ · 轻量 Stage L1-L3 (快进快出)   │  │
│  └──────────────────────┘     └──────────────────────────────────┘  │
│         │                              │                            │
│         ▼                              ▼                            │
│  knowledge-base/               requirements/REQ-XXX/               │
│  ├── _index.md                 ├── intake.md        (自主/交互模式) │
│  ├── domain-oms.md             ├── clarification.md (自主/交互模式) │
│  ├── domain-wms.md             ├── PRD-XXX.md / .docx (全模式)    │
│  ├── domain-tms.md             ├── review-report.md (自主/交互模式) │
│  └── ...                       └── diagrams/        (全模式)       │
└─────────────────────────────────────────────────────────────────────┘
```

## 2. 技能拆分策略

### 为什么是两个技能而不是五个

| 维度 | 两个技能 | 五个技能 |
|------|---------|---------|
| 上下文连贯性 | PRD四阶段共享对话上下文 | 每次切换丢失对话历史 |
| 使用门槛 | 两个命令即可 | 用户需记忆五个触发词 |
| 知识库复用 | 明确的生产者-消费者关系 | 多对多依赖关系复杂 |
| 独立迭代 | 知识沉淀和PRD生产独立演进 | 过度拆分增加维护成本 |

### 两个技能的分工

**Skill 1: scm-knowledge-curator（知识管家）**
- 定位：业务知识的"采集-加工-存储"工具
- 触发时机：项目启动初期、新业务域接入、重大流程变更后
- 产出：结构化的知识库文件集合

**Skill 2: scm-prd-workflow（PRD工作台）**
- 定位：从需求到PRD的全流程生产线，支持三种模式
  - **自主模式**（默认）：15章完整PRD，2-3轮对话
  - **交互模式**：15章完整PRD，逐步确认
  - **轻量模式**：7章精简PRD，0-1轮对话，适合简单需求/常规改动
- 触发时机：每次有新需求需要产出PRD时
- 输入：用户需求描述 + 知识库文件（如有）
- 产出：完整/精简PRD文档 + 流程图 + 自检报告（轻量模式仅PRD + 可选图）

## 3. 工作空间约定

```
项目根目录/
├── knowledge-base/                # 知识库（Skill 1 产出）
│   ├── _index.md                  # 知识地图/目录
│   ├── domain-oms.md              # OMS领域知识
│   ├── domain-wms.md              # WMS领域知识
│   ├── domain-tms.md              # TMS领域知识
│   ├── domain-bms.md              # BMS领域知识
│   ├── integration-points.md      # 系统集成点
│   ├── business-rules.md          # 通用业务规则
│   └── glossary.yaml              # 术语表（YAML格式）
│
├── requirements/                  # 需求文件夹（Skill 2 产出）
│   ├── REQ-20250301-订单拆单优化/         # 自主/交互模式：完整文件集
│   │   ├── intake.md              # Phase 1 / Stage A 产出（轻量模式不生成）
│   │   ├── clarification.md       # Phase 2 / Stage B 产出（轻量模式不生成）
│   │   ├── PRD-订单拆单优化.md    # Phase 3 产出：PRD正文（全模式）
│   │   ├── PRD-订单拆单优化.docx  # Phase 3 产出：Word版本（轻量模式不生成）
│   │   ├── review-report.md       # Phase 4 产出：自检报告（轻量模式不生成）
│   │   └── diagrams/
│   │       ├── main-flow.diagram.yaml   # YAML 泳道图源文件（轻量模式不使用）
│   │       ├── main-flow.drawio         # draw.io 文件（轻量模式不使用）
│   │       ├── swimlane.diagram.yaml    # YAML 泳道图源文件（轻量模式不使用）
│   │       ├── swimlane.drawio          # draw.io 文件（轻量模式不使用）
│   │       ├── state-machine.mermaid    # Mermaid 状态图（全模式）
│   │       ├── sequence.mermaid         # Mermaid 时序图（全模式）
│   │       └── data-flow.mermaid        # Mermaid 数据流图（全模式）
│   └── ...
│
└── .scm-prd-config.yaml          # 项目级配置（可选）
```

## 4. 阶段间状态传递

每个阶段产出标准化的Markdown文件，包含YAML front matter：

```yaml
---
type: intake | clarification | prd | review
requirement_id: REQ-20250301-订单拆单优化
phase: 1
status: completed | in_progress | needs_revision
created: 2025-03-01
updated: 2025-03-02
---
```

下一阶段启动时，自动读取上一阶段的产出文件作为输入。

## 5. 兼容性策略

### Claude Code（主要环境）
- 技能直接读写项目目录中的文件
- 阶段转换通过文件状态自动检测
- 可执行脚本辅助（如一致性检查）

### Claude.ai（兼容环境）
- 用户手动上传上一阶段产出文件
- 知识库文件在对话开始时上传
- 产出文件通过下载链接获取

## 6. 核心设计原则

1. **禁止臆想**：对不确定的信息必须追问，严禁虚构系统现有功能或业务规则
2. **质疑优先**：AI应主动质疑不合理需求，而非奉承用户
3. **证据驱动**：所有方案建议需说明依据，联网查询的行业实践需标注来源
4. **授权写入**：任何建议性内容未经用户明确同意不得写入PRD正文
5. **增量积累**：每次PRD过程中发现的新业务知识应提示用户补充到知识库
