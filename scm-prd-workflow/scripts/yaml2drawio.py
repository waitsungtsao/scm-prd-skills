#!/usr/bin/env python3
"""
yaml2drawio.py — 将 YAML 图表 DSL 转换为 draw.io XML 文件

泳道图布局：泳道横向排列（列），流程从上往下。
普通流程图布局：节点从左到右按拓扑排列。

用法:
    python yaml2drawio.py <input.diagram.yaml> [output.drawio]

依赖: PyYAML (pip install pyyaml)
兼容: Python 3.8+
"""

import sys
import os
from xml.sax.saxutils import escape

try:
    import yaml
except ImportError:
    print("错误: 需要 PyYAML 库。请运行: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

from diagram_core import (
    # 颜色常量
    COLORS, DEFAULT_COLOR, DEFAULT_LANE_COLOR, STYLE_COLORS,
    # 节点尺寸
    DEFAULT_NODE_SIZES, get_node_size, NODE_SIZES,
    # 布局参数
    LANE_HEADER_HEIGHT, DIAGRAM_MARGIN, TITLE_HEIGHT,
    # 校验
    validate,
    # 布局引擎
    compute_layout, compute_edge_ports, validate_edge_layout,
)

# =============================================================================
# draw.io 默认 CJK 字体（draw.io 应用自身支持 CSS font-family fallback，
# 此处为跨平台兼容提供多候选）
DRAWIO_FONT_FAMILY = "PingFang SC,Microsoft YaHei,Noto Sans CJK SC,sans-serif"


# =============================================================================
# draw.io XML 生成
# =============================================================================

def node_style(node, lane_color_name=None):
    """根据节点类型和样式生成 draw.io style 字符串。"""
    ntype = node.get('type', 'process')
    nstyle = node.get('style')

    if nstyle in STYLE_COLORS:
        fill = STYLE_COLORS[nstyle]['fill']
        stroke = STYLE_COLORS[nstyle]['stroke']
    elif lane_color_name and lane_color_name in COLORS:
        fill = COLORS[lane_color_name]['fill']
        stroke = COLORS[lane_color_name]['stroke']
    elif lane_color_name is not None:
        # 节点在泳道内但泳道未指定颜色 → 用泳道默认色
        fill = DEFAULT_LANE_COLOR['fill']
        stroke = DEFAULT_LANE_COLOR['stroke']
    else:
        fill = DEFAULT_COLOR['fill']
        stroke = DEFAULT_COLOR['stroke']

    base = f"fillColor={fill};strokeColor={stroke};fontFamily={DRAWIO_FONT_FAMILY};fontSize=12;"

    if ntype == 'decision':
        return f"rhombus;whiteSpace=wrap;html=1;{base}"
    elif ntype == 'start':
        return f"ellipse;whiteSpace=wrap;html=1;{base}aspect=fixed;"
    elif ntype == 'end':
        return f"ellipse;whiteSpace=wrap;html=1;{base}aspect=fixed;strokeWidth=3;"
    elif ntype == 'subprocess':
        return f"shape=mxgraph.flowchart.predefined_process;whiteSpace=wrap;html=1;{base}"
    elif ntype == 'database':
        return f"shape=cylinder3;whiteSpace=wrap;html=1;{base}size=15;"
    elif ntype == 'document':
        return f"shape=document;whiteSpace=wrap;html=1;{base}size=0.15;"
    else:  # process
        return f"rounded=1;whiteSpace=wrap;html=1;{base}"


def edge_style(edge_data, exit_port=None, entry_port=None):
    """根据边样式和端口生成 draw.io style 字符串。"""
    estyle = edge_data.get('style')
    base = ("edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;"
            "jettySize=auto;html=1;jumpStyle=arc;jumpSize=6;")
    base += f"fontFamily={DRAWIO_FONT_FAMILY};fontSize=11;"

    if exit_port:
        base += f"exitX={exit_port[0]};exitY={exit_port[1]};exitDx=0;exitDy=0;"
    if entry_port:
        base += f"entryX={entry_port[0]};entryY={entry_port[1]};entryDx=0;entryDy=0;"

    if estyle == 'error':
        return base + f"strokeColor={COLORS['red']['stroke']};strokeWidth=2;"
    elif estyle == 'async':
        return base + "dashed=1;dashPattern=8 4;"
    else:
        return base


def generate_er_xml(data):
    """生成 ER 图的 draw.io XML 字符串。实体渲染为表格形状，关系渲染为带基数的连线。"""
    entities = data.get('entities', [])
    relationships = data.get('relationships', [])
    title = data['diagram'].get('title', 'ER Diagram')

    # 布局：实体网格排列
    col_count = max(2, min(4, len(entities)))
    entity_width = 200
    entity_margin_x = 60
    entity_margin_y = 60
    header_h = 30
    field_h = 22
    title_h = 40
    margin = 20

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<mxfile>')
    lines.append('  <diagram name="Page-1">')

    page_w = margin * 2 + col_count * (entity_width + entity_margin_x)
    rows_needed = (len(entities) + col_count - 1) // col_count
    max_fields = max((len(e.get('fields', [])) for e in entities), default=3)
    entity_height = header_h + max_fields * field_h + 10
    page_h = margin * 2 + title_h + rows_needed * (entity_height + entity_margin_y)
    page_w = max(1200, page_w)
    page_h = max(800, page_h)

    lines.append(f'    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" '
                 f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
                 f'pageWidth="{page_w}" pageHeight="{page_h}">')
    lines.append('      <root>')
    lines.append('        <mxCell id="0"/>')
    lines.append('        <mxCell id="1" parent="0"/>')

    cell_id = 10
    entity_cell_ids = {}

    # 图表标题
    title_style = (f"text;html=1;align=center;verticalAlign=middle;resizable=0;"
                   f"points=[];autosize=0;fontStyle=1;fontSize=16;"
                   f"fontFamily={DRAWIO_FONT_FAMILY};")
    tw = page_w - 2 * margin
    lines.append(f'        <mxCell id="{cell_id}" '
                 f'value="{escape(title)}" '
                 f'style="{title_style}" vertex="1" parent="1">')
    lines.append(f'          <mxGeometry x="{margin}" y="{margin}" '
                 f'width="{tw}" height="{title_h}" as="geometry"/>')
    lines.append(f'        </mxCell>')
    cell_id += 1

    # 实体（表格形状）
    for idx, entity in enumerate(entities):
        col = idx % col_count
        row = idx // col_count
        x = margin + col * (entity_width + entity_margin_x)
        y = margin + title_h + entity_margin_y // 2 + row * (entity_height + entity_margin_y)

        fields = entity.get('fields', [])
        eh = header_h + len(fields) * field_h + 10

        eid = entity.get('id')
        ecid = cell_id
        cell_id += 1
        entity_cell_ids[eid] = ecid

        ecolor = entity.get('color')
        if ecolor and ecolor in COLORS:
            fill = COLORS[ecolor]['fill']
            stroke = COLORS[ecolor]['stroke']
        else:
            fill = '#dae8fc'
            stroke = '#6c8ebf'

        table_style = (f"shape=table;startSize={header_h};container=1;collapsible=0;"
                       f"childLayout=tableLayout;fixedRows=1;rowLines=1;fontStyle=1;"
                       f"align=center;resizeLast=1;fillColor={fill};strokeColor={stroke};"
                       f"fontFamily={DRAWIO_FONT_FAMILY};fontSize=12;html=1;whiteSpace=wrap;")
        lines.append(f'        <mxCell id="{ecid}" '
                     f'value="{escape(entity.get("label", eid))}" '
                     f'style="{table_style}" vertex="1" parent="1">')
        lines.append(f'          <mxGeometry x="{x}" y="{y}" '
                     f'width="{entity_width}" height="{eh}" as="geometry"/>')
        lines.append(f'        </mxCell>')

        # 字段行
        for field in fields:
            rcid = cell_id
            cell_id += 1
            pk_mark = "PK " if field.get('pk') else ("FK " if field.get('fk') else "")
            field_label = f"{pk_mark}{field.get('name', '')} : {field.get('type', '')}  {field.get('comment', '')}"
            row_style = ("text;strokeColor=none;align=left;verticalAlign=middle;"
                         f"spacingLeft=6;spacingRight=4;overflow=hidden;rotatable=0;"
                         f"points=[[0,0.5],[1,0.5]];portConstraint=eastwest;"
                         f"fontFamily={DRAWIO_FONT_FAMILY};fontSize=11;html=1;whiteSpace=wrap;")
            lines.append(f'        <mxCell id="{rcid}" '
                         f'value="{escape(field_label)}" '
                         f'style="{row_style}" vertex="1" parent="{ecid}">')
            lines.append(f'          <mxGeometry y="{header_h + fields.index(field) * field_h}" '
                         f'width="{entity_width}" height="{field_h}" as="geometry"/>')
            lines.append(f'        </mxCell>')

    # 关系连线
    cardinality_labels = {
        '1:1': ('1', '1'), '1:N': ('1', '*'), 'N:1': ('*', '1'), 'N:M': ('*', '*'),
    }
    for rel in relationships:
        rfrom = rel.get('from')
        rto = rel.get('to')
        if rfrom not in entity_cell_ids or rto not in entity_cell_ids:
            continue
        ecid = cell_id
        cell_id += 1
        rtype = rel.get('type', '1:N')
        src_card, tgt_card = cardinality_labels.get(rtype, ('', ''))
        label = rel.get('label', '')
        estyle = (f"edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;"
                  f"jettySize=auto;html=1;fontFamily={DRAWIO_FONT_FAMILY};fontSize=11;"
                  f"exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
                  f"entryX=0;entryY=0.5;entryDx=0;entryDy=0;")
        lines.append(f'        <mxCell id="{ecid}" value="{escape(label)}" '
                     f'style="{estyle}" edge="1" source="{entity_cell_ids[rfrom]}" '
                     f'target="{entity_cell_ids[rto]}" parent="1">')
        lines.append(f'          <mxGeometry relative="1" as="geometry">')
        lines.append(f'            <Array as="points"/>')
        lines.append(f'          </mxGeometry>')
        lines.append(f'        </mxCell>')
        # 源端基数标签
        if src_card:
            lcid = cell_id
            cell_id += 1
            lines.append(f'        <mxCell id="{lcid}" value="{src_card}" '
                         f'style="edgeLabel;align=left;verticalAlign=middle;'
                         f'fontFamily={DRAWIO_FONT_FAMILY};fontSize=10;" '
                         f'vertex="1" connectable="0" parent="{ecid}">')
            lines.append(f'          <mxGeometry x="-0.8" relative="1" as="geometry"/>')
            lines.append(f'        </mxCell>')
        # 目标端基数标签
        if tgt_card:
            lcid = cell_id
            cell_id += 1
            lines.append(f'        <mxCell id="{lcid}" value="{tgt_card}" '
                         f'style="edgeLabel;align=right;verticalAlign=middle;'
                         f'fontFamily={DRAWIO_FONT_FAMILY};fontSize=10;" '
                         f'vertex="1" connectable="0" parent="{ecid}">')
            lines.append(f'          <mxGeometry x="0.8" relative="1" as="geometry"/>')
            lines.append(f'        </mxCell>')

    lines.append('      </root>')
    lines.append('    </mxGraphModel>')
    lines.append('  </diagram>')
    lines.append('</mxfile>')
    return '\n'.join(lines)


def generate_xml(data, node_positions, lane_geometries, diagram_info):
    """生成完整的 draw.io XML 字符串。"""
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<mxfile>')
    lines.append('  <diagram name="Page-1">')
    # 画布尺寸根据图表实际尺寸动态计算，至少 1600×1200
    page_w = max(1600, diagram_info.get('total_width', 1600) + 100)
    page_h = max(1200, diagram_info.get('total_height', 1200) + 100)
    lines.append(f'    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" '
                 f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
                 f'pageWidth="{page_w}" pageHeight="{page_h}">')
    lines.append('      <root>')
    lines.append('        <mxCell id="0"/>')
    lines.append('        <mxCell id="1" parent="0"/>')

    cell_id = 10
    node_cell_ids = {}
    lane_cell_ids = {}

    dtype = data['diagram'].get('type', 'flow')
    lanes = data.get('lanes', [])
    nodes = data.get('nodes', [])
    edges = data.get('edges', [])
    lane_map = {lane['id']: lane for lane in lanes}

    if dtype == 'swimlane' and lane_geometries:
        # ── 图表标题 ──
        title_id = cell_id
        cell_id += 1
        tw = diagram_info['total_width'] - 2 * DIAGRAM_MARGIN
        title_style = (f"text;html=1;align=center;verticalAlign=middle;resizable=0;"
                        f"points=[];autosize=0;fontStyle=1;fontSize=16;"
                        f"fontFamily={DRAWIO_FONT_FAMILY};")
        lines.append(f'        <mxCell id="{title_id}" '
                     f'value="{escape(data["diagram"]["title"])}" '
                     f'style="{title_style}" vertex="1" parent="1">')
        lines.append(f'          <mxGeometry x="{DIAGRAM_MARGIN}" y="{DIAGRAM_MARGIN}" '
                     f'width="{tw}" height="{TITLE_HEIGHT}" as="geometry"/>')
        lines.append(f'        </mxCell>')

        # ── 泳道列（swimlane 容器）──
        for lane in lanes:
            lid = lane['id']
            lx, ly, lw, lh = lane_geometries[lid]
            lcid = cell_id
            cell_id += 1
            lane_cell_ids[lid] = lcid

            lcolor = lane.get('color')
            if lcolor and lcolor in COLORS:
                lane_fill = COLORS[lcolor]['fill']
                lane_stroke = COLORS[lcolor]['stroke']
            else:
                lane_fill = DEFAULT_LANE_COLOR['fill']
                lane_stroke = DEFAULT_LANE_COLOR['stroke']

            lane_style = (f"swimlane;startSize={LANE_HEADER_HEIGHT};horizontal=1;"
                          f"fillColor={lane_fill};strokeColor={lane_stroke};"
                          f"fontFamily={DRAWIO_FONT_FAMILY};fontSize=12;fontStyle=1;"
                          f"collapsible=0;container=1;swimlaneBody=1;")
            lines.append(f'        <mxCell id="{lcid}" '
                         f'value="{escape(lane["label"])}" '
                         f'style="{lane_style}" vertex="1" parent="1">')
            lines.append(f'          <mxGeometry x="{lx}" y="{ly}" '
                         f'width="{lw}" height="{lh}" as="geometry"/>')
            lines.append(f'        </mxCell>')

        # ── 节点（子元素，坐标相对于所属泳道）──
        for node in nodes:
            nid = node['id']
            if nid not in node_positions:
                continue
            rel_x, rel_y, nw, nh = node_positions[nid]
            ncid = cell_id
            cell_id += 1
            node_cell_ids[nid] = ncid

            # '' = 在泳道内但泳道未指定颜色, None = 不在泳道内
            lane_color = (lane_map[node['lane']].get('color', '')
                          if node.get('lane') in lane_map else None)
            nstyle = node_style(node, lane_color)
            parent_id = lane_cell_ids.get(node.get('lane'), 1)

            lines.append(f'        <mxCell id="{ncid}" '
                         f'value="{escape(node["label"])}" '
                         f'style="{nstyle}" vertex="1" parent="{parent_id}">')
            lines.append(f'          <mxGeometry x="{rel_x}" y="{rel_y}" '
                         f'width="{nw}" height="{nh}" as="geometry"/>')
            lines.append(f'        </mxCell>')

    else:
        # ── 普通流程图：节点直接放在顶层 ──
        for node in nodes:
            nid = node['id']
            if nid not in node_positions:
                continue
            x, y, nw, nh = node_positions[nid]
            ncid = cell_id
            cell_id += 1
            node_cell_ids[nid] = ncid

            nstyle = node_style(node, None)
            lines.append(f'        <mxCell id="{ncid}" '
                         f'value="{escape(node["label"])}" '
                         f'style="{nstyle}" vertex="1" parent="1">')
            lines.append(f'          <mxGeometry x="{x}" y="{y}" '
                         f'width="{nw}" height="{nh}" as="geometry"/>')
            lines.append(f'        </mxCell>')

    # ── 连线（始终挂在顶层 parent="1"，支持跨泳道连线）──
    port_map = compute_edge_ports(
        edges, nodes, node_positions, lane_geometries,
        is_swimlane=(dtype == 'swimlane'),
    )
    for edge_data in edges:
        efrom = edge_data['from']
        eto = edge_data['to']
        if efrom not in node_cell_ids or eto not in node_cell_ids:
            continue
        ecid = cell_id
        cell_id += 1

        ports = port_map.get((efrom, eto), {})
        estyle = edge_style(edge_data,
                            exit_port=ports.get('exit'),
                            entry_port=ports.get('entry'))
        label = escape(edge_data.get('label', ''))

        lines.append(f'        <mxCell id="{ecid}" value="{label}" '
                     f'style="{estyle}" edge="1" source="{node_cell_ids[efrom]}" '
                     f'target="{node_cell_ids[eto]}" parent="1">')
        lines.append(f'          <mxGeometry relative="1" as="geometry"/>')
        lines.append(f'        </mxCell>')

    lines.append('      </root>')
    lines.append('    </mxGraphModel>')
    lines.append('  </diagram>')
    lines.append('</mxfile>')

    return '\n'.join(lines)


# =============================================================================
# 主函数
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print("用法: python yaml2drawio.py <input.diagram.yaml> [output.drawio]", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    if not os.path.isfile(input_path):
        print(f"错误: 文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    # 确定输出路径
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        base = input_path
        if base.endswith('.diagram.yaml'):
            base = base[:-len('.diagram.yaml')]
        elif base.endswith('.yaml') or base.endswith('.yml'):
            base = os.path.splitext(base)[0]
        output_path = base + '.drawio'

    # 读取 YAML
    with open(input_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    if not data:
        print("错误: YAML 文件为空", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, dict):
        print(f"错误: YAML 内容必须是字典（mapping），当前类型为 {type(data).__name__}", file=sys.stderr)
        sys.exit(1)

    # 校验
    errors, warnings = validate(data)
    if warnings:
        print("YAML 校验警告:", file=sys.stderr)
        for warn in warnings:
            print(f"  ⚠ {warn}", file=sys.stderr)
    if errors:
        print("YAML 校验失败:", file=sys.stderr)
        for err in errors:
            print(f"  ✗ {err}", file=sys.stderr)
        sys.exit(1)

    # ER 图使用专用渲染
    if data['diagram'].get('type') == 'er':
        xml = generate_er_xml(data)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml)
        print(f"✓ 已生成 ER 图: {output_path}")
        return

    # 布局计算
    node_positions, lane_geometries, diagram_info = compute_layout(data)

    # 边布局校验
    dtype = data['diagram'].get('type', 'flow')
    edges = data.get('edges', [])
    nodes = data.get('nodes', [])
    port_map = compute_edge_ports(edges, nodes, node_positions,
                                  lane_geometries,
                                  is_swimlane=(dtype == 'swimlane'))
    layout_warnings = validate_edge_layout(edges, nodes, node_positions,
                                           lane_geometries, port_map)
    if layout_warnings:
        print("边布局校验:", file=sys.stderr)
        for lw in layout_warnings:
            print(f"  ⚠ {lw}", file=sys.stderr)

    # 生成 XML
    xml = generate_xml(data, node_positions, lane_geometries, diagram_info)

    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml)

    print(f"✓ 已生成: {output_path}")


if __name__ == '__main__':
    main()
