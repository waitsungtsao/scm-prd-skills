# 维护者导引 / Contributing Guide

## 文件职责地图

改什么 → 看什么 → 跑什么检查：

| 要改的内容 | 涉及文件 | 检查方式 |
|-----------|---------|---------|
| AI 行为规则（门控、标记、模式切换） | `SKILL.md` | `check-skill-consistency.py` + 人工验证行为 |
| 某阶段的详细操作指引 | `references/*.md` | `check-skill-consistency.py`（加载表对齐 + 门控 ID） |
| PRD 输出结构 | `templates/*.md` | `check-skill-consistency.py`（front matter + §引用） |
| 图表生成逻辑 | `scripts/diagram_core.py` + `yaml2drawio.py` / `yaml2svg.py` | `pytest tests/test_diagram_core.py tests/test_yaml2drawio.py` |
| Word 生成逻辑 | `scripts/md2docx.mjs` / `.py` | 手动测试（需实际 .md 输入） |
| PRD 一致性检查规则 | `scripts/check-prd-consistency.py` | `pytest tests/test_check_prd.py` |
| 知识库一致性规则 | `scripts/check-knowledge-consistency.py` | `pytest tests/test_check_knowledge.py` |
| Skill 自检规则 | `scripts/check-skill-consistency.py` | 自测：`python3 scripts/check-skill-consistency.py .` |

## 关键变更的检查清单

### 修改 SKILL.md 时

SKILL.md 是系统提示词——每次技能触发都完整加载。改动直接影响 AI 行为。

1. 如果新增/修改了 reference 文件 → 更新"Reference 文件按需加载策略"表
2. 如果新增了交互门控 → 在 `references/core-conventions.md` 交互 ID 速查表中注册
3. 如果修改了阶段流程 → 检查 `references/progress-display.md` 步骤表是否需要更新
4. 跑一遍：`python3 scripts/check-skill-consistency.py . --short`

### 修改 references/ 时

reference 文件按需加载——AI 在特定阶段才读取。

1. 新增文件 → 必须在 SKILL.md 加载表中注册（否则 AI 不知道何时读它）
2. 如果修改了门控 ID 或 CK 检查编号 → 检查 core-conventions.md 是否同步
3. 跑一遍：`python3 scripts/check-skill-consistency.py .`

### 修改 scripts/ 时

1. 修改 `diagram_core.py` → 跑 `pytest tests/test_diagram_core.py tests/test_yaml2drawio.py`
2. 修改 `check-prd-consistency.py` → 跑 `pytest tests/test_check_prd.py`
3. 修改任何 .py → `check-skill-consistency.py` 的冒烟测试会自动检查语法

### 发版时

1. 更新 `CHANGELOG.md`
2. 更新 `README.md`（否则 `check-skill-consistency.py --short` 会提醒文档过时）
3. 全量检查：`python -m pytest tests/ -v && python3 scripts/check-skill-consistency.py .`

## 提交规范

遵循 Conventional Commits：

- `feat:` — 新功能（新门控、新阶段、新检查项）
- `fix:` — 修复（行为 bug、检查误报）
- `refactor:` — 重构（提取共享模块、SKILL.md 瘦身）
- `test:` — 测试（新增测试、修复测试）
- `docs:` — 文档（README、CHANGELOG、CONTRIBUTING）

## 运行测试

```bash
# 全量测试
python -m pytest tests/ -v

# 单个模块
python -m pytest tests/test_diagram_core.py -v

# Skill 自检
python3 scm-prd-workflow/scripts/check-skill-consistency.py scm-prd-workflow
python3 scm-prd-workflow/scripts/check-skill-consistency.py scm-prd-workflow --short
```

## 依赖

| 依赖 | 用途 | 安装 |
|------|------|------|
| Python 3.8+ | 所有脚本 | 系统自带 |
| PyYAML ≥5.0 | YAML 图表转换 | `pip install pyyaml` |
| pytest | 运行测试 | `pip install pytest` |
| Node.js + docx | Word 生成（推荐） | `cd scripts && npm install` |
| python-docx | Word 生成（降级） | `pip install python-docx` |
| cairosvg | SVG→PNG 转换 | `pip install cairosvg`（可选） |
| @mermaid-js/mermaid-cli | Mermaid 本地渲染 | `npm install -g @mermaid-js/mermaid-cli`（可选） |
