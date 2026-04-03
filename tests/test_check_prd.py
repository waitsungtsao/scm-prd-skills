"""
test_check_prd.py — Tests for check-prd-consistency.py PRD validation.

Covers: detect_prd_mode(), check_id_consistency(), check_fuzzy_words(), lite mode detection.
"""

import os
import importlib
import pytest

# Module has hyphens in its name, so use importlib
check_prd = importlib.import_module('check-prd-consistency')

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


def _read_fixture(name):
    path = os.path.join(FIXTURES, name)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


# ---------------------------------------------------------------------------
# detect_prd_mode()
# ---------------------------------------------------------------------------

class TestDetectPrdMode:
    """Tests for PRD mode and requirement type detection."""

    def test_full_mode_detected(self):
        content = _read_fixture('prd_clean.md')
        mode, req_type, *_ = check_prd.detect_prd_mode(content)
        assert mode == 'full'
        assert req_type == 'new'

    def test_lite_mode_from_frontmatter(self):
        content = _read_fixture('prd_lite.md')
        mode, req_type, *_ = check_prd.detect_prd_mode(content)
        assert mode == 'lite'
        assert req_type == 'update'

    def test_lite_mode_by_chapter_count(self):
        """A PRD with <=7 chapters but no mode: lite in front matter should still be detected as lite."""
        content = "---\nrequirement_type: new\n---\n"
        for i in range(1, 7):
            content += f"\n## 第{i}章 Title\n\nContent.\n"
        mode, *_ = check_prd.detect_prd_mode(content)
        assert mode == 'lite'


# ---------------------------------------------------------------------------
# Clean PRD — no issues
# ---------------------------------------------------------------------------

class TestCleanPrd:
    """A well-formed PRD should produce no critical issues."""

    def test_no_critical_issues(self):
        content = _read_fixture('prd_clean.md')
        lines = content.split('\n')
        mode, req_type, *_ = check_prd.detect_prd_mode(content)

        issues = check_prd.check_id_consistency(content, lines, skip_prefixes={'C'})
        critical = [i for i in issues if i['severity'] == '关键']
        assert critical == [], f"Expected no critical issues, got: {critical}"


# ---------------------------------------------------------------------------
# Undefined ID references
# ---------------------------------------------------------------------------

class TestUndefinedRefs:
    """A PRD referencing undefined IDs should flag them."""

    def test_detects_undefined_f_id(self):
        content = _read_fixture('prd_undefined_refs.md')
        lines = content.split('\n')
        issues = check_prd.check_id_consistency(content, lines, skip_prefixes={'C'})
        # F-099 is referenced in Ch.5 but never defined
        undefined = [i for i in issues
                     if i['severity'] == '关键' and 'F-099' in i['message']]
        assert len(undefined) >= 1, f"Expected F-099 to be flagged, issues: {issues}"

    def test_detects_undefined_g_id(self):
        content = _read_fixture('prd_undefined_refs.md')
        lines = content.split('\n')
        issues = check_prd.check_id_consistency(content, lines, skip_prefixes={'C'})
        undefined = [i for i in issues
                     if i['severity'] == '关键' and 'G-05' in i['message']]
        assert len(undefined) >= 1, f"Expected G-05 to be flagged, issues: {issues}"

    def test_detects_undefined_if_id(self):
        content = _read_fixture('prd_undefined_refs.md')
        lines = content.split('\n')
        issues = check_prd.check_id_consistency(content, lines)
        undefined = [i for i in issues
                     if i['severity'] == '关键' and 'IF-999' in i['message']]
        assert len(undefined) >= 1, f"Expected IF-999 to be flagged, issues: {issues}"


# ---------------------------------------------------------------------------
# Fuzzy language detection
# ---------------------------------------------------------------------------

