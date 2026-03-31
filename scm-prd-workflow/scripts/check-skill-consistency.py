#!/usr/bin/env python3
"""
check-skill-consistency.py — Skill 定义文件自检工具

扫描 skill 目录下的所有定义文件（SKILL.md、references/、templates/），验证：
1. 文件引用完整性（引用的文件是否存在）
2. 模板 front matter 字段对齐（指引提到的字段在模板中是否声明）
3. 交互ID完整性（所有ID是否有定义位置）
4. 章节引用有效性（§X.X 引用是否指向存在的章节）
5. 术语一致性（核心概念是否使用统一术语）
6. 模式覆盖完整性（横切概念是否在三种模式中都有说明）

用法:
    cd scm-prd-workflow && python3 scripts/check-skill-consistency.py
    # 或指定 skill 目录
    python3 scripts/check-skill-consistency.py /path/to/scm-prd-workflow

依赖: 无（仅使用标准库）
兼容: Python 3.8+
"""

import re
import sys
import os
import glob
from collections import defaultdict


# =============================================================================
# 配置
# =============================================================================

# 文件路径引用模式
FILE_REF_PATTERN = re.compile(
    r'`?(?:references|templates|scripts)/[\w.-]+\.(?:md|py|sh|yaml)`?'
)

# 交互ID模式
INTERACTION_ID_PATTERN = re.compile(
    r'\b(MC-\d{2}|MT-\d{2}|SL-\d{2}|SC-\d{2}|P4-\d{2}|CK-\d{1,2}[a-z]?|CK-L\d{1,2})\b'
)

# 章节引用模式：§X.X 或 Ch.X§X.X
SECTION_REF_PATTERN = re.compile(r'§(\d+\.?\d*)')

# 关键 front matter 字段 → 应出现在哪些模板
EXPECTED_FIELDS = {
    'requirement_type': [
        'templates/prd-template.md',
        'templates/lite-prd-template.md',
        'templates/requirement-brief.md',
        'templates/autonomous-intake-brief.md',
    ],
    'requirement_id': [
        'templates/prd-template.md',
        'templates/lite-prd-template.md',
        'templates/requirement-brief.md',
        'templates/autonomous-intake-brief.md',
        'templates/clarification-template.md',
    ],
}

# 术语规范：规范术语 → 应被替代的偏差术语
TERM_VARIANTS = {
    '变更范围声明': ['变更范围确认', '变更范围选择'],
    '按需生成章节': ['增量标记', '条件生成章节', '增量描述标记'],
    '系统公约': ['系统约定', '系统惯例'],
    '需求类型确认': ['需求分类确认'],
}

# 横切概念 → 应在哪些文件中有提及
CROSS_CUTTING_CONCEPTS = {
    'requirement_type': [
        'SKILL.md',
        'references/phase1-intake.md',
        'references/autonomous-mode.md',
        'references/lite-mode.md',
    ],
    '变更范围': [
        'references/phase1-intake.md',
        'references/autonomous-mode.md',
        'references/lite-mode.md',
    ],
    '未涉及的方面': [
        'references/phase3-write.md',
        'templates/prd-template.md',
        'templates/lite-prd-template.md',
    ],
}


# =============================================================================
# 工具函数
# =============================================================================

def find_skill_dir():
    """确定 skill 根目录。"""
    if len(sys.argv) > 1:
        return sys.argv[1]
    # 尝试从当前目录推断
    if os.path.isfile('SKILL.md'):
        return '.'
    if os.path.isdir('scm-prd-workflow') and os.path.isfile('scm-prd-workflow/SKILL.md'):
        return 'scm-prd-workflow'
    print("错误: 找不到 SKILL.md。请在 skill 目录下运行，或指定路径。", file=sys.stderr)
    sys.exit(1)


def read_all_md_files(skill_dir):
    """读取 skill 目录下所有 .md 文件。返回 {relative_path: content}。"""
    files = {}
    for pattern in ['*.md', 'references/*.md', 'templates/*.md']:
        for path in glob.glob(os.path.join(skill_dir, pattern)):
            rel = os.path.relpath(path, skill_dir)
            with open(path, 'r', encoding='utf-8') as f:
                files[rel] = f.read()
    return files


