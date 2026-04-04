#!/usr/bin/env python3
"""
check-skill-consistency.py — Skill 定义文件自检工具

扫描 skill 目录下的所有定义文件（SKILL.md、references/、templates/），验证：
 1. 文件引用完整性（引用的文件是否存在）
 2. 模板 front matter 字段对齐
 3. 交互ID完整性
 4. 章节引用有效性（§X.X）
 5. 术语一致性（自动从 glossary.yaml 提取 + 手动规则）
 6. 横切概念覆盖（自动发现：出现在 SKILL.md + ≥2 模式文件中的概念）
 7. Gate ID 集成验证
 8. 脚本可执行冒烟测试（import / node --check）
 9. Reference 加载表 ↔ references/ 目录对齐
10. 发版就绪检测（git log 语义信号 + 文档新鲜度）
11. 数值断言同步（SKILL.md 中的章节数/维度数/CK范围 vs reference 实际）
12. 模板占位符完整性（templates/ 中的 {占位符} 是否在指引中有引用）
13. 脚本测试覆盖（scripts/*.py 是否在 tests/ 中有对应测试）

用法:
    python3 scripts/check-skill-consistency.py [skill目录]    # 完整报告
    python3 scripts/check-skill-consistency.py --short         # 一行摘要
    python3 scripts/check-skill-consistency.py --verbose       # 完整报告（默认）

依赖: 无（仅使用标准库）
兼容: Python 3.8+
"""

import re
import sys
import os
import glob
import subprocess
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

# 术语规范：手动维护的最小集（不易从文件中自动提取的语义等价对）
TERM_VARIANTS_MANUAL = {
    '变更范围声明': ['变更范围确认', '变更范围选择'],
    '按需生成章节': ['增量标记', '条件生成章节', '增量描述标记'],
    '系统公约': ['系统约定', '系统惯例'],
    '需求类型确认': ['需求分类确认'],
}

# 两种模式文件（用于横切概念自动发现）
MODE_FILES = [
    'references/autonomous-mode.md',
    'references/lite-mode.md',
]


# =============================================================================
# 工具函数
# =============================================================================

def find_skill_dir():
    """确定 skill 根目录（从当前目录推断）。"""
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


def _load_glossary_terms(skill_dir):
    """从 knowledge-base/glossary.yaml 提取术语规范（如存在）。

    返回 {canonical_cn_name: [term, full_name]} 的映射，
    用于检测同一概念的不同写法。
    """
    glossary_terms = {}
    # 搜索 glossary.yaml
    for candidate in [
        os.path.join(skill_dir, '..', 'knowledge-base', 'glossary.yaml'),
        os.path.join(skill_dir, 'knowledge-base', 'glossary.yaml'),
    ]:
        if os.path.isfile(candidate):
            try:
                with open(candidate, 'r', encoding='utf-8') as f:
                    content = f.read()
                # 简易提取 term / cn_name 对
                current_term = None
                current_cn = None
                for line in content.split('\n'):
                    s = line.strip()
                    if s.startswith('- term:'):
                        current_term = s.split(':', 1)[1].strip().strip('"\'')
                    elif s.startswith('cn_name:'):
                        current_cn = s.split(':', 1)[1].strip().strip('"\'')
                        if current_term and current_cn and current_term != current_cn:
                            glossary_terms[current_cn] = [current_term]
                        current_term = None
                        current_cn = None
            except Exception:
                pass
            break
    return glossary_terms


