"""Smoke tests for md2docx.mjs — Markdown to Word conversion."""

import os
import subprocess
import tempfile


SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'scm-prd-workflow', 'scripts', 'md2docx.mjs'
)


def _has_node_and_docx():
    """Check if Node.js and docx package are available."""
    try:
        result = subprocess.run(
            ['node', '-e', 'require("docx")'],
            capture_output=True, text=True,
            env={**os.environ, 'NODE_PATH': subprocess.run(
                ['npm', 'root', '-g'], capture_output=True, text=True
            ).stdout.strip()}
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


SAMPLE_MD = """---
type: prd
version: V1.0
---

# Test PRD

## 1. Document Info

| Version | Date |
|---------|------|
| V1.0 | 2026-01-01 |

## 2. Overview

#### G-01 Reduce manual work

Goal description here.

#### F-001 Auto allocation

Feature description.

| Step | Action | Rule |
|------|--------|------|
| 1 | Check stock | Stock >= order qty |

> [!INFO] This is an info block

> [待确认] Is this correct?
> Current assumption: yes.
"""


class TestMd2Docx:
    def test_generates_docx_file(self):
        """Given markdown input, should produce a valid .docx file."""
        if not _has_node_and_docx():
            import pytest
            pytest.skip("Node.js or docx package not available")

        with tempfile.TemporaryDirectory() as tmp:
            md_path = os.path.join(tmp, 'test.md')
            docx_path = os.path.join(tmp, 'test.docx')
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(SAMPLE_MD)

            npm_root = subprocess.run(
                ['npm', 'root', '-g'], capture_output=True, text=True
            ).stdout.strip()

            result = subprocess.run(
                ['node', SCRIPT_PATH, md_path, docx_path],
                capture_output=True, text=True,
                env={**os.environ, 'NODE_PATH': npm_root}
            )

            assert result.returncode == 0, f"md2docx failed: {result.stderr}"
            assert os.path.exists(docx_path), "docx file was not created"
            assert os.path.getsize(docx_path) > 1000, "docx file is suspiciously small"

    def test_docx_is_valid_zip(self):
        """Output .docx should be a valid ZIP file (OOXML format)."""
        if not _has_node_and_docx():
            import pytest
            pytest.skip("Node.js or docx package not available")

        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            md_path = os.path.join(tmp, 'test.md')
            docx_path = os.path.join(tmp, 'test.docx')
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(SAMPLE_MD)

            npm_root = subprocess.run(
                ['npm', 'root', '-g'], capture_output=True, text=True
            ).stdout.strip()

            subprocess.run(
                ['node', SCRIPT_PATH, md_path, docx_path],
                capture_output=True, env={**os.environ, 'NODE_PATH': npm_root}
            )

            assert zipfile.is_zipfile(docx_path), "docx is not a valid ZIP/OOXML file"
