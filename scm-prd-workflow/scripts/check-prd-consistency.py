#!/usr/bin/env python3
"""
check-prd-consistency.py — PRD 一致性扫描工具

扫描 PRD 文件，验证：
1. 交叉引用 ID 完整性（分层检查：G/F 必查，C/IF 按需）
2. 模糊用语和冗余表述
3. 变更点覆盖（每个变更项是否有对应功能和验收标准）

三层 ID 体系：
- 第一层（始终检查）：G-XX 目标、F-XXX 功能
- 第二层（按需检查）：C-XX 变更（update/mixed 时）、IF-XXX 接口（存在时）
- 第三层（不检查全局一致性）：规则和异常使用局部编号

用法:
    python check-prd-consistency.py <PRD文件路径>
    python check-prd-consistency.py requirements/REQ-20260318-xxx/PRD-xxx.md

依赖: 无（仅使用标准库）
兼容: Python 3.8+
"""

import re
import sys
import os
from collections import defaultdict


# =============================================================================
# PRD 模式检测
# =============================================================================

def detect_prd_mode(content):
    """检测 PRD 模式和需求类型，用于自适应检查。"""
    mode = 'full'  # full / lite
    requirement_type = 'new'  # new / update / mixed

    # 从 front matter 检测
    if content.startswith('---'):
        end = content.find('---', 3)
        if end > 0:
            fm = content[3:end]
            if 'mode: lite' in fm:
                mode = 'lite'
            for line in fm.split('\n'):
                line = line.strip()
                if line.startswith('requirement_type:'):
                    val = line.split(':', 1)[1].strip().strip('"\'')
                    if val in ('update', 'mixed', 'new'):
                        requirement_type = val

    # 兜底：按章节数判断
    chapter_count = len(re.findall(r'^##\s+第\d+章', content, re.MULTILINE))
    if chapter_count <= 7 and mode != 'lite':
        mode = 'lite'

    return mode, requirement_type


# =============================================================================
# ID 模式定义
# =============================================================================

ID_PATTERNS = {
    'G': re.compile(r'\bG-(\d{2,3})\b'),
    'C': re.compile(r'\bC-(\d{2,3})\b'),
    'F': re.compile(r'\bF-(\d{3})\b'),
    'IF': re.compile(r'\bIF-(\d{3})\b'),
}

# 第一层 ID（始终检查）
TIER1_IDS = {'G', 'F'}
# 第二层 ID（按需检查：C 仅 update/mixed，IF 仅存在时）
TIER2_IDS = {'C', 'IF'}

# 各 ID 类型的预期定义章节（full 模式）
DEFINITION_CHAPTERS = {
    'G': '第2章',
    'C': '第4章',
    'F': '第6章',
    'IF': '第7章',
}

# lite 模式章节映射
DEFINITION_CHAPTERS_LITE = {
    'G': '第2章',
    'C': '第3章',
    'F': '第4章',
}


def extract_ids(text, prefix):
    """提取文本中所有指定前缀的 ID。"""
    pattern = ID_PATTERNS[prefix]
    return set(pattern.findall(text))


def find_definition_and_reference(lines, prefix):
    """分析每个 ID 的定义位置和引用位置。"""
    pattern = ID_PATTERNS[prefix]
    id_locations = defaultdict(lambda: {'defined': [], 'referenced': []})

    current_chapter = '未知章节'
    for i, line in enumerate(lines, 1):
        # 检测章节标题
        chapter_match = re.match(r'^#{1,3}\s+(?:第)?(\d+)', line)
        if chapter_match:
            current_chapter = f'第{chapter_match.group(1)}章'

        for match in pattern.finditer(line):
            full_id = f"{prefix}-{match.group(1)}"
            # 判断是定义还是引用
            # 定义：出现在标题中 或 出现在表格第一列 或 紧跟功能名称
            is_definition = (
                line.strip().startswith(f'### {full_id}') or
                line.strip().startswith(f'| {full_id}') or
                line.strip().startswith(f'**{full_id}')
            )
            if is_definition:
                id_locations[full_id]['defined'].append((i, current_chapter))
            else:
                id_locations[full_id]['referenced'].append((i, current_chapter))

    return id_locations


