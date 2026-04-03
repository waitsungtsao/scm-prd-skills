"""
test_yaml2drawio.py — Tests for yaml2drawio.py draw.io XML generation.

Covers: generate_xml() for swimlane/flow, generate_er_xml(), end-to-end XML validity.
"""

import os
import xml.etree.ElementTree as ET
import pytest
import yaml

import diagram_core

# yaml2drawio must be imported after diagram_core is on the path (conftest handles this)
import importlib
yaml2drawio = importlib.import_module('yaml2drawio')


FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


def _load_yaml(name):
    with open(os.path.join(FIXTURES, name), 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _generate_full_xml(data):
    """Helper: run layout then generate XML (for swimlane/flow diagrams)."""
    node_positions, lane_geometries, diagram_info = diagram_core.compute_layout(data)
    return yaml2drawio.generate_xml(data, node_positions, lane_geometries, diagram_info)


def _assert_valid_drawio_xml(xml_str):
    """Parse XML and verify basic draw.io structure."""
    root = ET.fromstring(xml_str)
    assert root.tag == 'mxfile'
    diagram = root.find('diagram')
    assert diagram is not None
    model = diagram.find('mxGraphModel')
    assert model is not None
    graph_root = model.find('root')
    assert graph_root is not None
    cells = graph_root.findall('mxCell')
    # At minimum: cell 0 (root) + cell 1 (default parent)
    assert len(cells) >= 2


class TestSwimlaneXml:
    """Tests for swimlane diagram XML generation."""

    def test_produces_valid_xml(self):
        data = _load_yaml('valid_swimlane.yaml')
        xml_str = _generate_full_xml(data)
        _assert_valid_drawio_xml(xml_str)

    def test_contains_lane_cells(self):
        data = _load_yaml('valid_swimlane.yaml')
        xml_str = _generate_full_xml(data)
        root = ET.fromstring(xml_str)
        # Swimlane containers should have swimlane style
        all_cells = root.iter('mxCell')
        swimlane_cells = [c for c in all_cells if 'swimlane' in (c.get('style') or '')]
        assert len(swimlane_cells) == len(data['lanes'])

    def test_contains_edge_cells(self):
        data = _load_yaml('valid_swimlane.yaml')
        xml_str = _generate_full_xml(data)
        root = ET.fromstring(xml_str)
        edge_cells = [c for c in root.iter('mxCell') if c.get('edge') == '1']
        assert len(edge_cells) == len(data['edges'])


class TestFlowXml:
    """Tests for plain flow diagram XML generation."""

    def test_produces_valid_xml(self):
        data = _load_yaml('valid_flow.yaml')
        xml_str = _generate_full_xml(data)
        _assert_valid_drawio_xml(xml_str)

    def test_node_count_matches(self):
        data = _load_yaml('valid_flow.yaml')
        xml_str = _generate_full_xml(data)
        root = ET.fromstring(xml_str)
        # Vertex cells with parent="1" are top-level nodes
        vertex_cells = [c for c in root.iter('mxCell')
                        if c.get('vertex') == '1' and c.get('parent') == '1']
        assert len(vertex_cells) == len(data['nodes'])


class TestErXml:
    """Tests for ER diagram XML generation."""

    def test_produces_valid_xml(self):
        data = _load_yaml('valid_er.yaml')
        xml_str = yaml2drawio.generate_er_xml(data)
        _assert_valid_drawio_xml(xml_str)

    def test_contains_entity_tables(self):
        data = _load_yaml('valid_er.yaml')
        xml_str = yaml2drawio.generate_er_xml(data)
        root = ET.fromstring(xml_str)
        table_cells = [c for c in root.iter('mxCell')
                       if 'shape=table' in (c.get('style') or '')]
        assert len(table_cells) == len(data['entities'])

    def test_contains_relationship_edges(self):
        data = _load_yaml('valid_er.yaml')
        xml_str = yaml2drawio.generate_er_xml(data)
        root = ET.fromstring(xml_str)
        edge_cells = [c for c in root.iter('mxCell') if c.get('edge') == '1']
        assert len(edge_cells) == len(data['relationships'])
