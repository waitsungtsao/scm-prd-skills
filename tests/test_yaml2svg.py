"""Tests for yaml2svg.py — SVG generation from YAML diagram DSL."""

import os
import importlib

import yaml

yaml2svg = importlib.import_module('yaml2svg')
diagram_core = importlib.import_module('diagram_core')

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def _load_yaml(name):
    path = os.path.join(FIXTURE_DIR, name)
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _generate(name):
    """Load YAML, validate, compute layout, generate SVG."""
    data = _load_yaml(name)
    errors, warnings = diagram_core.validate(data)
    assert not errors, f"Validation errors: {errors}"
    node_positions, lane_geometries, diagram_info = diagram_core.compute_layout(data)
    return yaml2svg.generate_svg(data, node_positions, lane_geometries, diagram_info)


class TestSwimlaneSvg:
    def test_produces_valid_svg(self):
        svg = _generate('valid_swimlane.yaml')
        assert svg.startswith('<svg')
        assert '</svg>' in svg

    def test_contains_text_elements(self):
        svg = _generate('valid_swimlane.yaml')
        assert '<text' in svg


class TestFlowSvg:
    def test_produces_valid_svg(self):
        svg = _generate('valid_flow.yaml')
        assert svg.startswith('<svg')
        assert '</svg>' in svg


class TestErSvg:
    def test_produces_valid_svg(self):
        svg = _generate('valid_er.yaml')
        assert svg.startswith('<svg')
        assert '</svg>' in svg

    def test_contains_entity_text(self):
        svg = _generate('valid_er.yaml')
        assert '<text' in svg