def extract_front_matter(content):
    """提取 YAML front matter 的原始文本。"""
    if content.startswith('---'):
        end = content.find('---', 3)
        if end > 0:
            return content[3:end]
    return ''


# =============================================================================
# 检查函数
# =============================================================================

def check_file_references(files, skill_dir):
    """检查1: 文件引用完整性。"""
    issues = []
    for filepath, content in files.items():
        for i, line in enumerate(content.split('\n'), 1):
            for match in FILE_REF_PATTERN.finditer(line):
                ref = match.group(0).strip('`')
                full_path = os.path.join(skill_dir, ref)
                if not os.path.isfile(full_path):
                    issues.append({
                        'severity': '关键',
                        'type': '文件引用',
                        'message': f'{filepath} L{i}: 引用 `{ref}` 但文件不存在',
                        'suggestion': f'创建 {ref} 或修正引用路径',
                    })
    return issues


def check_front_matter_fields(files):
    """检查2: 模板 front matter 字段对齐。"""
    issues = []
    for field, template_files in EXPECTED_FIELDS.items():
        for tpl in template_files:
            if tpl not in files:
                continue
            fm = extract_front_matter(files[tpl])
            if field not in fm:
                issues.append({
                    'severity': '关键',
                    'type': '字段缺失',
                    'message': f'{tpl}: front matter 缺少 `{field}` 字段',
                    'suggestion': f'在 {tpl} 的 YAML front matter 中添加 `{field}` 字段',
                })
    return issues


def check_interaction_ids(files):
    """检查3: 交互ID完整性。"""
    issues = []
    # 收集所有ID出现位置
    id_locations = defaultdict(list)  # id → [(file, line_num, line_text)]
    for filepath, content in files.items():
        for i, line in enumerate(content.split('\n'), 1):
            for match in INTERACTION_ID_PATTERN.finditer(line):
                id_locations[match.group(0)].append((filepath, i, line.strip()))

    # 判断ID是否有"定义上下文"（出现在标题、粗体定义、表格定义行中）
    definition_patterns = [
        re.compile(r'\*\*.*{id}.*\*\*'),  # **MC-01** 粗体
        re.compile(r'#+.*{id}'),           # 标题中
        re.compile(r'\|\s*{id}\s*\|'),     # 表格第一列
        re.compile(r'\|\s*{id}\s'),        # 表格中ID开头（如 | CK-L2 一致性 |）
        re.compile(r'{id}.*[:：]'),        # ID后跟冒号的定义行
    ]

    for id_str, locations in sorted(id_locations.items()):
        has_definition = False
        for filepath, line_num, line_text in locations:
            for pat in definition_patterns:
                concrete = re.compile(pat.pattern.replace('{id}', re.escape(id_str)))
                if concrete.search(line_text):
                    has_definition = True
                    break
            if has_definition:
                break

        # 跳过范围表示中的ID（如 P4-01 在 "P4-01~05" 中）
        is_range_ref = False
        for filepath, line_num, line_text in locations:
            if re.search(re.escape(id_str) + r'~\d', line_text):
                is_range_ref = True
                break

        if not has_definition and not is_range_ref and len(locations) <= 2:
            # 只在少数地方出现且无定义 → 可能是孤立引用
            loc_summary = ', '.join(f'{f} L{n}' for f, n, _ in locations[:3])
            issues.append({
                'severity': '警告',
                'type': 'ID无定义',
                'message': f'交互ID `{id_str}` 出现在 {loc_summary}，但未找到定义位置',
                'suggestion': f'在 SKILL.md 交互ID速查表中补充 {id_str} 的定义',
            })

    return issues


