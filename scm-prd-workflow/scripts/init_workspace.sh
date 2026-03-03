#!/bin/bash
# SCM PRD 工作空间初始化脚本
# 用法: bash init_workspace.sh [需求简称]

set -e

REQ_NAME="${1:-unnamed}"
DATE=$(date +%Y%m%d)
REQ_ID="REQ-${DATE}-${REQ_NAME}"
REQ_DIR="requirements/${REQ_ID}"

# 创建知识库目录（如不存在）
if [ ! -d "knowledge-base" ]; then
    mkdir -p knowledge-base
    echo "✓ 创建 knowledge-base/ 目录"
    
    # 创建空的索引文件
    cat > knowledge-base/_index.md << 'EOF'
---
type: knowledge-index
last_updated: $(date +%Y-%m-%d)
total_domains: 0
overall_completeness: 0%
---

# 供应链知识库索引

> 最后更新: $(date +%Y-%m-%d)
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

# 创建需求目录
if [ -d "${REQ_DIR}" ]; then
    echo "⚠ 需求目录 ${REQ_DIR} 已存在，跳过创建"
else
    mkdir -p "${REQ_DIR}/diagrams"
    echo "✓ 创建需求目录: ${REQ_DIR}/"
    echo "✓ 创建图表目录: ${REQ_DIR}/diagrams/"
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