def check_term_consistency(files, skill_dir):
    """检查5: 术语一致性（手动规则 + glossary.yaml 自动提取）。"""
    issues = []

    # 合并手动规则和 glossary 提取
    all_variants = dict(TERM_VARIANTS_MANUAL)
    glossary_terms = _load_glossary_terms(skill_dir)
    # glossary 中的 cn_name → term 英文缩写，检测混用
    # 例如 glossary 定义了 cn_name="预到货通知", term="ASN"
    # 如果某文件用了 "ASN" 而同行没有 "预到货通知"，不算错——这是正常的
    # 但如果用了 "预到货单" 而 glossary 说是 "预到货通知"，就是偏差
    # 这类偏差需要更复杂的 NLP，暂不自动检测
    # → glossary 自动提取的主要价值：在 check 报告中列出 glossary 覆盖范围

    for filepath, content in files.items():
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if line.strip().startswith('<!--'):
                continue
            for canonical, variants in all_variants.items():
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
    """检查6: 横切概念覆盖完整性（自动发现）。

    策略：从 SKILL.md 中提取 **粗体** 定义的概念，
    如果它在 SKILL.md + ≥1 个模式文件中出现，则视为横切概念，
    检查是否在所有模式文件中都有提及。
    """
    issues = []

    skill_content = files.get('SKILL.md', '')
    if not skill_content:
        return issues

    # 提取 SKILL.md 中 **粗体** 定义的概念
    # 过滤条件：≥4 字中文或含英文标识符，排除通用词
    GENERIC_BOLD = {
        '注意', '重要', '说明', '核心', '禁止', '必须', '默认', '推荐',
        '原则', '时机', '目标', '产出', '规则', '条件', '格式', '策略',
        '产出文件', '触发条件', '默认行为', '设计方案',
    }
    bold_terms = set()
    for match in re.finditer(r'\*\*([^*]{4,30})\*\*', skill_content):
        term = match.group(1).strip()
        if term in GENERIC_BOLD:
            continue
        if re.match(r'^[\d.]+$', term):
            continue
        if re.match(r'^[.a-z]', term):  # 文件扩展名如 .drawio
            continue
        bold_terms.add(term)

    # 确定哪些是横切概念：在 SKILL.md 中定义且在 ≥1 个模式文件中也出现
    mode_file_contents = {}
    for mf in MODE_FILES:
        if mf in files:
            mode_file_contents[mf] = files[mf]

    if not mode_file_contents:
        return issues

    cross_cutting = []  # (concept, missing_in_files)
    for term in sorted(bold_terms):
        present_in = [mf for mf, content in mode_file_contents.items() if term in content]
        # 在 ≥2 模式文件中出现但不在全部 → 真正的横切概念遗漏
        if len(present_in) >= 2 and len(present_in) < len(mode_file_contents):
            missing = [mf for mf in mode_file_contents if mf not in present_in]
            cross_cutting.append((term, missing))

    for concept, missing_files in cross_cutting:
        for mf in missing_files:
            issues.append({
                'severity': '信息',
                'type': '横切概念',
                'message': f'概念 "{concept}" 在 SKILL.md 和其他模式文件中出现，但在 {mf} 中未提及',
                'suggestion': f'如 "{concept}" 适用于该模式，考虑补充说明',
            })

    return issues


def check_numeric_assertions(files):
    """检查11: SKILL.md 数值断言 vs reference 实际内容。

    SKILL.md 概述性地提及了数值（如"10章""9个维度""CK-0~CK-9"），
    如果 reference 中的实际内容变了而 SKILL.md 没同步，就会产生逻辑断裂。
    """
    issues = []
    skill = files.get('SKILL.md', '')
    if not skill:
        return issues

    # --- 断言1: PRD 章节数 ---
    # SKILL.md 声称"10章完整版"和"7章精简版"
    for tpl_name, expected_ch, mode_label in [
        ('templates/prd-template.md', 10, '完整版'),
        ('templates/lite-prd-template.md', 7, '轻量版'),
    ]:
        if tpl_name not in files:
            continue
        # 统计模板中的章节标题数
        actual_ch = len(re.findall(r'^##\s+第?\d+[章.]', files[tpl_name], re.MULTILINE))
        if actual_ch == 0:
            # 尝试 ## N. 格式
            actual_ch = len(re.findall(r'^##\s+\d+\.', files[tpl_name], re.MULTILINE))
        if actual_ch > 0 and actual_ch != expected_ch:
            issues.append({
                'severity': '警告',
                'type': '数值断裂',
                'message': f'SKILL.md 声称{mode_label} {expected_ch} 章，但 {tpl_name} 实际有 {actual_ch} 章',
                'suggestion': f'同步 SKILL.md 中的章节数描述，或修正模板',
            })

    # --- 断言2: CK 检查项范围 ---
    # SKILL.md 可能说"CK-0~CK-9"，检查 review-guide.md 中实际最大编号
    review = files.get('references/review-guide.md', '')
    if review:
        ck_nums = [int(m.group(1)) for m in re.finditer(r'\bCK-(\d{1,2})\b', review)
                   if not re.match(r'CK-L', m.group(0))]  # 排除 CK-L 系列
        if ck_nums:
            actual_max = max(ck_nums)
            # 从 SKILL.md 提取声称的 CK 范围
            ck_range = re.search(r'CK-0[~～]CK-(\d{1,2})', skill)
            if ck_range:
                claimed_max = int(ck_range.group(1))
                if actual_max != claimed_max:
                    issues.append({
                        'severity': '警告',
                        'type': '数值断裂',
                        'message': f'SKILL.md 声称 CK-0~CK-{claimed_max}，但 review-guide.md 实际最大为 CK-{actual_max}',
                        'suggestion': f'同步 SKILL.md 中的 CK 范围',
                    })

    # --- 断言3: (已移除 — 澄清维度数检查，phase2-clarify.md 已删除，9维度降级为 AI 内部框架) ---

    # --- 断言4: NP 检查项范围 ---
    write = files.get('references/writing-guide.md', '')
    if write:
        np_nums = [int(m.group(1)) for m in re.finditer(r'\bNP-(\d{2})\b', write)]
        if np_nums:
            actual_max_np = max(np_nums)
            np_range = re.search(r'NP-01[~～](?:NP-)?(\d{2})', skill)
            if np_range:
                claimed_max_np = int(np_range.group(1))
                if actual_max_np != claimed_max_np:
                    issues.append({
                        'severity': '信息',
                        'type': '数值断裂',
                        'message': f'SKILL.md 声称 NP-01~{claimed_max_np:02d}，但 writing-guide.md 实际最大为 NP-{actual_max_np:02d}',
                        'suggestion': f'同步引用中的 NP 范围',
                    })

    return issues


