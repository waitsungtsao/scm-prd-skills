# 核心公约 — 交互ID、标记体系、补充约束

读取时机：初始化完成后（所有模式通用），与 `progress-display.md` 同时加载。

---

## 交互ID速查表

| ID | 名称 | 所在文件 | 触发时机 |
|----|------|---------|---------|
| ENV-01 | 环境状态播报 | SKILL.md / env-setup.md | 初始化检测完成后 |
| MC-01 | 模式+类型确认（合并） | SKILL.md | ENV-01 后（一次交互同时确认模式和需求类型） |
| CD-01 | 章节详略选择 | phase3-write.md / autonomous-mode.md / lite-mode.md | 叙事规划输出后、撰写前（全模式） |
| SL-01 | 轻量审阅反馈 | lite-mode.md | Stage L3 |
| SL-02 | 复杂度升级建议 | lite-mode.md | Stage L2/L3 复杂度超标时 |
| SC-01~06 | 自主模式审阅交互 | autonomous-mode.md | Stage C |
| P4-01~05 | 交互模式审阅交互 | phase4-review.md | Phase 4 |
| CK-0~9 | 自检项（全模式） | phase4-review.md | Phase 4 / Stage B |
| CK-L1~5 | 自检项（轻量） | lite-mode.md | Stage L2 |
| PT-01 | 原型策略（CD-01扩展） | phase3-write.md / autonomous-mode.md | 叙事规划输出后 |
| PT-02 | 原型设计方案迭代 | prototype-planning.md | 原型设计阶段（多轮） |
| PT-03 | 原型结果确认 | prototype-planning.md | 原型生成后 |
| CK-PT | 原型一致性检查 | phase4-review.md | Phase 4 / Stage C（启用原型时） |
| RV-01 | 修订类型选择 | revision-mode.md | Stage RV-A |
| RV-02 | 修订章节详略选择 | revision-mode.md | Stage RV-B |
| RV-03 | 修订交付确认 | revision-mode.md | Stage RV-D |

---

## 标记体系

### 交互模式标记

| 标记 | 含义 | 使用场景 |
|------|------|---------|
| `[建议]` | AI建议 | 交互模式Phase 3撰写中，AI补充的内容，需用户逐条确认 |

### 自主模式标记

| 标记 | 含义 | 使用场景 | 示例 |
|------|------|---------|------|
| （无标记） | 已确认事实 | 用户明确说的、知识库中已确认的 | 用户说"涉及OMS和WMS" |
| `[推断]` | 专业推断 | 行业标准做法、由已知事实推导的必然结论 | 接口超时重试3次后转人工 `[推断]` |
| `[待确认]` | 需用户确认 | 业务边界决策、特定业务规则、多方案决策点 | 见下方格式 |

**`[待确认]` 标准格式**：

```markdown
> [待确认] 当库存不足时，系统是否应自动触发采购申请？
> 当前假设：仅通知仓库主管，不自动触发采购流程。
> 如需变更此假设，请在审阅时指出。
```

### 轻量模式标记

| 标记 | 含义 | 使用场景 |
|------|------|---------|
| （无标记） | 所有内容默认无标记 | AI推断直接写入，视为合理默认值 |
| `[待确认]` | 真正的业务歧义 | 仅用于存在多种合理方案、必须由用户决定的业务决策点（每个计入加权复杂度 +2 分） |

轻量模式**不使用** `[推断]` 和 `[建议]` 标记。用户选择轻量模式即表明团队对背景有共识，AI的专业推断视为合理默认值。每个 `[待确认]` 项计入加权复杂度 +2 分，总分 ≥ 8 触发复杂度升级（详见 `references/lite-mode.md`）。

### 标记生命周期

```
Stage B 生成 → Stage C 审阅 → 用户确认 → 移除标记 → 写入正文
                              → 用户修改 → 更新内容 → 移除标记 → 写入正文
```

- `[推断]`：用户未提异议则默认确认，批量移除
- `[待确认]`：必须等用户明确确认或修改后才移除
- 详细的标记判断标准见 `references/autonomous-mode.md`

### 标记对比速查

| 维度 | 交互模式 | 自主模式 | 轻量模式 |
|------|---------|---------|---------|
| AI 补充内容 | `[建议]` 逐条确认 | `[推断]` 默认通过 | 无标记（视为默认值） |
| 业务歧义 | 提问确认 | `[待确认]` 必须确认 | `[待确认]`（≤3 项） |
| 已确认事实 | 无标记 | 无标记 | 无标记 |

---

## 补充约束

### knowledge-discoveries 格式

PRD 过程中发现的新业务知识记录到 `knowledge-discoveries.md`：

```markdown
# Knowledge Discoveries — {需求名称}

## 新发现的业务规则
- **{规则描述}** — 来源：{用户确认/澄清讨论} — 建议沉淀到：{domain-xxx.md}

## 系统现状补充
- **{发现内容}** — 来源：{来源} — 影响：{影响评估}

## 术语补充
- **{术语}** = {定义} — 来源：{来源}
```

交付时提示用户："本次发现 N 条新业务知识，是否使用 scm-knowledge-curator 技能导入知识库？"导入方式：将 `knowledge-discoveries.md` 作为 curator 技能的输入材料，curator 解析后更新对应的领域知识卡片和 glossary.yaml

### 双向知识链接

**Workflow → Curator（知识发现导入）**：
- PRD 过程中发现的新知识自动记录到 `knowledge-discoveries.md`
- 交付时提示用户一键触发 Curator 导入
- Curator 导入后更新 `glossary.yaml` 和领域知识卡片，新术语在后续 PRD 中自动生效

**Curator → Workflow（知识更新通知）**：
- Curator 完成知识梳理后，在 `knowledge-base/_index.md` 的"更新日志"中记录变更
- Workflow 启动时读取 `_index.md`，如发现自上次 PRD 后知识库有更新，主动提示："知识库在 {日期} 有更新（{变更摘要}），已纳入本次 PRD 背景"
- 如 `glossary.yaml` 中新增了术语，自动在 PRD 术语章节（Ch.3）引用

### 模式特别约束

轻量模式和自主模式各有额外约束，详见对应 reference 文件：
- 轻量模式：`references/lite-mode.md` "轻量模式特别约束"章节
- 自主模式：`references/autonomous-mode.md` "自主模式特别约束"章节
