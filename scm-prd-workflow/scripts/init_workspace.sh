#!/usr/bin/env bash
# SCM PRD 工作空间初始化脚本（macOS / Linux / Git Bash on Windows）
# 用法: bash init_workspace.sh [需求简称]
#
# 注意：此脚本需要 Bash 环境。Windows 用户可通过 Git Bash 或 WSL 运行。
# Claude Code 在各平台上会通过自身工具自动完成初始化，无需手动运行此脚本。

set -e

REQ_NAME="${1:-unnamed}"
DATE=$(date +%Y%m%d)
TODAY=$(date +%Y-%m-%d)
REQ_ID="REQ-${DATE}-${REQ_NAME}"
REQ_DIR="requirements/${REQ_ID}"

# 创建知识库目录（如不存在）
if [ ! -d "knowledge-base" ]; then
    mkdir -p knowledge-base
    echo "✓ 创建 knowledge-base/ 目录"

    # 创建空的索引文件
    cat > knowledge-base/_index.md << EOF
---
type: knowledge-index
last_updated: ${TODAY}
total_domains: 0
overall_completeness: 0%
---

# 供应链知识库索引

> 最后更新: ${TODAY}
> 覆盖领域: 待添加
> 整体完整度: 0%

## 领域知识

| 文件 | 领域 | 最后更新 | 完整度 | 摘要 |
|------|------|----------|--------|------|
| （暂无） | | | | |

## 已知空白

- [ ] 待首次知识梳理

## 更新记录

| 日期 | 变更内容 | 操作人 |
|------|---------|--------|
EOF
    echo "✓ 创建 knowledge-base/_index.md"
else
    echo "ℹ knowledge-base/ 已存在"
fi

# 提示系统公约（如不存在）
if [ ! -f "knowledge-base/system-conventions.md" ]; then
    echo "ℹ 提示: knowledge-base/system-conventions.md 不存在。如需避免PRD重复描述通用组件行为（查询、排序、分页等），可在PRD流程中创建系统公约。"
fi

# 创建需求目录
if [ -d "${REQ_DIR}" ]; then
    echo "⚠ 需求目录 ${REQ_DIR} 已存在，跳过创建"
else
    mkdir -p "${REQ_DIR}/diagrams"
    echo "✓ 创建需求目录: ${REQ_DIR}/"
    echo "✓ 创建图表目录: ${REQ_DIR}/diagrams/"
    # diagrams/ 目录支持三种文件类型：
    #   .mermaid       — Mermaid 图表（状态图、时序图、数据流、简单流程）
    #   .diagram.yaml  — YAML 图表 DSL 源文件（泳道图、复杂流程）
    #   .drawio        — draw.io XML 文件（由 yaml2drawio.py 从 .diagram.yaml 转换生成）
fi

# 检测 Python 环境
PYTHON_CMD=""
for cmd in python3 python py; do
    if $cmd -c "import yaml; print('ok')" >/dev/null 2>&1; then
        PYTHON_CMD="$cmd"
        echo "✓ 检测到 Python 环境: $PYTHON_CMD"
        break
    fi
done
if [ -z "$PYTHON_CMD" ]; then
    echo "⚠ 未检测到 Python 3 + PyYAML 环境，泳道图将仅输出 .diagram.yaml 源文件"
fi

# 创建配置文件（如不存在）
if [ ! -f ".scm-prd-config.yaml" ]; then
    cat > .scm-prd-config.yaml << EOF
# SCM PRD 工作流配置
project_name: ""
default_author: ""
prd_output_format:
  - markdown
  - docx  # 取消注释此行启用Word输出
knowledge_base_path: "./knowledge-base"
requirements_path: "./requirements"
python_cmd: "${PYTHON_CMD}"
python_available: $([ -n "$PYTHON_CMD" ] && echo "true" || echo "false")
EOF
    echo "✓ 创建配置文件: .scm-prd-config.yaml"
fi

echo ""
echo "=============================="
echo "工作空间初始化完成"
echo "需求编号: ${REQ_ID}"
echo "工作目录: ${REQ_DIR}/"
echo "=============================="
echo ""
echo "下一步:"
echo "  1. 如需梳理知识库 → 使用 scm-knowledge-curator 技能"
echo "  2. 如直接开始PRD → 使用 scm-prd-workflow 技能"
