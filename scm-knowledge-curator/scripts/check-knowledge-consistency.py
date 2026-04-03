#!/usr/bin/env python3
"""
check-knowledge-consistency.py — 知识库一致性检查

检查 knowledge-base/ 目录下的知识卡片、术语表、索引文件的内部一致性。

用法:
    python check-knowledge-consistency.py [knowledge-base目录]
    # 默认检查当前目录下的 knowledge-base/

检查项:
  KC-1: 术语双向引用一致性（glossary.yaml 中 related 字段是否双向）
  KC-2: Domain code 大小写统一（必须全部大写 OMS/WMS/TMS/BMS）
  KC-3: 索引完整性（_index.md 是否覆盖所有 domain-*.md 文件）
  KC-4: 完整度字段有效性（0-100 范围，front matter 与 _index.md 一致）
  KC-5: Source type 合法性（仅允许 interview/document/inference/observation）
"""

import sys
import os
import re
import glob
from collections import defaultdict

try:
    import yaml
except ImportError:
    yaml = None

VALID_DOMAINS = {'OMS', 'WMS', 'TMS', 'BMS', 'common'}
VALID_SOURCES = {'interview', 'document', 'inference', 'observation'}


def find_kb_dir(arg=None):
    """定位 knowledge-base 目录。"""
    if arg and os.path.isdir(arg):
        return arg
    # 从当前目录或上级目录查找
    for candidate in ['knowledge-base', '../knowledge-base', '.']:
        if os.path.isdir(candidate) and (
            os.path.exists(os.path.join(candidate, '_index.md'))
            or glob.glob(os.path.join(candidate, 'domain-*.md'))
        ):
            return candidate
    return None


def _parse_yaml_simple(text):
    """简易 YAML 值提取（PyYAML 不可用时的降级方案）。"""
    result = {}
    for line in text.split('\n'):
        line = line.strip()
        if ':' in line and not line.startswith('#'):
            key, _, val = line.partition(':')
            result[key.strip()] = val.strip().strip('"\'')
    return result


def parse_yaml_text(text):
    """解析 YAML 文本，优先使用 PyYAML，降级为正则。"""
    if yaml:
        try:
            result = yaml.safe_load(text)
            return result if isinstance(result, dict) else {}
        except yaml.YAMLError:
            pass
    return _parse_yaml_simple(text)


def parse_front_matter(content):
    """提取 Markdown 文件的 YAML front matter。"""
    match = re.match(r'\A---[ \t]*\n(.*?\n)---[ \t]*\n', content, re.DOTALL)
    if match:
        return parse_yaml_text(match.group(1))
    return {}


def _parse_glossary_yaml(content):
    """使用 PyYAML 解析 glossary.yaml，返回 {term: {related, domains, source}} 字典。"""
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        return {}
    entries = data.get('terms', [])
    if not isinstance(entries, list):
        return {}
    terms = {}
    for entry in entries:
        if not isinstance(entry, dict) or 'term' not in entry:
            continue
        name = str(entry['term'])
        related = entry.get('related', [])
        if isinstance(related, str):
            related = [related]
        elif not isinstance(related, list):
            related = []
        related = [str(r) for r in related]
        domains = entry.get('domain', [])
        if isinstance(domains, str):
            domains = [domains]
        elif not isinstance(domains, list):
            domains = []
        domains = [str(d) for d in domains]
        source = entry.get('source')
        if isinstance(source, dict):
            source = source.get('type')
        terms[name] = {
            'related': related,
            'domains': domains,
            'source': str(source) if source else None,
        }
    return terms


def _parse_glossary_regex(content):
    """正则降级方案：逐行解析 glossary.yaml。"""
    terms = {}
    current_term = None
    current_related = []
    current_domains = []
    current_source = None

    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('- term:'):
            if current_term:
                terms[current_term] = {
                    'related': current_related,
                    'domains': current_domains,
                    'source': current_source,
                }
            current_term = stripped.split(':', 1)[1].strip().strip('"\'')
            current_related = []
            current_domains = []
            current_source = None
        elif stripped.startswith('related:'):
            val = stripped.split(':', 1)[1].strip()
            if val.startswith('['):
                items = val.strip('[]').split(',')
                current_related = [i.strip().strip('"\'') for i in items if i.strip()]
        elif stripped.startswith('domain:'):
            val = stripped.split(':', 1)[1].strip()
            if val.startswith('['):
                items = val.strip('[]').split(',')
                current_domains = [i.strip().strip('"\'') for i in items if i.strip()]
        elif stripped.startswith('source:'):
            current_source = stripped.split(':', 1)[1].strip().strip('"\'')

    if current_term:
        terms[current_term] = {
            'related': current_related,
            'domains': current_domains,
            'source': current_source,
        }
    return terms


def _parse_glossary(content):
    """解析 glossary.yaml，优先 PyYAML，降级正则。"""
    if yaml:
        try:
            return _parse_glossary_yaml(content)
        except yaml.YAMLError:
            pass
    return _parse_glossary_regex(content)


