#!/bin/bash
# Claude Code PostToolUse hook for Bash: git commit 后检查发版状态
# 当 AI 执行 git commit 时，检查是否堆积了过多未发版的 commit

INPUT=$(cat)

# 只在 git commit 命令后触发
echo "$INPUT" | grep -q '"command"' || exit 0
COMMAND=$(echo "$INPUT" | grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"command"[[:space:]]*:[[:space:]]*"//;s/"$//')

case "$COMMAND" in
    git\ commit*|git\ -C\ *commit*)
        ;;
    *)
        exit 0
        ;;
esac

# 检查发版状态
if [ -f "scm-prd-workflow/scripts/check-skill-consistency.py" ]; then
    CHECK=$(python3 scm-prd-workflow/scripts/check-skill-consistency.py scm-prd-workflow --short 2>/dev/null)
    if echo "$CHECK" | grep -q "critical.*建议发版"; then
        echo "[ACTION REQUIRED] 发版严重滞后 — 请先执行发版流程（更新 CHANGELOG → git tag）再继续开发"
    elif echo "$CHECK" | grep -q "建议发版"; then
        echo "[REMINDER] $(echo "$CHECK" | grep -o '自 v[^ ]* .*')"
    fi
fi
