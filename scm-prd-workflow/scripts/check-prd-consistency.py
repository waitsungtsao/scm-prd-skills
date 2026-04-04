#!/usr/bin/env python3
"""
check-prd-consistency.py — PRD 一致性扫描工具

扫描 PRD 文件，验证：
1. 交叉引用 ID 完整性（分层检查：G/F 必查，C/IF 按需）
2. 模糊用语和冗余表述
3. 变更点覆盖（每个变更项是否有对应功能和验收标准）
4. 叙事信号（目标-功能连接、背景量化、验收覆盖率、异常密度）

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
    """检测 PRD 模式、需求类型和自定义章节-ID映射，用于自适应检查。

    Returns:
        (mode, requirement_type, chapter_id_map_override)
        chapter_id_map_override: dict or None — 从 front matter 的 chapter_id_map 解析，
        格式 {'G': '第2章', 'F': '第6章', ...}，未提供时为 None（使用硬编码默认值）。
    """
    mode = 'full'  # full / lite
    requirement_type = 'new'  # new / update / mixed
    chapter_id_map_override = None

    # 从 front matter 检测 — 只匹配行首的 --- 作为分隔符，
    # 避免 PRD 正文中的 --- 水平线被误判为 front matter 边界
    fm_match = re.match(r'\A---[ \t]*\n(.*?\n)---[ \t]*\n', content, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        if 'mode: lite' in fm:
            mode = 'lite'
        # 解析 requirement_type
        for line in fm.split('\n'):
            line = line.strip()
            if line.startswith('requirement_type:'):
                val = line.split(':', 1)[1].strip().strip('"\'')
                if val in ('update', 'mixed', 'new'):
                    requirement_type = val

        # 解析 chapter_id_map（简易 YAML 缩进解析，无需外部依赖）
        # 格式示例:
        #   chapter_id_map:
        #     G: 2
        #     F: 6
        fm_lines = fm.split('\n')
        in_map = False
        parsed_map = {}
        for line in fm_lines:
            stripped = line.strip()
            if stripped.startswith('chapter_id_map:'):
                # 检查是否为单行空值（即后续缩进行才是内容）
                after_colon = stripped.split(':', 1)[1].strip()
                if not after_colon or after_colon.startswith('#'):
                    in_map = True
                continue
            if in_map:
                # 缩进行属于 map；非缩进或空行结束
                if line.startswith((' ', '\t')) and ':' in stripped:
                    key, val = stripped.split(':', 1)
                    key = key.strip().strip('"\'')
                    val = val.strip().split('#')[0].strip().strip('"\'')
                    if key in ID_PATTERNS and val.isdigit():
                        parsed_map[key] = f'第{val}章'
                else:
                    in_map = False
        if parsed_map:
            chapter_id_map_override = parsed_map

    # 兜底：按章节数判断
    chapter_count = len(re.findall(r'^##\s+第\d+章', content, re.MULTILINE))
    if chapter_count <= 7 and mode != 'lite':
        mode = 'lite'

    return mode, requirement_type, chapter_id_map_override


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


def check_id_consistency(content, lines, skip_prefixes=None, lenient_unreferenced=False,
                         definition_chapters=None):
    """检查所有 ID 的定义与引用完整性。

    Args:
        skip_prefixes: 跳过检查的 ID 前缀集合（如 lite 模式跳过 IF/BR）
        lenient_unreferenced: 是否将"已定义未引用"降级为信息级别（update 模式下按需生成章节可能导致）
        definition_chapters: ID前缀→定义章节映射（用于建议文本），None 时使用硬编码默认值
    """
    if definition_chapters is None:
        definition_chapters = DEFINITION_CHAPTERS
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
                    'suggestion': f'在{definition_chapters.get(prefix, "对应章节")}中添加 {full_id} 的定义',
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


def _load_fuzzy_config():
    """Load fuzzy word config from YAML file, fallback to defaults."""
    config_path = os.path.join(os.path.dirname(__file__), 'fuzzy-config.yaml')
    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        return (
            [(p['word'], p['suggestion']) for p in cfg.get('fuzzy_patterns', [])],
            [(p['word'], p['suggestion']) for p in cfg.get('redundancy_patterns', [])],
            [(p['word'], p['suggestion']) for p in cfg.get('filler_patterns', [])],
            cfg.get('exclusions', {}),
        )
    except Exception:
        # Fallback: hardcoded defaults
        return (
            [('大概', '请给出具体数值'), ('可能', '请明确是否会发生'), ('一般', '请明确具体条件'),
             ('适当', '请量化标准'), ('合理', '请量化标准'), ('及时', '请给出时间要求'),
             ('灵活', '请明确具体规则'), ('可配置', '请说明配置项、默认值和配置入口')],
            [('进行', '删除"进行"，直接用动词'), ('相关的', '删除"相关的"或明确具体对象'),
             ('一定程度上', '删除或量化程度'), ('基本上', '删除"基本上"或说明例外'),
             ('总体来说', '删除"总体来说"'), ('需要注意的是', '删除，直接陈述'),
             ('众所周知', '删除'), ('不言而喻', '删除，明确说明')],
            [('本章是', '删除填充句'), ('以下将详细描述', '删除填充句，直接描述'),
             ('以下将逐一说明', '删除填充句，直接说明'), ('下面我们来看', '删除填充句')],
            {'及时': ['及时性', '及时率'], '一般': ['一般纳税人', '一般贸易', '一般计税'],
             '可能': ['可能性', '不可能'], '合理': ['合理性'],
             '进行': ['进行中', '进行时'], '相关的': ['相关的系统', '相关的接口']},
        )


def check_fuzzy_words(content):
    """检查模糊用语。"""
    issues = []
    fuzzy_patterns, redundancy_patterns, filler_patterns, exclusions = _load_fuzzy_config()

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


def check_narrative_signals(content, lines, mode, requirement_type):
    """检查叙事信号：已有内容的内在比例和连接，不检查章节存在性。"""
    issues = []

    # --- 信号1: 目标-功能悬空 ---
    # G-XX 被定义但未在任何 F-XXX 段落中被引用
    g_ids = extract_ids(content, 'G')
    f_sections = []
    current_section = ''
    for line in lines:
        if re.match(r'^#{2,4}\s+.*F-\d{3}', line):
            if current_section:
                f_sections.append(current_section)
            current_section = line
        elif current_section:
            current_section += '\n' + line
    if current_section:
        f_sections.append(current_section)
    f_text = '\n'.join(f_sections)

    for g_num in sorted(g_ids):
        g_full = f'G-{g_num}'
        if g_full not in f_text:
            issues.append({
                'severity': '警告',
                'type': '叙事信号',
                'message': f'{g_full} 定义了目标但 PRD 功能章节中无实现路径',
                'suggestion': f'确认 {g_full} 是否有对应的 F-XXX 功能实现',
            })

    # --- 信号2: 背景空心 ---
    # §2 存在但不含任何数字（决策者可能无法判断紧迫性）
    ch2_text = ''
    in_ch2 = False
    for line in lines:
        if re.match(r'^##\s+第?2[章.\s]', line):
            in_ch2 = True
            continue
        elif re.match(r'^##\s+第?\d+[章.\s]', line) and in_ch2:
            break
        elif in_ch2:
            ch2_text += line + '\n'

    if ch2_text and not re.search(r'\d+[%％万亿元秒天条单笔次/]', ch2_text):
        issues.append({
            'severity': '信息',
            'type': '叙事信号',
            'message': '§2 需求概述缺少量化数据——决策者可能无法判断紧迫性',
            'suggestion': '考虑在背景描述中补充关键指标（数量、频率、金额、影响范围等）',
        })

    # --- 信号3: 验收覆盖率 ---
    f_ids = extract_ids(content, 'F')
    if f_ids and mode == 'full':
        # 定位 §9（验收标准章节）
        ch9_text = ''
        in_ch9 = False
        for line in lines:
            if re.match(r'^##\s+第?9[章.\s]', line):
                in_ch9 = True
                continue
            elif re.match(r'^##\s+第?\d+[章.\s]', line) and in_ch9:
                break
            elif in_ch9:
                ch9_text += line + '\n'

        if ch9_text:
            f_in_ch9 = set(ID_PATTERNS['F'].findall(ch9_text))
            coverage = len(f_in_ch9) / len(f_ids) * 100 if f_ids else 100
            if coverage < 70:
                issues.append({
                    'severity': '警告',
                    'type': '叙事信号',
                    'message': f'仅 {coverage:.0f}% 的功能点在验收标准中被引用'
                               f'（{len(f_in_ch9)}/{len(f_ids)}）',
                    'suggestion': '检查未覆盖的功能点是否需要验收标准',
                })

    # --- 信号4: 异常密度 ---
    exception_keywords = re.findall(r'异常|失败|超时|错误|回滚|降级|兜底', content)
    if f_ids and len(exception_keywords) < len(f_ids):
        issues.append({
            'severity': '信息',
            'type': '叙事信号',
            'message': f'异常处理描述密度偏低（{len(f_ids)}个功能点，'
                       f'仅{len(exception_keywords)}处异常相关描述）',
            'suggestion': '核查每个功能点是否都考虑了异常路径',
        })

    # --- 信号5: 变更点-验收对应（update/mixed）---
    if requirement_type in ('update', 'mixed'):
        c_ids = extract_ids(content, 'C')
        ch9_text_for_c = ''
        in_ch9_c = False
        for line in lines:
            if re.match(r'^##\s+第?(?:9|6)[章.\s]', line):  # lite 模式验收在 Ch.6
                in_ch9_c = True
                continue
            elif re.match(r'^##\s+第?\d+[章.\s]', line) and in_ch9_c:
                break
            elif in_ch9_c:
                ch9_text_for_c += line + '\n'

        for c_num in sorted(c_ids):
            c_full = f'C-{c_num}'
            if c_full not in ch9_text_for_c:
                issues.append({
                    'severity': '警告',
                    'type': '叙事信号',
                    'message': f'变更点 {c_full} 未出现在验收标准中',
                    'suggestion': f'确认 {c_full} 的变更是否有对应的验收场景',
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
    mode, requirement_type, chapter_id_map_override = detect_prd_mode(content)
    print(f"检测到 PRD 模式: {mode}, 需求类型: {requirement_type}")

    # 解析定义章节映射：front matter 自定义 > 模式默认值
    if chapter_id_map_override:
        # 以硬编码默认值为底，用 front matter 覆盖
        base = (DEFINITION_CHAPTERS_LITE if mode == 'lite' else DEFINITION_CHAPTERS).copy()
        base.update(chapter_id_map_override)
        definition_chapters = base
        print(f"使用自定义章节-ID映射: {chapter_id_map_override}")
    else:
        definition_chapters = DEFINITION_CHAPTERS_LITE if mode == 'lite' else DEFINITION_CHAPTERS

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
    all_issues.extend(check_id_consistency(content, lines, skip_prefixes, lenient_unreferenced,
                                           definition_chapters))
    all_issues.extend(check_fuzzy_words(content))
    if requirement_type in ('update', 'mixed'):
        all_issues.extend(check_change_coverage(content, lines))
    all_issues.extend(check_er_consistency(content, mode))
    all_issues.extend(check_narrative_signals(content, lines, mode, requirement_type))

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
