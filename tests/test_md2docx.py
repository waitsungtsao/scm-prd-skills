"""Smoke tests for md2docx.mjs — Markdown to Word conversion."""

import os
import re
import struct
import subprocess
import tempfile
import zipfile
import zlib


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


def _make_png(w, h):
    """生成最小合法 PNG（纯白）"""
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    raw = b"".join(b"\x00" + b"\xff\xff\xff" * w for _ in range(h))
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _make_jpg():
    """最小合法 JPEG（仅 SOI/JFIF/EOI，docx 库只看 magic bytes 不解码）"""
    return (bytes([0xff, 0xd8, 0xff, 0xe0, 0, 16]) + b"JFIF\0"
            + b"\x01\x01\x01\x00\x48\x00\x48\x00\x00" + bytes([0xff, 0xd9]))


class TestImageRendering:
    """回归测试：md-to-docx 仓库 commit 98d316a 修复的 3 个图片 bug。

    Bug 1: ImageRun.transformation 被传 EMU 而非像素，docx 库再乘 9525 → cx 溢出
    Bug 2: ImageRun 缺 type，媒体文件名变成 .undefined
    Bug 3: docx@9.6.1 库 bug 导致所有 wp:docPr id 全为 1
    """

    def _generate(self, tmp):
        png_path = os.path.join(tmp, 'pic.png')
        jpg_path = os.path.join(tmp, 'pic.jpg')
        with open(png_path, 'wb') as f:
            f.write(_make_png(800, 600))
        with open(jpg_path, 'wb') as f:
            f.write(_make_jpg())

        md_path = os.path.join(tmp, 'test.md')
        docx_path = os.path.join(tmp, 'test.docx')
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(
                "---\ntype: prd\nversion: V1.0\n---\n\n"
                "# Image Test\n\n## 1. Pics\n\n"
                "![first](pic.png)\n\n![second](pic.jpg)\n\n![third](pic.png)\n"
            )

        npm_root = subprocess.run(
            ['npm', 'root', '-g'], capture_output=True, text=True
        ).stdout.strip()
        result = subprocess.run(
            ['node', SCRIPT_PATH, md_path, docx_path],
            capture_output=True, text=True,
            env={**os.environ, 'NODE_PATH': npm_root}
        )
        assert result.returncode == 0, f"md2docx failed: {result.stderr}"
        return docx_path

    def test_media_files_have_correct_extensions(self):
        """Bug 2: 媒体文件扩展名应反映实际类型，不能是 .undefined"""
        if not _has_node_and_docx():
            import pytest
            pytest.skip("Node.js or docx package not available")

        with tempfile.TemporaryDirectory() as tmp:
            docx_path = self._generate(tmp)
            with zipfile.ZipFile(docx_path) as z:
                media = [n for n in z.namelist()
                         if n.startswith('word/media/') and not n.endswith('/')]
            assert media, "no media files in docx"
            assert all(not n.endswith('.undefined') for n in media), \
                f"media has .undefined extension (type missing): {media}"
            assert any(n.endswith('.png') for n in media), f"no png media: {media}"
            assert any(n.endswith(('.jpg', '.jpeg')) for n in media), \
                f"no jpg media: {media}"

    def test_image_dimensions_in_valid_emu_range(self):
        """Bug 1: cx 应在合理 EMU 范围（6 inch ≈ 5.5M），不能因单位混用溢出"""
        if not _has_node_and_docx():
            import pytest
            pytest.skip("Node.js or docx package not available")

        with tempfile.TemporaryDirectory() as tmp:
            docx_path = self._generate(tmp)
            with zipfile.ZipFile(docx_path) as z:
                xml = z.read('word/document.xml').decode()
            cx_vals = [int(v) for v in re.findall(r'cx="(\d+)"', xml)]
            assert cx_vals, "no extent cx attributes found"
            for cx in cx_vals:
                # 修复前 bug: 6*914400*9525 ≈ 5.2e10
                assert cx < 100_000_000, \
                    f"cx={cx} too large — 单位混用 bug 回归（EMU 当 px 传）"
                assert cx > 1_000_000, f"cx={cx} unexpectedly small"

    def test_docpr_ids_are_unique(self):
        """Bug 3: 多张图片的 wp:docPr id 必须唯一，不能全为 1"""
        if not _has_node_and_docx():
            import pytest
            pytest.skip("Node.js or docx package not available")

        with tempfile.TemporaryDirectory() as tmp:
            docx_path = self._generate(tmp)
            with zipfile.ZipFile(docx_path) as z:
                xml = z.read('word/document.xml').decode()
            ids = re.findall(r'<wp:docPr\s+id="(\d+)"', xml)
            assert len(ids) >= 3, f"expected ≥3 docPr ids for 3 images, got {ids}"
            assert len(set(ids)) == len(ids), \
                f"docPr ids not unique: {ids} — docx@9.6.1 计数器 bug 回归"
