"""
test_diagram_core.py — Tests for diagram_core.py shared module.

Covers: validate(), compute_layout(), get_node_size(), _estimate_label_width()
"""

import os
import pytest
import yaml

import diagram_core


FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


def _load_yaml(name):
    with open(os.path.join(FIXTURES, name), 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------

class TestValidate:
    """Tests for diagram_core.validate()."""

    def test_valid_swimlane_no_errors(self):
        data = _load_yaml('valid_swimlane.yaml')
        errors, warnings = diagram_core.validate(data)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_valid_flow_no_errors(self):
        data = _load_yaml('valid_flow.yaml')
        errors, warnings = diagram_core.validate(data)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_valid_er_no_errors(self):
        data = _load_yaml('valid_er.yaml')
        errors, warnings = diagram_core.validate(data)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_missing_title_produces_error(self):
        data = _load_yaml('missing_title.yaml')
        errors, _ = diagram_core.validate(data)
        assert any('title' in e for e in errors), \
            f"Expected error about missing title, got: {errors}"

    def test_invalid_type_produces_error(self):
        data = _load_yaml('invalid_type.yaml')
        errors, _ = diagram_core.validate(data)
        assert any('type' in e for e in errors), \
            f"Expected error about invalid type, got: {errors}"

    def test_duplicate_node_ids_produces_error(self):
        data = _load_yaml('duplicate_ids.yaml')
        errors, _ = diagram_core.validate(data)
        assert any('重复' in e for e in errors), \
            f"Expected duplicate ID error, got: {errors}"

    def test_decision_with_fewer_than_2_edges(self):
        data = _load_yaml('decision_one_edge.yaml')
        errors, _ = diagram_core.validate(data)
        assert any('decision' in e and '2' in e for e in errors), \
            f"Expected decision edge count error, got: {errors}"


# ---------------------------------------------------------------------------
# compute_layout()
# ---------------------------------------------------------------------------

class TestComputeLayout:
    """Tests for diagram_core.compute_layout()."""

    def test_swimlane_layout_returns_all_positions(self):
        data = _load_yaml('valid_swimlane.yaml')
        node_positions, lane_geometries, diagram_info = diagram_core.compute_layout(data)
        node_ids = {n['id'] for n in data['nodes']}
        assert set(node_positions.keys()) == node_ids

    def test_swimlane_layout_has_lane_geometries(self):
        data = _load_yaml('valid_swimlane.yaml')
        _, lane_geometries, _ = diagram_core.compute_layout(data)
        lane_ids = {l['id'] for l in data['lanes']}
        assert set(lane_geometries.keys()) == lane_ids

    def test_flow_layout_returns_all_positions(self):
        data = _load_yaml('valid_flow.yaml')
        node_positions, lane_geometries, diagram_info = diagram_core.compute_layout(data)
        node_ids = {n['id'] for n in data['nodes']}
        assert set(node_positions.keys()) == node_ids
        # flow layout has no lane geometries
        assert lane_geometries == {}

    def test_layout_coordinates_are_positive(self):
        data = _load_yaml('valid_flow.yaml')
        node_positions, _, _ = diagram_core.compute_layout(data)
        for nid, (x, y, w, h) in node_positions.items():
            assert x >= 0, f"Node {nid} has negative x={x}"
            assert y >= 0, f"Node {nid} has negative y={y}"
            assert w > 0, f"Node {nid} has non-positive width={w}"
            assert h > 0, f"Node {nid} has non-positive height={h}"


# ---------------------------------------------------------------------------
# get_node_size() and CJK width estimation
# ---------------------------------------------------------------------------

class TestGetNodeSize:
    """Tests for diagram_core.get_node_size() and _estimate_label_width()."""

    def test_cjk_label_wider_than_ascii(self):
        """A CJK label should produce a wider estimated width than a same-length ASCII label."""
        cjk_width = diagram_core._estimate_label_width("订单管理系统")
        ascii_width = diagram_core._estimate_label_width("abcdef")
        assert cjk_width > ascii_width

    def test_mixed_label_width(self):
        """Mixed ASCII/CJK: width should be between pure ASCII and pure CJK of same char count."""
        mixed = diagram_core._estimate_label_width("OMS订单")
        pure_ascii = diagram_core._estimate_label_width("OMS12")
        pure_cjk = diagram_core._estimate_label_width("订单管理系")
        assert mixed > pure_ascii
        assert mixed < pure_cjk

    def test_decision_node_wider_due_to_rhombus(self):
        """Decision (rhombus) nodes get extra width for the same label."""
        label = "Check Stock"
        process_w, _ = diagram_core.get_node_size({'type': 'process', 'label': label})
        decision_w, _ = diagram_core.get_node_size({'type': 'decision', 'label': label})
        assert decision_w >= process_w

    def test_start_end_nodes_use_fixed_size_for_short_label(self):
        """Start/end nodes with short labels use the default fixed size."""
        w, h = diagram_core.get_node_size({'type': 'start', 'label': 'S'})
        default_w, default_h = diagram_core.DEFAULT_NODE_SIZES['start']
        assert w == default_w
        assert h == default_h
