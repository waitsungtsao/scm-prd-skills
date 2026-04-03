"""
test_check_knowledge.py — Tests for check-knowledge-consistency.py.

Covers: KC-1 (asymmetric related), KC-2 (lowercase domain), KC-3 (missing index),
        KC-4 (invalid completeness), KC-5 (invalid source type).
"""

import os
import importlib
import pytest

check_kc = importlib.import_module('check-knowledge-consistency')

KB_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'kb')


# ---------------------------------------------------------------------------
# KC-1: Glossary asymmetric related references
# ---------------------------------------------------------------------------

class TestKC1AsymmetricRelated:
    """KC-1: If term A lists B in related, then B should list A."""

    def test_detects_asymmetric_reference(self):
        """SKU lists '库存单元' as related, but '库存单元' does not list 'SKU' back."""
        issues = check_kc.check_glossary(KB_DIR)
        kc1_warnings = [(s, c, m) for s, c, m in issues
                        if c == 'KC-1' and s == 'warning']
        # SKU -> 库存单元 is asymmetric
        asymmetric = [m for _, _, m in kc1_warnings if 'SKU' in m and '库存单元' in m]
        assert len(asymmetric) >= 1, \
            f"Expected asymmetric reference warning for SKU/库存单元, got: {kc1_warnings}"

    def test_symmetric_pair_no_warning(self):
        """拣货 <-> 波次 are symmetric, should not produce a KC-1 warning."""
        issues = check_kc.check_glossary(KB_DIR)
        kc1_warnings = [(s, c, m) for s, c, m in issues
                        if c == 'KC-1' and s == 'warning']
        picking_wave = [m for _, _, m in kc1_warnings
                        if '拣货' in m and '波次' in m]
        assert len(picking_wave) == 0, \
            f"Symmetric pair should not be flagged, got: {picking_wave}"


# ---------------------------------------------------------------------------
# KC-2: Lowercase domain codes
# ---------------------------------------------------------------------------

class TestKC2DomainCase:
    """KC-2: Domain codes like 'wms' should be uppercase 'WMS'."""

    def test_detects_lowercase_domain(self):
        issues = check_kc.check_glossary(KB_DIR)
        kc2_warnings = [(s, c, m) for s, c, m in issues
                        if c == 'KC-2' and s == 'warning']
        lowercase_hits = [m for _, _, m in kc2_warnings if 'wms' in m]
        assert len(lowercase_hits) >= 1, \
            f"Expected lowercase domain warning for 'wms', got: {kc2_warnings}"


# ---------------------------------------------------------------------------
# KC-3: Missing files in index
# ---------------------------------------------------------------------------

class TestKC3IndexCoverage:
    """KC-3: domain-*.md files not listed in _index.md should be warned."""

    def test_detects_missing_file_in_index(self):
        issues = check_kc.check_index_coverage(KB_DIR)
        kc3_warnings = [(s, c, m) for s, c, m in issues
                        if c == 'KC-3' and s == 'warning']
        # domain-wms-packing.md exists but is not in _index.md
        missing = [m for _, _, m in kc3_warnings if 'domain-wms-packing.md' in m]
        assert len(missing) >= 1, \
            f"Expected missing index warning for domain-wms-packing.md, got: {kc3_warnings}"

    def test_listed_file_not_warned(self):
        issues = check_kc.check_index_coverage(KB_DIR)
        kc3_warnings = [(s, c, m) for s, c, m in issues
                        if c == 'KC-3' and s == 'warning']
        # domain-wms-picking.md IS in _index.md
        found = [m for _, _, m in kc3_warnings if 'domain-wms-picking.md' in m]
        assert len(found) == 0, \
            f"Listed file should not be warned, got: {found}"


# ---------------------------------------------------------------------------
# KC-4: Invalid completeness range
# ---------------------------------------------------------------------------

class TestKC4Completeness:
    """KC-4: completeness outside 0-100 should be flagged."""

    def test_detects_invalid_completeness(self):
        issues = check_kc.check_completeness(KB_DIR)
        kc4_warnings = [(s, c, m) for s, c, m in issues
                        if c == 'KC-4' and s == 'warning']
        # domain-wms-packing.md has completeness: 120%
        over_range = [m for _, _, m in kc4_warnings if '120' in m]
        assert len(over_range) >= 1, \
            f"Expected completeness warning for 120%, got: {kc4_warnings}"


# ---------------------------------------------------------------------------
# KC-5: Invalid source type
# ---------------------------------------------------------------------------

class TestKC5SourceType:
    """KC-5: source types not in the valid set should be flagged."""

    def test_detects_invalid_source(self):
        issues = check_kc.check_glossary(KB_DIR)
        kc5_warnings = [(s, c, m) for s, c, m in issues
                        if c == 'KC-5' and s == 'warning']
        # '签收' has source: magic, which is invalid
        magic_hits = [m for _, _, m in kc5_warnings if 'magic' in m]
        assert len(magic_hits) >= 1, \
            f"Expected invalid source warning for 'magic', got: {kc5_warnings}"