def check_id_consistency(content, lines, skip_prefixes=None, lenient_unreferenced=False):
    """检查所有 ID 的定义与引用完整性。

    Args:
        skip_prefixes: 跳过检查的 ID 前缀集合（如 lite 模式跳过 IF/BR）
        lenient_unreferenced: 是否将"已定义未引用"降级为信息级别（update 模式下按需生成章节可能导致）
    """
    issues = []
    if skip_prefixes is None:
        skip_prefixes = set()

    for prefix in ID_PATTERNS:
        if prefix in skip_prefixes:
            continue

        locations = find_definition_and_reference(lines, prefix)

        for full_id, info in sorted(locations.items()):
            if not info['defined'] and info['referenced']:
                ref_lines = ', '.join(f'L{loc[0]}' for loc in info['referenced'][:3])
                issues.append({
                    'severity': '关键',
                    'type': 'ID未定义',
                    'message': f'{full_id} 被引用（{ref_lines}）但未找到定义位置',
                    'suggestion': f'在{DEFINITION_CHAPTERS.get(prefix, "对应章节")}中添加 {full_id} 的定义',
                })
            elif info['defined'] and not info['referenced']:
                def_lines = ', '.join(f'L{loc[0]}' for loc in info['defined'][:3])
                severity = '信息' if lenient_unreferenced else '警告'
                issues.append({
                    'severity': severity,
                    'type': 'ID未引用',
                    'message': f'{full_id} 已定义（{def_lines}）但未被其他章节引用',
                    'suggestion': f'检查 {full_id} 是否需要在验收标准或流程图中引用',
                })

    return issues


def check_fuzzy_words(content):
    """检查模糊用语。"""
    issues = []
    fuzzy_patterns = [
        ('大概', '请给出具体数值'),
        ('可能', '请明确是否会发生'),
        ('一般', '请明确具体条件'),
        ('适当', '请量化标准'),
        ('合理', '请量化标准'),
        ('及时', '请给出时间要求'),
        ('灵活', '请明确具体规则'),
        ('可配置', '请说明配置项、默认值和配置入口'),
    ]

    # 冗余用语检测
    redundancy_patterns = [
        ('进行', '删除"进行"，直接用动词'),
        ('相关的', '删除"相关的"或明确具体对象'),
        ('一定程度上', '删除或量化程度'),
        ('基本上', '删除"基本上"或说明例外'),
        ('总体来说', '删除"总体来说"'),
        ('需要注意的是', '删除，直接陈述'),
        ('众所周知', '删除'),
        ('不言而喻', '删除，明确说明'),
    ]

    # 填充句检测
    filler_patterns = [
        ('本章是', '删除填充句'),
        ('以下将详细描述', '删除填充句，直接描述'),
        ('以下将逐一说明', '删除填充句，直接说明'),
        ('下面我们来看', '删除填充句'),
    ]

    # 排除词表：包含模糊词但语义明确的合法术语
    exclusions = {
        '及时': ['及时性', '及时率'],
        '一般': ['一般纳税人', '一般贸易', '一般计税'],
        '可能': ['可能性', '不可能'],
        '合理': ['合理性'],
        '进行': ['进行中', '进行时'],
        '相关的': ['相关的系统', '相关的接口'],
    }

    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        # 跳过代码块和注释
        if line.strip().startswith('```') or line.strip().startswith('<!--'):
            continue
        for word, suggestion in fuzzy_patterns:
            if word in line:
                # 检查是否命中排除词表中的合法术语
                excluded = False
                for exc_term in exclusions.get(word, []):
                    if exc_term in line:
                        excluded = True
                        break
                if excluded:
                    continue
                issues.append({
                    'severity': '警告',
                    'type': '模糊用语',
                    'message': f'L{i}: 发现模糊用语 "{word}"',
                    'suggestion': suggestion,
                })

        for word, suggestion in redundancy_patterns:
            if word in line:
                excluded = False
                for exc_term in exclusions.get(word, []):
                    if exc_term in line:
                        excluded = True
                        break
                if excluded:
                    continue
                issues.append({
                    'severity': '信息',
                    'type': '冗余用语',
                    'message': f'L{i}: 发现冗余用语 "{word}"',
                    'suggestion': suggestion,
                })

        for word, suggestion in filler_patterns:
            if word in line:
                issues.append({
                    'severity': '信息',
                    'type': '填充句',
                    'message': f'L{i}: 疑似填充句 "{word}"',
                    'suggestion': suggestion,
                })

    return issues


