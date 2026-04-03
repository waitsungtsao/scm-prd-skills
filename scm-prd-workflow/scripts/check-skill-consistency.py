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
7. Gate ID 集成验证（速查表与实际文件中 gate ID 的交叉一致性）

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


def check_gate_id_integration(files):
    """检查7: 交互ID速查表与实际文件的一致性。

    从 core-conventions.md 的"交互ID速查表"提取权威ID列表，
    与所有 reference 文件 + SKILL.md 中实际出现的 gate ID 交叉验证。
    """
    issues = []
    conventions_file = 'references/core-conventions.md'
    if conventions_file not in files:
        issues.append({
            'severity': '警告',
            'type': 'Gate ID',
            'message': f'{conventions_file} 不存在，跳过交互ID速查表一致性检查',
            'suggestion': f'创建 {conventions_file} 并包含"## 交互ID速查表"',
        })
        return issues

    # --- 步骤1: 从速查表提取权威 gate ID 列表 ---
    conv_content = files[conventions_file]

    # 定位 "## 交互ID速查表" 区块
    table_start = conv_content.find('## 交互ID速查表')
    if table_start < 0:
        issues.append({
            'severity': '警告',
            'type': 'Gate ID',
            'message': f'{conventions_file} 中未找到"## 交互ID速查表"章节',
            'suggestion': '在 core-conventions.md 中添加交互ID速查表',
        })
        return issues

    # 截取到下一个 ## 或文件结尾
    next_section = conv_content.find('\n## ', table_start + 1)
    table_block = conv_content[table_start:next_section] if next_section > 0 else conv_content[table_start:]

    # 解析表格行，提取 ID 列（第一列）
    # 跳过删除线条目 ~~ID~~
    gate_id_range_pattern = re.compile(r'([A-Z]{2,4})-(\d{1,2})~(\d{1,2})')
    gate_id_single_pattern = re.compile(r'([A-Z]{2,4})-(\d{1,2})')
    gate_id_alpha_pattern = re.compile(r'([A-Z]{2,4})-([A-Z]{2,4})')  # e.g. CK-PT

    authoritative_ids = set()
    table_lines = table_block.split('\n')
    for line in table_lines:
        # 表格行以 | 分隔
        if not line.strip().startswith('|'):
            continue
        # 跳过表头分隔行
        if re.match(r'\|\s*-', line):
            continue
        # 跳过表头
        cols = [c.strip() for c in line.split('|')]
        cols = [c for c in cols if c]  # 去空
        if not cols:
            continue
        id_cell = cols[0]
        # 跳过删除线条目
        if '~~' in id_cell:
            continue
        # 跳过表头行
        if id_cell == 'ID':
            continue

        # 展开范围: SC-01~06 → SC-01, SC-02, ..., SC-06
        range_match = gate_id_range_pattern.search(id_cell)
        if range_match:
            prefix = range_match.group(1)
            start = int(range_match.group(2))
            end = int(range_match.group(3))
            width = len(range_match.group(2))  # 保留前导零宽度
            for n in range(start, end + 1):
                authoritative_ids.add(f'{prefix}-{str(n).zfill(width)}')
            continue

        # 字母组合ID: CK-PT
        alpha_match = gate_id_alpha_pattern.search(id_cell)
        if alpha_match:
            authoritative_ids.add(alpha_match.group(0))
            continue

        # 单个ID: ENV-01, MC-01
        single_match = gate_id_single_pattern.search(id_cell)
        if single_match:
            authoritative_ids.add(single_match.group(0))
            continue

    if not authoritative_ids:
        issues.append({
            'severity': '警告',
            'type': 'Gate ID',
            'message': '未能从交互ID速查表中提取到任何 gate ID',
            'suggestion': '检查速查表格式是否为标准 Markdown 表格',
        })
        return issues

    # --- 步骤2: 扫描所有文件中出现的 gate ID ---
    # 宽泛模式：2~4个大写字母 + 短横 + 数字或大写字母
    broad_gate_pattern = re.compile(r'\b([A-Z]{2,4}-(?:\d{1,2}|[A-Z]{2,4}))\b')

    # 收集每个 gate ID 在哪些文件出现（排除 core-conventions.md 本身）
    id_in_files = defaultdict(set)  # gate_id → {file1, file2, ...}

    for filepath, content in files.items():
        if filepath == conventions_file:
            continue  # 速查表本身不算"引用"
        for line in content.split('\n'):
            # 跳过删除线内容
            if '~~' in line:
                line = re.sub(r'~~[^~]*~~', '', line)
            for match in broad_gate_pattern.finditer(line):
                gate_id = match.group(1)
                # 验证格式：要么 LETTERS-DIGITS，要么 LETTERS-LETTERS
                if not (re.match(r'^[A-Z]{2,4}-\d{1,2}$', gate_id) or
                        re.match(r'^[A-Z]{2,4}-[A-Z]{2,4}$', gate_id)):
                    continue
                id_in_files[gate_id].add(filepath)

    # --- 步骤3: 报告缺失与未注册 ---

    # 3a: 权威列表中的ID，在 reference 文件中无引用
    for gate_id in sorted(authoritative_ids):
        if gate_id not in id_in_files:
            issues.append({
                'severity': '警告',
                'type': 'Gate ID 缺引用',
                'message': f'交互ID `{gate_id}` 在速查表中已注册，但未在任何 reference 文件或 SKILL.md 中引用',
                'suggestion': f'在对应的 reference 文件中补充 {gate_id} 的使用或定义',
            })

    # 3b: reference 文件中出现但不在权威列表中的 gate ID
    all_found_ids = set(id_in_files.keys())

    # 过滤：排除已知的非 gate ID 模式（占位符、业务术语等）
    noise_patterns = re.compile(
        r'^(?:'
        r'ID-\d{1,2}'      # 表头噪音 (ID-01)
        r'|AS-IS|TO-BE'    # 业务术语 (as-is / to-be 状态)
        r'|YYYY-\w+'       # 日期占位符 (YYYY-MM, YYYY-DD)
        r'|IF-[A-Z]{2,}'   # 接口ID占位符 (IF-XXX, IF-OMS)
        r'|PRD-[A-Z]{2,}'  # 文档ID占位符 (PRD-XX)
        r')$'
    )
    for gate_id in sorted(all_found_ids - authoritative_ids):
        if noise_patterns.match(gate_id):
            continue
        ref_files = ', '.join(sorted(id_in_files[gate_id]))
        issues.append({
            'severity': '信息',
            'type': 'Gate ID 未注册',
            'message': f'交互ID `{gate_id}` 出现在 {ref_files}，但未在速查表中注册',
            'suggestion': f'如 {gate_id} 是有效 gate ID，请在 {conventions_file} 速查表中补充注册',
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
    all_issues.extend(check_gate_id_integration(files))

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
