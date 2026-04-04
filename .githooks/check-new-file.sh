#!/bin/bash
# Claude Code PostToolUse hook: 关键目录文件变更提醒
# 输出注入 AI 上下文作为 actionable todo，AI 应在当前任务完成后处理

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//;s/"$//')

[ -z "$FILE_PATH" ] && exit 0

case "$FILE_PATH" in
    */scripts/*.py)
        module=$(basename "$FILE_PATH" .py | tr '-' '_')
        [ "$module" = "__init__" ] || [ "$module" = "check_skill_consistency" ] && exit 0

        if ! ls tests/test_${module}*.py >/dev/null 2>&1; then
            echo "[ACTION REQUIRED] 新增脚本 $(basename "$FILE_PATH") — 在提交前必须创建 tests/test_${module}.py（pre-commit 会阻止无测试的提交）"
        else
            echo "[CHECK] 修改脚本 $(basename "$FILE_PATH") — 检查 tests/test_${module}.py 是否仍覆盖变更，不覆盖则更新"
        fi
        ;;
    */references/*.md|*/references/**/*.md)
        fname=$(basename "$FILE_PATH")
        skill_dir=$(echo "$FILE_PATH" | sed 's|/references/.*||')
        if [ -f "$skill_dir/SKILL.md" ] && grep -q "$fname" "$skill_dir/SKILL.md"; then
            : # 已注册，不提醒
        else
            echo "[CHECK] 变更 reference $fname — 未在 SKILL.md 加载表中注册，确认是否需要添加"
        fi
        ;;
    */templates/*.md)
        echo "[CHECK] 变更 template $(basename "$FILE_PATH") — 确认占位符在指引中有引用"
        ;;
    */SKILL.md)
        echo "[CHECK] 变更 SKILL.md — 运行 python3 scripts/check-skill-consistency.py 验证一致性"
        ;;
esac
