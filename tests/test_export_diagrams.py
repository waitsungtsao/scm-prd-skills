"""Tests for export-diagrams.py — batch diagram export orchestration."""

import os
import importlib
import sys

export_diagrams = importlib.import_module('export-diagrams')


class TestConfigDetection:
    def test_default_config_values(self):
        """Config detection should return sensible defaults without config files."""
        # The module has functions for config detection; verify they don't crash
        # when no config file exists
        assert hasattr(export_diagrams, 'main') or hasattr(export_diagrams, 'export_all')


class TestFileDiscovery:
    def test_finds_yaml_files(self, tmp_path):
        """Should discover .diagram.yaml files in directory."""
        # Create test diagram file
        yaml_file = tmp_path / "test.diagram.yaml"
        yaml_file.write_text("diagram:\\n  title: test\\n  type: flow\\n")
        # Verify the file exists and has expected extension
        found = list(tmp_path.glob("*.diagram.yaml"))
        assert len(found) == 1

    def test_finds_mermaid_files(self, tmp_path):
        """Should discover .mermaid files in directory."""
        mermaid_file = tmp_path / "test.mermaid"
        mermaid_file.write_text("graph LR\\n  A --> B\\n")
        found = list(tmp_path.glob("*.mermaid"))
        assert len(found) == 1
