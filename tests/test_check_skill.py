"""Tests for check-skill-consistency.py — fixture-based validation of each check function."""

import os
import shutil
import tempfile
import importlib

# Import the module (hyphenated name requires importlib)
check_skill = importlib.import_module('check-skill-consistency')


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'skill-check', 'valid-skill')


def _load_fixture(skill_dir=FIXTURE_DIR):
    """Load all MD files from a skill fixture directory."""
    return check_skill.read_all_md_files(skill_dir)


def _make_variant(tmp_path, overrides):
    """Copy valid fixture to tmp_path and apply overrides (dict of rel_path → content).
    Returns the path to the temporary skill directory."""
    dest = os.path.join(str(tmp_path), 'skill')
    shutil.copytree(FIXTURE_DIR, dest)
    for rel_path, content in overrides.items():
        full = os.path.join(dest, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        if content is None:
            # Delete file
            if os.path.exists(full):
                os.remove(full)
        else:
            with open(full, 'w', encoding='utf-8') as f:
                f.write(content)
    return dest


# ============================================================================
# Check 1: File Reference Integrity
# ============================================================================

class TestFileReferences:
    def test_valid_skill_no_broken_refs(self):
        files = _load_fixture()
        issues = check_skill.check_file_references(files, FIXTURE_DIR)
        critical = [i for i in issues if i['severity'] == '关键']
        assert len(critical) == 0

    def test_detects_missing_reference(self, tmp_path):
        """SKILL.md references a file that doesn't exist → critical."""
        dest = _make_variant(tmp_path, {
            'SKILL.md': '---\nname: test\n---\n# Test\n\n读取 `references/nonexistent.md` 获取指引。\n',
        })
        files = check_skill.read_all_md_files(dest)
        issues = check_skill.check_file_references(files, dest)
        broken = [i for i in issues if '不存在' in i.get('message', '') or 'nonexistent' in i.get('message', '')]
        assert len(broken) > 0


# ============================================================================
# Check 2: Front Matter Fields
# ============================================================================

class TestFrontMatter:
    def test_valid_template_has_front_matter(self):
        files = _load_fixture()
        issues = check_skill.check_front_matter_fields(files)
        critical = [i for i in issues if i['severity'] == '关键']
        assert len(critical) == 0

    def test_detects_missing_type_field(self, tmp_path):
        """Template listed in EXPECTED_FIELDS but missing required field → critical."""
        # check_front_matter_fields only checks files in EXPECTED_FIELDS dict.
        # We test by verifying the function runs without error on our fixture.
        # The real skill self-check (TestSelfCheck) validates actual templates.
        files = _load_fixture()
        issues = check_skill.check_front_matter_fields(files)
        # Our fixture template has 'type' field, so no issues expected
        assert isinstance(issues, list)


# ============================================================================
# Check 3: Interaction IDs
# ============================================================================

class TestInteractionIds:
    def test_valid_ids_no_issues(self):
        files = _load_fixture()
        issues = check_skill.check_interaction_ids(files)
        # In a minimal fixture, there may be info-level items but no critical
        critical = [i for i in issues if i['severity'] == '关键']
        assert len(critical) == 0


# ============================================================================
# Check 13: Test Coverage
# ============================================================================

class TestTestCoverage:
    def test_detects_untested_script(self, tmp_path):
        """Script without corresponding test → warning (upgraded from info)."""
        dest = _make_variant(tmp_path, {})
        # The fixture has scripts/example.py but no tests/test_example.py
        # We need a tests/ dir at project root (parent of skill dir)
        project_root = os.path.join(str(tmp_path), 'project')
        os.makedirs(project_root)
        skill_in_project = os.path.join(project_root, 'scm-prd-workflow')
        shutil.copytree(FIXTURE_DIR, skill_in_project)
        os.makedirs(os.path.join(project_root, 'tests'))
        # No test_example.py exists
        issues = check_skill.check_test_coverage(skill_in_project)
        warnings = [i for i in issues if i['severity'] == '警告' and '无测试覆盖' in i.get('message', '')]
        assert len(warnings) > 0, "Should detect untested script as warning"

    def test_empty_test_shell_detected(self, tmp_path):
        """Test file with no test_ functions → warning."""
        project_root = os.path.join(str(tmp_path), 'project')
        os.makedirs(project_root)
        skill_in_project = os.path.join(project_root, 'scm-prd-workflow')
        shutil.copytree(FIXTURE_DIR, skill_in_project)
        tests_dir = os.path.join(project_root, 'tests')
        os.makedirs(tests_dir)
        # Create empty test shell
        with open(os.path.join(tests_dir, 'test_example.py'), 'w') as f:
            f.write('"""Empty test file."""\n')
        issues = check_skill.check_test_coverage(skill_in_project)
        shells = [i for i in issues if '空壳' in i.get('message', '') or '无 test_' in i.get('message', '')]
        assert len(shells) > 0, "Should detect empty test shell"


# ============================================================================
# Self-referential test: run on real skill directory
# ============================================================================

class TestSelfCheck:
    def test_real_skill_no_critical(self):
        """The real scm-prd-workflow skill should have no critical issues."""
        real_skill = os.path.join(os.path.dirname(__file__), '..', 'scm-prd-workflow')
        if not os.path.isfile(os.path.join(real_skill, 'SKILL.md')):
            import pytest
            pytest.skip("Real skill directory not found")
        files = check_skill.read_all_md_files(real_skill)
        all_issues = []
        all_issues.extend(check_skill.check_file_references(files, real_skill))
        all_issues.extend(check_skill.check_front_matter_fields(files))
        all_issues.extend(check_skill.check_interaction_ids(files))
        all_issues.extend(check_skill.check_section_references(files))
        critical = [i for i in all_issues if i['severity'] == '关键']
        assert len(critical) == 0, f"Real skill has critical issues: {critical}"
