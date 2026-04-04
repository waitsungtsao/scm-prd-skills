# 行动指南（全程保留）

读取时机：初始化时加载，全程不释放。本文件是 AI 的"工作记忆管理协议"。

---

## 阶段 → 加载清单

| 阶段 | 加载 | 可释放上阶段内容 |
|------|------|----------------|
| 初始化 | context-guide, core-conventions, progress-display, env-setup | — |
| MC-01 后（自主） | + autonomous-overview | env-setup |
| MC-01 后（轻量） | + lite-mode | env-setup |
| Stage A | + stage-a-intake | — |
| Stage B 叙事规划 | + writing-principles, writing-narrative, stage-bc-generate-review | stage-a-intake |
| Stage B 撰写 | + writing-chapters, diagram-patterns | writing-narrative |
| Stage B 图表 | + diagram-yaml-schema; 查阅 examples/*.yaml | — |
| Stage B 自检 | + review-guide | writing-chapters, diagram-* |
| Stage C 审阅 | （review-guide + stage-bc 已加载） | writing-principles |
| Stage D 原型 | + prototype-planning | review-guide |
| 交付 | review-guide（约束索引提取） | 其余全部 |

**轻量模式**：Stage L1 = lite-mode 已加载；Stage L2 = + diagram-patterns（如需图表）；Stage L3 = 审阅交付 + Word 生成。批量模式交互流程相同，输出为一个文件含 N 个需求。

**修订模式**：MC-01 前选择修订 → + revision-mode，内部使用自主模式执行。

---

## 每阶段核心要求速查

| 阶段 | 锚点 |
|------|------|
| **Stage A** | 收敛标准=假设自洽+鉴别点已排除。开发者测试/替代方案测试/标记测试。不按清单提问。 |
| **叙事规划** | 三个核心问题：故事是什么 / 哪些主线哪些支撑 / 读者记住什么。NP-01~11 静默自检。方案评估（因果链/合理性/成本权衡）。 |
| **撰写** | 按叙事详略逐章写。事实>观点，具体>抽象。模板是菜单不是框架。Feature Heading 自动渲染。 |
| **自检** | 脚本先行(CK-1.8/2.6a/5.4~5.9)→AI 语义(CK-0/3/4/7/9/10)。诊断自洽性，不开清单。 |
| **审阅** | 假设总览表→批量文本反馈（不逐条 AskUserQuestion）。静默确认机制。 |
| **交付** | 交付选项(multiSelect) → Word/交付精要/测试骨架/用户故事。约束索引更新。 |
| **轻量 L1** | 0-1 轮对话。批量时所有需求的追问合并为一次。 |
| **轻量 L2** | 3 章叙事（背景/系统需求/注意事项）。AI 内部叙事思考，不输出叙事规划。脚本+AI 快速自检。 |
| **轻量 L3** | 自由文本反馈，最多 2 轮大改。Word 输出（批量注意标题层级）。 |

---

## 退回时的重新加载

| 退回目标 | 重新加载 | 检查下游影响 |
|---------|---------|------------|
| 叙事规划 | writing-principles + writing-narrative | PRD 章节、自检报告 |
| 撰写 | writing-chapters + diagram-patterns | 自检报告、原型设计 |
| Stage A | stage-a-intake（罕见，方向性返工） | 全部下游 |

退回时按目标阶段执行阶段转换协议，不重新加载全部 references。

---

## 可用 Reference 一览

| 文件 | 用途 |
|------|------|
| `autonomous-overview.md` | 模式切换规则、自主模式特别约束 |
| `stage-a-intake.md` | 自适应深度、鉴别诊断、假设检验、red flags |
| `stage-bc-generate-review.md` | Stage B 生成序列 + Stage C 审阅交互 |
| `writing-principles.md` | 叙事规划核心原则、方案评估、已知背景推断 |
| `writing-narrative.md` | 叙事规划模板、NP-01~11、CD-01 定义 |
| `writing-chapters.md` | 逐章撰写指引、表注、Feature Heading |
| `diagram-patterns.md` | 图表选型、布局约定、规划策略、降级、质量校验 |
| `diagram-yaml-schema.md` | YAML DSL 完整规范 |
| `review-guide.md` | CK-0~11 检查清单、多角色审查、交付流程 |
| `lite-mode.md` | 轻量模式全流程（Stage L1-L3） |
| `revision-mode.md` | 修订模式全流程（Stage RV-A~D） |
| `prototype-planning.md` | 原型触发判断、精细度、设计模板 |
| `core-conventions.md` | 交互 ID 速查、标记体系、补充约束 |
| `progress-display.md` | 进度显示 5 层规范 |
| `env-setup.md` | 环境检测与依赖引导 |

---

## 阶段转换协议（AI 内部执行，不输出给用户）

每次进入新阶段时，静默执行以下步骤：

1. **查表**：查阅上方"阶段→加载清单"，确定目标阶段需要的 references
2. **加载**：读取需要但当前未加载的 reference 文件
3. **释放确认**：明确哪些上阶段内容不再是当前阶段的行动依据（认知边界）
4. **锚点复述**：内部快速复述目标阶段的核心要求（从上方速查表，重建工作记忆焦点）

**退回场景追加**：
5. 按目标阶段重新执行 1-4
6. 检查下游已生成文件是否受影响（查阅上方退回表）