def check_template_placeholders(files):
    """检查12: 模板占位符完整性。

    扫描 templates/ 中的 {占位符}，检查是否在对应的 reference 指引中
    有填充说明。未被引用的占位符可能导致 AI 生成时留下未替换的内容。
    """
    issues = []

    # 占位符模式：{中文或英文，2-30字符}，排除代码块和 YAML 值
    placeholder_pattern = re.compile(r'\{([A-Za-z\u4e00-\u9fff][\w\u4e00-\u9fff /.-]{1,30})\}')
    # 已知的通用占位符（不需要单独填充说明）
    KNOWN_PLACEHOLDERS = {
        'YYYY-MM-DD', 'YYYY-MM', 'YYYY.MM.PATCH', 'date', 'name', 'version',
        'X', 'N', 'M', 'i', 'id', 'true', 'false',
    }

    # 收集所有 reference 文件的文本（用于搜索占位符是否被引用）
    all_refs_text = '\n'.join(
        content for path, content in files.items()
        if path.startswith('references/') or path == 'SKILL.md'
    )

    for tpl_path, tpl_content in files.items():
        if not tpl_path.startswith('templates/'):
            continue

        in_code_block = False
        for line_num, line in enumerate(tpl_content.split('\n'), 1):
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            for match in placeholder_pattern.finditer(line):
                ph = match.group(1)
                if ph in KNOWN_PLACEHOLDERS:
                    continue
                # 含中文的占位符是自描述的（如{痛点1}{量化目标}），AI 理解无障碍
                if re.search(r'[\u4e00-\u9fff]', ph):
                    continue
                # 含 / 的是枚举选项（如{HTTP POST / MQ / RPC}），也是自描述的
                if '/' in ph:
                    continue
                # 仅标记纯英文非通用占位符（可能是代码变量或缩写）
                if ph not in all_refs_text:
                    issues.append({
                        'severity': '信息',
                        'type': '占位符',
                        'message': f'{tpl_path} L{line_num}: 占位符 "{{{ph}}}" 未在任何指引文件中引用',
                        'suggestion': f'确认 AI 是否知道如何填充此占位符',
                    })

    return issues


