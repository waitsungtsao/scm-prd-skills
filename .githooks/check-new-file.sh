#!/bin/bash
# Claude Code PostToolUse hook: 关键目录文件变更提醒
# 输出注入 AI 上下文，AI 可决定何时处理（不中断当前任务）

# tool input 通过 stdin 传入（JSON），提取 file_path
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//;s/"$//')

[ -z "$FILE_PATH" ] && exit 0

case "$FILE_PATH" in
    */scripts/*.py)
        module=$(basename "$FILE_PATH" .py | tr '-' '_')
        [ "$module" = "__init__" ] || [ "$module" = "check_skill_consistency" ] && exit 0

        if ! ls tests/test_${module}*.py >/dev/null 2>&1; then
            # 新脚本，无测试
            echo "[hook] 新增脚本 $(basename "$FILE_PATH") — 需要添加 tests/test_${module}.py（pre-commit 会阻止无测试的提交）"
        else
            # 已有测试，检查是否需要更新
            echo "[hook] 修改脚本 $(basename "$FILE_PATH") — 确认 tests/test_${module}.py 是否需要同步更新"
        fi
        ;;
    */references/*.md)
        echo "[hook] 变更 reference $(basename "$FILE_PATH") — 确认 SKILL.md 加载表是否需要同步"
        ;;
    */templates/*.md)
        echo "[hook] 变更 template $(basename "$FILE_PATH") — 确认占位符是否在指引中有引用"
        ;;
esac
