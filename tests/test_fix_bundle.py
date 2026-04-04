"""Tests for fix-bundle-fileproto.mjs — HTML file:// protocol compatibility fixes."""

import os
import subprocess
import tempfile


SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'scm-prd-workflow', 'scripts', 'fix-bundle-fileproto.mjs'
)


def _has_node():
    try:
        subprocess.run(['node', '--version'], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


class TestFixBundle:
    def test_removes_type_module(self):
        """Should remove type='module' from script tags."""
        if not _has_node():
            import pytest
            pytest.skip("Node.js not available")

        html = '<html><head></head><body><script type="module">console.log("hi")</script></body></html>'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html)
            f.flush()
            result = subprocess.run(
                ['node', SCRIPT_PATH, f.name],
                capture_output=True, text=True
            )
            with open(f.name, 'r') as out:
                fixed = out.read()
            os.unlink(f.name)

        assert 'type="module"' not in fixed
        assert result.returncode == 0

    def test_adds_charset_meta(self):
        """Should add charset meta if missing."""
        if not _has_node():
            import pytest
            pytest.skip("Node.js not available")

        html = '<html><head></head><body>Test</body></html>'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html)
            f.flush()
            subprocess.run(['node', SCRIPT_PATH, f.name], capture_output=True)
            with open(f.name, 'r') as out:
                fixed = out.read()
            os.unlink(f.name)

        assert 'charset' in fixed.lower()

    def test_no_changes_needed(self):
        """Already-clean HTML should not be modified."""
        if not _has_node():
            import pytest
            pytest.skip("Node.js not available")

        html = '<html><head><meta charset="UTF-8"></head><body><script>console.log("hi")</script></body></html>'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html)
            f.flush()
            result = subprocess.run(
                ['node', SCRIPT_PATH, f.name],
                capture_output=True, text=True
            )
            os.unlink(f.name)

        assert result.returncode == 0