def check_section_references(files):
    """检查4: 章节引用有效性。"""
    issues = []

    # 从所有模板中提取实际存在的章节号
    template_sections = set()
    for tpl_name, tpl_content in files.items():
        if not tpl_name.startswith('templates/'):
            continue
        for line in tpl_content.split('\n'):
            # 匹配 ### X.X 或 ## 第X章 格式
            m = re.match(r'^#{2,4}\s+(\d+\.\d+)', line)
            if m:
                template_sections.add(m.group(1))
            m = re.match(r'^#{2,4}\s+第(\d+)章', line)
            if m:
                template_sections.add(m.group(1))

    # 检查指引文件中的 §X.X 引用
    guide_files = [f for f in files if f.startswith('references/') or f == 'SKILL.md']
    for filepath in guide_files:
        content = files[filepath]
        for i, line in enumerate(content.split('\n'), 1):
            for match in SECTION_REF_PATTERN.finditer(line):
                section = match.group(1)
                # 只检查有明确章节号的引用（如 §10.7），跳过模糊引用
                if '.' in section and section not in template_sections:
                    # 检查主章节号是否存在
                    main_chapter = section.split('.')[0]
                    if main_chapter in template_sections:
                        # 主章节存在但子节不存在
                        issues.append({
                            'severity': '警告',
                            'type': '章节引用',
                            'message': f'{filepath} L{i}: 引用 §{section}，但模板中未找到对应子节',
                            'suggestion': f'检查模板中是否存在 §{section} 对应的标题',
                        })
    return issues


def check_term_consistency(files):
    """检查5: 术语一致性。"""
    issues = []
    for filepath, content in files.items():
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            # 跳过注释
            if line.strip().startswith('<!--'):
                continue
            for canonical, variants in TERM_VARIANTS.items():
                for variant in variants:
                    if variant in line and canonical not in line:
                        issues.append({
                            'severity': '警告',
                            'type': '术语偏差',
                            'message': f'{filepath} L{i}: 使用了 "{variant}"，规范术语为 "{canonical}"',
                            'suggestion': f'将 "{variant}" 替换为 "{canonical}"',
                        })
    return issues


def check_mode_coverage(files):
    """检查6: 模式覆盖完整性。"""
    issues = []
    for concept, expected_files in CROSS_CUTTING_CONCEPTS.items():
        for expected_file in expected_files:
            if expected_file not in files:
                issues.append({
                    'severity': '信息',
                    'type': '模式覆盖',
                    'message': f'横切概念 "{concept}" 预期在 {expected_file} 中有说明，但文件不存在',
                    'suggestion': f'检查 {expected_file} 是否应包含 "{concept}" 相关内容',
                })
                continue
            if concept not in files[expected_file]:
                issues.append({
                    'severity': '信息',
                    'type': '模式覆盖',
                    'message': f'横切概念 "{concept}" 在 {expected_file} 中未提及',
                    'suggestion': f'考虑在 {expected_file} 中补充 "{concept}" 相关说明',
                })
    return issues


# =============================================================================
# 主函数
# =============================================================================

def main():
    skill_dir = find_skill_dir()
    files = read_all_md_files(skill_dir)

    print(f"检测到 skill 文件: {len(files)} 个")
    print()

    all_issues = []
    all_issues.extend(check_file_references(files, skill_dir))
    all_issues.extend(check_front_matter_fields(files))
    all_issues.extend(check_interaction_ids(files))
    all_issues.extend(check_section_references(files))
    all_issues.extend(check_term_consistency(files))
    all_issues.extend(check_mode_coverage(files))

    if not all_issues:
        print("✓ Skill 自检通过，未发现问题")
        sys.exit(0)

    critical = [i for i in all_issues if i['severity'] == '关键']
    warnings = [i for i in all_issues if i['severity'] == '警告']
    infos = [i for i in all_issues if i['severity'] == '信息']

    if critical:
        print("== 关键问题 ==")
        for i, issue in enumerate(critical, 1):
            print(f"  {i}. [{issue['type']}] {issue['message']}")
            print(f"     建议: {issue['suggestion']}")
        print()

    if warnings:
        print("== 警告 ==")
        for i, issue in enumerate(warnings, 1):
            print(f"  {i}. [{issue['type']}] {issue['message']}")
            print(f"     建议: {issue['suggestion']}")
        print()

    if infos:
        print("== 信息 ==")
        for i, issue in enumerate(infos, 1):
            print(f"  {i}. [{issue['type']}] {issue['message']}")
        print()

    print(f"✓ 检查完成: {len(critical)} 个关键, {len(warnings)} 个警告, {len(infos)} 个信息")
    sys.exit(1 if critical else 0)


if __name__ == '__main__':
    main()
