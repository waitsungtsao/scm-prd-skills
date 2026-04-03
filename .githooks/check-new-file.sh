#!/bin/bash
# Claude Code PostToolUse hook: 检测关键目录下的新文件，输出提醒
# 输出会被注入到 AI 上下文，AI 可决定何时处理（不中断当前任务）

# tool input 通过 stdin 传入（JSON 格式），提取 file_path
FILE_PATH=$(cat | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//;s/"$//')

[ -z "$FILE_PATH" ] && exit 0

# 只检查新创建的文件（已存在的文件修改不提醒）
# 通过检查 git status 判断：untracked = 新文件
if ! git ls-files --error-unmatch "$FILE_PATH" >/dev/null 2>&1; then
    IS_NEW=1
else
    IS_NEW=0
fi

[ "$IS_NEW" -eq 0 ] && exit 0

case "$FILE_PATH" in
    */scripts/*.py)
        module=$(basename "$FILE_PATH" .py | tr '-' '_')
        if [ "$module" != "__init__" ] && [ "$module" != "check_skill_consistency" ]; then
            if ! ls tests/test_${module}*.py >/dev/null 2>&1; then
                echo "[hook] 新增脚本 $(basename "$FILE_PATH") — 需要添加 tests/test_${module}.py（pre-commit 会阻止无测试的脚本提交）"
            fi
        fi
        ;;
    */references/*.md)
        echo "[hook] 新增 reference $(basename "$FILE_PATH") — 需要在 SKILL.md 加载表中注册"
        ;;
    */templates/*.md)
        echo "[hook] 新增 template $(basename "$FILE_PATH") — 检查占位符是否在指引中有引用"
        ;;
esac