def check_change_coverage(content, lines):
    """检查变更项是否有对应的功能点和验收标准。"""
    issues = []
    c_ids = extract_ids(content, 'C')
    f_ids = extract_ids(content, 'F')

    # 检查每个 C-XX 是否在功能点的"关联变更"中被引用
    for c_num in sorted(c_ids):
        c_full = f'C-{c_num}'
        # 检查是否在 F-XXX 的关联变更中出现
        found_in_func = False
        for line in lines:
            if '关联变更' in line and c_full in line:
                found_in_func = True
                break
        if not found_in_func:
            issues.append({
                'severity': '警告',
                'type': '变更未关联功能',
                'message': f'变更项 {c_full} 未在任何功能点的"关联变更"字段中被引用',
                'suggestion': f'确认 {c_full} 的实现功能点，并在 Ch.6 中添加关联',
            })

    return issues


def check_er_consistency(content, mode):
    """检查数据模型/ER图一致性。"""
    issues = []
    if mode == 'lite':
        return issues

    has_new_entity = bool(re.search(r'新增.*实体|新增.*表|新建.*系统|是否新增.*是', content))
    has_er_section = bool(re.search(r'###\s*7\.2\s*数据模型', content))

    if has_new_entity and not has_er_section:
        issues.append({
            'severity': '关键',
            'type': 'ER图缺失',
            'message': '检测到新增实体/新建系统，但未找到 §7.2 数据模型章节',
            'suggestion': '在 Ch.7 中添加 §7.2 数据模型，包含 ER 图和实体说明表',
        })

    return issues


def main():
    if len(sys.argv) < 2:
        print("用法: python check-prd-consistency.py <PRD文件路径>", file=sys.stderr)
        sys.exit(1)

    prd_path = sys.argv[1]
    if not os.path.isfile(prd_path):
        print(f"错误: 文件不存在: {prd_path}", file=sys.stderr)
        sys.exit(1)

    with open(prd_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    mode, requirement_type = detect_prd_mode(content)
    print(f"检测到 PRD 模式: {mode}, 需求类型: {requirement_type}")

    # 根据模式和需求类型决定跳过的 ID 前缀
    skip_prefixes = set()
    if mode == 'lite':
        # 轻量模式只检查 G 和 F
        skip_prefixes = {'C', 'IF'}
    elif requirement_type == 'new':
        # 新建类型不检查 C（无变更项）
        skip_prefixes = {'C'}

    # update/mixed 模式下，未引用的 ID 降级为信息（按需生成章节可能导致部分ID只定义不引用）
    lenient_unreferenced = requirement_type in ('update', 'mixed')

    all_issues = []
    all_issues.extend(check_id_consistency(content, lines, skip_prefixes, lenient_unreferenced))
    all_issues.extend(check_fuzzy_words(content))
    if requirement_type in ('update', 'mixed'):
        all_issues.extend(check_change_coverage(content, lines))
    all_issues.extend(check_er_consistency(content, mode))

    # 输出结果
    if not all_issues:
        print("✓ PRD 一致性检查通过，未发现问题")
        sys.exit(0)

    critical = [i for i in all_issues if i['severity'] == '关键']
    warnings = [i for i in all_issues if i['severity'] == '警告']
    infos = [i for i in all_issues if i['severity'] == '信息']

    print(f"PRD 一致性检查结果: {len(critical)} 个关键问题, {len(warnings)} 个警告, {len(infos)} 个信息")
    print()

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

    sys.exit(1 if critical else 0)


if __name__ == '__main__':
    main()