def check_script_smoke(skill_dir):
    """检查8: 脚本可执行冒烟测试。

    对 scripts/*.py 尝试 import，对 *.mjs 尝试 node --check。
    捕捉重构后的语法错误和缺失依赖。
    """
    issues = []
    scripts_dir = os.path.join(skill_dir, 'scripts')
    if not os.path.isdir(scripts_dir):
        return issues

    for py_file in sorted(glob.glob(os.path.join(scripts_dir, '*.py'))):
        basename = os.path.basename(py_file)
        try:
            result = subprocess.run(
                [sys.executable, '-c', f'import sys; sys.path.insert(0, "{scripts_dir}"); exec(open("{py_file}").read().split("\\nif __name__")[0])'],
                capture_output=True, text=True, timeout=10,
                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
            )
            # 更轻量的方法：仅检查语法
            result = subprocess.run(
                [sys.executable, '-m', 'py_compile', py_file],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                issues.append({
                    'severity': '关键',
                    'type': '脚本语法',
                    'message': f'scripts/{basename}: Python 编译失败',
                    'suggestion': result.stderr.strip()[:200] if result.stderr else '检查语法错误',
                })
        except Exception as e:
            issues.append({
                'severity': '警告',
                'type': '脚本检查',
                'message': f'scripts/{basename}: 冒烟测试异常 — {e}',
                'suggestion': '手动运行脚本确认',
            })

    for mjs_file in sorted(glob.glob(os.path.join(scripts_dir, '*.mjs'))):
        basename = os.path.basename(mjs_file)
        try:
            import shutil
            node = shutil.which('node')
            if not node:
                continue  # Node 不可用时跳过
            result = subprocess.run(
                [node, '--check', mjs_file],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                issues.append({
                    'severity': '关键',
                    'type': '脚本语法',
                    'message': f'scripts/{basename}: Node.js 语法检查失败',
                    'suggestion': result.stderr.strip()[:200] if result.stderr else '检查语法错误',
                })
        except Exception:
            pass  # Node 不可用不阻断

    return issues


def check_loading_table(files, skill_dir):
    """检查9: Reference 加载表 ↔ references/ 目录对齐。

    SKILL.md 的加载表是 AI 知道何时读什么文件的唯一入口，
    遗漏 = 文件存在但 AI 不知道什么时候读。
    """
    issues = []
    skill_content = files.get('SKILL.md', '')
    if not skill_content:
        return issues

    # 从 "Reference 文件按需加载策略" 区块中提取文件名
    # 定位加载表区块（在"按需加载"和下一个 ### 之间）
    loading_section_start = skill_content.find('按需加载')
    if loading_section_start < 0:
        return issues  # 无加载表
    loading_section_end = skill_content.find('\n### ', loading_section_start + 1)
    if loading_section_end < 0:
        loading_section_end = skill_content.find('\n## ', loading_section_start + 1)
    loading_block = skill_content[loading_section_start:loading_section_end] if loading_section_end > 0 else skill_content[loading_section_start:]

    table_files = set()
    for match in re.finditer(r'\|\s*`([a-z][\w-]+\.md)`\s*\|', loading_block):
        table_files.add(match.group(1))

    # 实际 references/ 目录文件
    refs_dir = os.path.join(skill_dir, 'references')
    actual_files = set()
    if os.path.isdir(refs_dir):
        for f in os.listdir(refs_dir):
            if f.endswith('.md'):
                actual_files.add(f)

    # 在表中但不在目录
    for f in sorted(table_files - actual_files):
        issues.append({
            'severity': '关键',
            'type': '加载表',
            'message': f'SKILL.md 加载表引用 `{f}`，但 references/ 中不存在',
            'suggestion': f'创建 references/{f} 或从加载表移除',
        })

    # 在目录但不在表中
    for f in sorted(actual_files - table_files):
        issues.append({
            'severity': '警告',
            'type': '加载表',
            'message': f'references/{f} 存在但未出现在 SKILL.md 加载表中',
            'suggestion': f'AI 不知道何时读取此文件——在加载表中补充 `{f}` 的读取时机',
        })

    return issues


def check_test_coverage(skill_dir):
    """检查13: 脚本测试覆盖。

    每个 scripts/*.py 应在 tests/ 中有对应测试。
    不要求 1:1 文件名映射，只要脚本的模块名被 import 就算覆盖。
    """
    issues = []
    project_root = os.path.join(skill_dir, '..')
    tests_dir = os.path.join(project_root, 'tests')

    if not os.path.isdir(tests_dir):
        return issues

    # 收集所有测试文件中 import 的模块名
    tested_modules = set()
    for test_file in glob.glob(os.path.join(tests_dir, 'test_*.py')):
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
            # 匹配 import xxx / from xxx import / importlib.import_module('xxx')
            for m in re.finditer(r"(?:import|from)\s+([\w.-]+)", content):
                tested_modules.add(m.group(1).replace('-', '_').replace('.', '_'))
            for m in re.finditer(r"import_module\(['\"]([^'\"]+)", content):
                tested_modules.add(m.group(1).replace('-', '_').replace('.', '_'))
        except Exception:
            pass

    # 检查每个脚本是否被测试覆盖
    scripts_dirs = [
        os.path.join(skill_dir, 'scripts'),
        os.path.join(project_root, 'scm-knowledge-curator', 'scripts'),
    ]
    # 排除：自身（check-skill-consistency）和纯配置文件
    skip_scripts = {'check_skill_consistency', '__init__'}

    for scripts_dir in scripts_dirs:
        if not os.path.isdir(scripts_dir):
            continue
        for py_file in sorted(glob.glob(os.path.join(scripts_dir, '*.py'))):
            basename = os.path.basename(py_file)
            module_name = basename.replace('.py', '').replace('-', '_')
            if module_name in skip_scripts:
                continue
            if module_name not in tested_modules:
                rel_path = os.path.relpath(py_file, project_root)
                issues.append({
                    'severity': '信息',
                    'type': '测试覆盖',
                    'message': f'{rel_path} 无测试覆盖',
                    'suggestion': f'在 tests/ 中添加 test_{module_name}.py',
                })

    # 检查测试文件是否为空壳（至少有 1 个 def test_ 函数）
    for test_file in glob.glob(os.path.join(tests_dir, 'test_*.py')):
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
            test_funcs = re.findall(r'def test_\w+', content)
            if not test_funcs:
                issues.append({
                    'severity': '警告',
                    'type': '测试空壳',
                    'message': f'{os.path.basename(test_file)} 没有任何 test_ 函数 — 测试文件是空壳',
                    'suggestion': '添加至少一个 def test_xxx() 测试函数',
                })
        except Exception:
            pass

    return issues


def check_release_readiness(skill_dir):
    """检查10: 发版就绪检测。

    基于 git log 语义信号判断是否应该发版，发版时附带文档新鲜度检查。
    替代原 check_doc_freshness — 文档新鲜度作为发版检查的子逻辑。
    """
    issues = []
    project_root = os.path.join(skill_dir, '..')

    # --- 读取 git 状态 ---
    try:
        # 最新 tag
        latest_tag = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0'],
            capture_output=True, text=True, timeout=5,
            cwd=project_root,
        )
        if latest_tag.returncode != 0:
            return issues  # 无 tag 历史，跳过
        tag = latest_tag.stdout.strip()

        # 自上次 tag 以来的 commits（conventional commit type 分组）
        log_result = subprocess.run(
            ['git', 'log', f'{tag}..HEAD', '--oneline', '--format=%s'],
            capture_output=True, text=True, timeout=5,
            cwd=project_root,
        )
        if log_result.returncode != 0:
            return issues
        commits = [line.strip() for line in log_result.stdout.strip().split('\n') if line.strip()]

        if not commits:
            return issues  # tag 就是最新，无未发布变更

        # 分类 commits
        feat_commits = [c for c in commits if c.startswith('feat:') or c.startswith('feat(')]
        fix_commits = [c for c in commits if c.startswith('fix:') or c.startswith('fix(')]
        refactor_commits = [c for c in commits if c.startswith('refactor:')]

        # SKILL.md 是否有变更
        skill_changed = subprocess.run(
            ['git', 'diff', '--name-only', f'{tag}..HEAD', '--', '*/SKILL.md'],
            capture_output=True, text=True, timeout=5,
            cwd=project_root,
        )
        skill_md_changed = bool(skill_changed.stdout.strip())

        # 自上次 tag 的天数
        tag_date = subprocess.run(
            ['git', 'log', '-1', '--format=%ct', tag],
            capture_output=True, text=True, timeout=5,
            cwd=project_root,
        )
        import datetime
        days_since_tag = 0
        if tag_date.returncode == 0 and tag_date.stdout.strip():
            tag_ts = int(tag_date.stdout.strip())
            days_since_tag = (datetime.datetime.now().timestamp() - tag_ts) / 86400

    except (FileNotFoundError, subprocess.TimeoutExpired):
        return issues  # git 不可用，跳过

    # --- 发版信号判断 ---
    reasons = []

    if len(feat_commits) >= 3:
        reasons.append(f'{len(feat_commits)} 个新功能')
    if skill_md_changed and feat_commits:
        reasons.append('SKILL.md 行为已变化')
    if days_since_tag >= 7 and (feat_commits or fix_commits):
        reasons.append(f'已 {int(days_since_tag)} 天未发版')

    if reasons:
        summary = '、'.join(reasons)
        commit_breakdown = []
        if feat_commits:
            commit_breakdown.append(f'{len(feat_commits)} feat')
        if fix_commits:
            commit_breakdown.append(f'{len(fix_commits)} fix')
        if refactor_commits:
            commit_breakdown.append(f'{len(refactor_commits)} refactor')
        breakdown = ', '.join(commit_breakdown)

        issues.append({
            'severity': '警告',
            'type': '建议发版',
            'message': f'自 {tag} 以来有 {len(commits)} 个未发布 commit（{breakdown}）— {summary}',
            'suggestion': f'考虑发版。发版前同步更新 CHANGELOG + README + CONTRIBUTING + CLAUDE.md',
        })

        # 子检查：文档是否比最新 tag 更旧
        docs_to_check = [
            ('README.md', '项目介绍'),
            ('CONTRIBUTING.md', '维护者导引'),
            ('CLAUDE.md', 'AI 项目指引'),
            ('CHANGELOG.md', '版本记录'),
        ]
        stale_docs = []
        for doc_name, desc in docs_to_check:
            doc_path = os.path.join(project_root, doc_name)
            if os.path.isfile(doc_path):
                doc_mtime = os.path.getmtime(doc_path)
                if tag_date.returncode == 0 and tag_date.stdout.strip():
                    if doc_mtime < tag_ts:
                        stale_docs.append(doc_name)

        if stale_docs:
            issues.append({
                'severity': '信息',
                'type': '发版文档',
                'message': f'发版前需更新: {", ".join(stale_docs)}',
                'suggestion': '这些文档在上次发版后未更新，发版时应同步',
            })

        # 子检查：测试是否全部通过
        tests_dir = os.path.join(project_root, 'tests')
        if os.path.isdir(tests_dir):
            try:
                test_result = subprocess.run(
                    [sys.executable, '-m', 'pytest', tests_dir, '-q', '--tb=no'],
                    capture_output=True, text=True, timeout=30,
                    cwd=project_root,
                )
                last_line = test_result.stdout.strip().split('\n')[-1] if test_result.stdout.strip() else ''
                if test_result.returncode != 0:
                    issues.append({
                        'severity': '警告',
                        'type': '发版测试',
                        'message': f'测试未通过 — {last_line}',
                        'suggestion': '发版前必须所有测试通过: python -m pytest tests/ -v',
                    })
                else:
                    issues.append({
                        'severity': '信息',
                        'type': '发版测试',
                        'message': f'测试通过 — {last_line}',
                        'suggestion': '',
                    })
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass  # pytest 不可用，跳过

    return issues


# =============================================================================
# 主函数
# =============================================================================

def main():
    # 解析参数
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    flags = [a for a in sys.argv[1:] if a.startswith('-')]
    short_mode = '--short' in flags
    # --verbose 是默认行为（向后兼容），不需要特殊处理

    skill_dir = find_skill_dir() if not args else args[0]
    if not os.path.isfile(os.path.join(skill_dir, 'SKILL.md')):
        if os.path.isfile('SKILL.md'):
            skill_dir = '.'
        else:
            print("错误: 找不到 SKILL.md。", file=sys.stderr)
            sys.exit(1)

    files = read_all_md_files(skill_dir)

    if not short_mode:
        print(f"检测到 skill 文件: {len(files)} 个")
        print()

    all_issues = []
    all_issues.extend(check_file_references(files, skill_dir))
    all_issues.extend(check_front_matter_fields(files))
    all_issues.extend(check_interaction_ids(files))
    all_issues.extend(check_section_references(files))
    all_issues.extend(check_term_consistency(files, skill_dir))
    all_issues.extend(check_mode_coverage(files))
    all_issues.extend(check_gate_id_integration(files))
    all_issues.extend(check_numeric_assertions(files))
    all_issues.extend(check_template_placeholders(files))
    all_issues.extend(check_script_smoke(skill_dir))
    all_issues.extend(check_loading_table(files, skill_dir))
    all_issues.extend(check_test_coverage(skill_dir))
    all_issues.extend(check_release_readiness(skill_dir))

    critical = [i for i in all_issues if i['severity'] == '关键']
    warnings = [i for i in all_issues if i['severity'] == '警告']
    infos = [i for i in all_issues if i['severity'] == '信息']

    # Short mode: 一行摘要
    if short_mode:
        parts = []
        if critical:
            parts.append(f"{len(critical)} critical")
        if warnings:
            parts.append(f"{len(warnings)} warnings")
        if infos:
            parts.append(f"{len(infos)} info")
        # 附加发版提醒
        release_issues = [i for i in all_issues if i['type'] == '建议发版']
        release_hint = f" | {release_issues[0]['message']}" if release_issues else ""
        summary = ', '.join(parts) if parts else "all clear"
        print(f"skill-check: {summary}{release_hint}")
        sys.exit(1 if critical else 0)

    # Verbose mode: 完整报告
    if not all_issues:
        print("✓ Skill 自检通过，未发现问题")
        sys.exit(0)

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