class TestFuzzyWords:
    """check_fuzzy_words() should flag ambiguous/vague terms."""

    def test_detects_fuzzy_words(self):
        content = _read_fixture('prd_fuzzy.md')
        issues = check_prd.check_fuzzy_words(content)
        found_words = {i['message'].split('"')[1] for i in issues
                       if i['type'] in ('模糊用语', '冗余用语')}
        assert '灵活' in found_words, f"Expected '灵活' to be flagged, found: {found_words}"
        assert '可配置' in found_words, f"Expected '可配置' to be flagged, found: {found_words}"

    def test_detects_timely_fuzzy(self):
        content = _read_fixture('prd_fuzzy.md')
        issues = check_prd.check_fuzzy_words(content)
        found_words = {i['message'].split('"')[1] for i in issues
                       if i['type'] == '模糊用语'}
        assert '及时' in found_words, f"Expected '及时' to be flagged, found: {found_words}"

    def test_clean_prd_minimal_fuzzy(self):
        content = _read_fixture('prd_clean.md')
        issues = check_prd.check_fuzzy_words(content)
        fuzzy_issues = [i for i in issues if i['type'] == '模糊用语']
        assert len(fuzzy_issues) == 0, f"Clean PRD should have no fuzzy issues, got: {fuzzy_issues}"


# ---------------------------------------------------------------------------
# Lite mode relaxed checks
# ---------------------------------------------------------------------------

class TestLiteMode:
    """Lite mode PRDs should skip IF/C checks."""

    def test_lite_skips_c_and_if(self):
        content = _read_fixture('prd_lite.md')
        lines = content.split('\n')
        mode, *_ = check_prd.detect_prd_mode(content)
        assert mode == 'lite'

        # With lite skip_prefixes, no errors about C or IF
        issues = check_prd.check_id_consistency(
            content, lines, skip_prefixes={'C', 'IF'})
        c_or_if_issues = [i for i in issues
                          if 'C-' in i['message'] or 'IF-' in i['message']]
        assert c_or_if_issues == [], \
            f"Lite mode should not flag C/IF issues, got: {c_or_if_issues}"


# ---------------------------------------------------------------------------
# Narrative signal checks
# ---------------------------------------------------------------------------

class TestNarrativeSignals:
    """Tests for narrative signal detection."""

    def test_goal_without_function_link(self):
        """G-XX defined but never referenced in F-XXX sections."""
        content = """---
requirement_type: new
---
## 第2章 需求概述

### G-01 提升退货效率
### G-02 降低错发率

## 第5章 业务流程

参见 F-001 和 G-01。

## 第6章 功能与规则

### F-001 退货申请
关联目标：G-01
"""
        lines = content.split('\n')
        issues = check_prd.check_narrative_signals(content, lines, 'full', 'new')
        # G-02 is defined but never appears in any F-XXX section
        g02_issues = [i for i in issues if 'G-02' in i['message'] and '叙事信号' in i['type']]
        assert len(g02_issues) >= 1, f"Expected G-02 flagged, got: {issues}"

    def test_background_without_numbers(self):
        """§2 exists but has no quantitative data."""
        content = """---
requirement_type: new
---
## 第2章 需求概述

当前退货流程不够高效，用户体验较差，需要优化。

## 第3章 术语
"""
        lines = content.split('\n')
        issues = check_prd.check_narrative_signals(content, lines, 'full', 'new')
        bg_issues = [i for i in issues if '量化数据' in i['message']]
        assert len(bg_issues) >= 1

    def test_background_with_numbers_no_warning(self):
        """§2 with quantitative data should not trigger."""
        content = """---
requirement_type: new
---
## 第2章 需求概述

当前日均退货量约500单，处理时效平均3天，退货率约8%。

## 第3章 术语
"""
        lines = content.split('\n')
        issues = check_prd.check_narrative_signals(content, lines, 'full', 'new')
        bg_issues = [i for i in issues if '量化数据' in i['message']]
        assert len(bg_issues) == 0

    def test_low_acceptance_coverage(self):
        """Less than 70% of F-XXX referenced in §9."""
        content = """---
requirement_type: new
---
## 第2章 需求概述

G-01 目标

## 第6章 功能与规则

### F-001 功能A
### F-002 功能B
### F-003 功能C
### F-004 功能D

## 第9章 验收标准

| 场景 | F-001 |
"""
        lines = content.split('\n')
        issues = check_prd.check_narrative_signals(content, lines, 'full', 'new')
        coverage_issues = [i for i in issues if '验收标准' in i['message'] and '功能点' in i['message']]
        assert len(coverage_issues) >= 1