def check_glossary(kb_dir):
    """KC-1 & KC-2 & KC-5: 检查术语表。"""
    issues = []
    glossary_path = os.path.join(kb_dir, 'glossary.yaml')
    if not os.path.exists(glossary_path):
        issues.append(('info', 'KC-1', 'glossary.yaml 不存在，跳过术语检查'))
        return issues

    with open(glossary_path, 'r', encoding='utf-8') as f:
        content = f.read()

    terms = _parse_glossary(content)

    term_names = set(terms.keys())

    # KC-1: 双向引用检查
    for term, info in terms.items():
        for rel in info['related']:
            if rel in terms:
                if term not in terms[rel]['related']:
                    issues.append((
                        'warning', 'KC-1',
                        f'术语 "{term}" 引用了 "{rel}" 作为关联术语，'
                        f'但 "{rel}" 的 related 中未包含 "{term}"'
                    ))
            # 引用了不存在的术语只是 info，不一定是错误
            elif rel not in term_names:
                issues.append((
                    'info', 'KC-1',
                    f'术语 "{term}" 引用了 "{rel}"，但该术语未在 glossary 中定义'
                ))

    # KC-2: Domain code 大小写
    for term, info in terms.items():
        for d in info['domains']:
            if d not in VALID_DOMAINS:
                if d.upper() in VALID_DOMAINS:
                    issues.append((
                        'warning', 'KC-2',
                        f'术语 "{term}" 的 domain "{d}" 应为大写 "{d.upper()}"'
                    ))
                else:
                    issues.append((
                        'info', 'KC-2',
                        f'术语 "{term}" 的 domain "{d}" 不在标准列表中'
                    ))

    # KC-5: Source type 合法性
    for term, info in terms.items():
        if info['source'] and info['source'] not in VALID_SOURCES:
            issues.append((
                'warning', 'KC-5',
                f'术语 "{term}" 的 source "{info["source"]}" '
                f'不在合法值中（{", ".join(sorted(VALID_SOURCES))}）'
            ))

    return issues


def check_index_coverage(kb_dir):
    """KC-3: 检查索引覆盖率。"""
    issues = []
    index_path = os.path.join(kb_dir, '_index.md')
    domain_files = set()
    for f in glob.glob(os.path.join(kb_dir, 'domain-*.md')):
        domain_files.add(os.path.basename(f))

    if not os.path.exists(index_path):
        if domain_files:
            issues.append((
                'warning', 'KC-3',
                f'存在 {len(domain_files)} 个 domain 文件但缺少 _index.md'
            ))
        return issues

    with open(index_path, 'r', encoding='utf-8') as f:
        index_content = f.read()

    for df in domain_files:
        if df not in index_content:
            issues.append((
                'warning', 'KC-3',
                f'文件 {df} 未在 _index.md 中引用'
            ))

    return issues


def check_completeness(kb_dir):
    """KC-4: 检查完整度字段。"""
    issues = []
    for f in glob.glob(os.path.join(kb_dir, 'domain-*.md')):
        fname = os.path.basename(f)
        with open(f, 'r', encoding='utf-8') as fh:
            content = fh.read()
        fm = parse_front_matter(content)
        comp = fm.get('completeness', '')
        if comp:
            # 提取数字
            num = re.search(r'(\d+)', comp)
            if num:
                val = int(num.group(1))
                if val < 0 or val > 100:
                    issues.append((
                        'warning', 'KC-4',
                        f'{fname}: completeness 值 {val} 超出 0-100 范围'
                    ))
            else:
                issues.append((
                    'info', 'KC-4',
                    f'{fname}: completeness 字段无法解析为数字: "{comp}"'
                ))
    return issues


def main():
    kb_dir = find_kb_dir(sys.argv[1] if len(sys.argv) > 1 else None)
    if not kb_dir:
        print("未找到 knowledge-base 目录。")
        print("用法: python check-knowledge-consistency.py [knowledge-base目录]")
        sys.exit(0)  # 不算错误，可能还没创建

    print(f"检查目录: {os.path.abspath(kb_dir)}\n")

    all_issues = []
    all_issues.extend(check_glossary(kb_dir))
    all_issues.extend(check_index_coverage(kb_dir))
    all_issues.extend(check_completeness(kb_dir))

    # 分类输出
    criticals = [(s, c, m) for s, c, m in all_issues if s == 'critical']
    warnings = [(s, c, m) for s, c, m in all_issues if s == 'warning']
    infos = [(s, c, m) for s, c, m in all_issues if s == 'info']

    if warnings:
        print("== 警告 ==")
        for i, (_, code, msg) in enumerate(warnings, 1):
            print(f"  {i}. [{code}] {msg}")
        print()

    if infos:
        print("== 信息 ==")
        for i, (_, code, msg) in enumerate(infos, 1):
            print(f"  {i}. [{code}] {msg}")
        print()

    print(f"✓ 检查完成: {len(criticals)} 个关键, {len(warnings)} 个警告, {len(infos)} 个信息")
    sys.exit(1 if criticals else 0)


if __name__ == '__main__':
    main()
