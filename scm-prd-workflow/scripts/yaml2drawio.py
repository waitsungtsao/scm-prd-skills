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
from collections import defaultdict, deque
from xml.sax.saxutils import escape

try:
    import yaml
except ImportError:
    print("错误: 需要 PyYAML 库。请运行: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# SCM 领域色板
# =============================================================================

COLORS = {
    'blue':   {'fill': '#dae8fc', 'stroke': '#6c8ebf'},  # OMS
    'green':  {'fill': '#d5e8d4', 'stroke': '#82b366'},  # WMS
    'orange': {'fill': '#ffe6cc', 'stroke': '#d6b656'},  # TMS
    'purple': {'fill': '#e1d5e7', 'stroke': '#9673a6'},  # BMS
    'red':    {'fill': '#f8cecc', 'stroke': '#b85450'},  # 异常路径
}

DEFAULT_COLOR = {'fill': '#ffffff', 'stroke': '#000000'}

# 语义样式 → 颜色覆盖
STYLE_COLORS = {
    'error':     {'fill': '#f8cecc', 'stroke': '#b85450'},
    'highlight': {'fill': '#fff2cc', 'stroke': '#d6b656'},
}

# =============================================================================
# 节点尺寸
# =============================================================================

DEFAULT_NODE_SIZES = {
    'process':    (120, 60),
    'decision':   (100, 60),
    'start':      (60, 60),
    'end':        (60, 60),
    'subprocess': (120, 60),
    'database':   (120, 60),
    'document':   (120, 60),
}

# 每个中文字符约 14px 宽（12pt 字体），英文约 7px
CHAR_WIDTH_CJK = 14
CHAR_WIDTH_ASCII = 7
NODE_PADDING = 20  # 节点内边距（左右各 10px）


def _estimate_label_width(label):
    """估算标签渲染宽度（px）。"""
    width = 0
    for ch in label:
        if ord(ch) > 127:
            width += CHAR_WIDTH_CJK
        else:
            width += CHAR_WIDTH_ASCII
    return width + NODE_PADDING


def get_node_size(node):
    """根据节点类型和标签长度计算节点尺寸，长标签自动加宽。
    菱形节点可用文字区域约为外接矩形的50%，因此宽度需要额外补偿。"""
    ntype = node.get('type', 'process')
    default_w, default_h = DEFAULT_NODE_SIZES.get(ntype, (120, 60))
    label = node.get('label', '')
    label_width = _estimate_label_width(label)
    # 菱形节点可用面积小，宽度乘以 1.4 补偿
    if ntype == 'decision':
        label_width = int(label_width * 1.4)
    w = max(default_w, label_width)
    return (w, default_h)


# 兼容旧引用
NODE_SIZES = DEFAULT_NODE_SIZES

# =============================================================================
# 布局参数 — 泳道图（泳道横向排列为列，流程从上往下）
# =============================================================================

LANE_MIN_WIDTH = 200          # 每条泳道列的最小宽度
LANE_HEADER_HEIGHT = 30       # 泳道标题栏高度（列顶部）
LANE_CONTENT_PADDING = 20     # 泳道内容区左右内边距
ROW_HEIGHT = 100              # 节点行间距（垂直）
ROW_TOP_PADDING = 20          # 泳道标题与首行节点间距
ROW_BOTTOM_PADDING = 30       # 末行节点与泳道底部间距
NODE_X_GAP = 20               # 同行多节点水平间距
DIAGRAM_MARGIN = 20           # 图表外边距
TITLE_HEIGHT = 40             # 图表标题高度

# 布局参数 — 普通流程图（无泳道）
FLOW_H_SPACING = 160
FLOW_V_SPACING = 100


# =============================================================================
# 校验
# =============================================================================

def validate(data):
    """校验 YAML 结构完整性，返回 (errors, warnings) 二元组。"""
    errors = []
    warnings = []

    diagram = data.get('diagram', {})
    if not diagram.get('title'):
        errors.append("diagram.title 不能为空")
    dtype = diagram.get('type')
    if dtype not in ('swimlane', 'flow'):
        errors.append(f"diagram.type 必须为 swimlane 或 flow，当前: {dtype}")

    lanes = data.get('lanes', [])
    nodes = data.get('nodes', [])
    edges = data.get('edges', [])

    # ID 唯一性
    lane_ids = set()
    for lane in lanes:
        lid = lane.get('id')
        if not lid:
            errors.append("存在缺少 id 的泳道")
        elif lid in lane_ids:
            errors.append(f"泳道 ID 重复: {lid}")
        else:
            lane_ids.add(lid)

    node_ids = set()
    for node in nodes:
        nid = node.get('id')
        if not nid:
            errors.append("存在缺少 id 的节点")
        elif nid in node_ids:
            errors.append(f"节点 ID 重复: {nid}")
        else:
            node_ids.add(nid)
        if not node.get('label'):
            errors.append(f"节点 {nid} 缺少 label")
        if not node.get('type'):
            errors.append(f"节点 {nid} 缺少 type")

    # 泳道引用完整性
    if dtype == 'swimlane':
        if not lanes:
            errors.append("swimlane 类型必须定义 lanes")
        for node in nodes:
            nlane = node.get('lane')
            if not nlane:
                errors.append(f"swimlane 模式下节点 {node.get('id')} 缺少 lane")
            elif nlane not in lane_ids:
                errors.append(f"节点 {node.get('id')} 引用了不存在的泳道: {nlane}")

    # 边引用完整性
    for i, edge in enumerate(edges):
        efrom = edge.get('from')
        eto = edge.get('to')
        if not efrom or not eto:
            errors.append(f"第 {i+1} 条边缺少 from 或 to")
        else:
            if efrom not in node_ids:
                errors.append(f"边的 from 引用了不存在的节点: {efrom}")
            if eto not in node_ids:
                errors.append(f"边的 to 引用了不存在的节点: {eto}")

    # 判断节点出边检查
    decision_out = defaultdict(int)
    for edge in edges:
        decision_out[edge.get('from')] += 1
    for node in nodes:
        if node.get('type') == 'decision':
            nid = node.get('id')
            if decision_out.get(nid, 0) < 2:
                errors.append(f"decision 节点 {nid} 至少需要 2 条出边，当前 {decision_out.get(nid, 0)} 条")

    # 循环依赖检测 (T-1)
    if nodes and edges:
        adj = defaultdict(list)
        in_deg_check = defaultdict(int)
        all_node_ids = [n.get('id') for n in nodes if n.get('id')]
        for nid in all_node_ids:
            in_deg_check[nid] = 0
        for edge in edges:
            efrom, eto = edge.get('from'), edge.get('to')
            if efrom and eto and efrom in set(all_node_ids) and eto in set(all_node_ids):
                adj[efrom].append(eto)
                in_deg_check[eto] += 1
        queue = deque([nid for nid in all_node_ids if in_deg_check[nid] == 0])
        visited_count = 0
        while queue:
            nid = queue.popleft()
            visited_count += 1
            for neighbor in adj[nid]:
                in_deg_check[neighbor] -= 1
                if in_deg_check[neighbor] == 0:
                    queue.append(neighbor)
        if visited_count < len(all_node_ids):
            cycle_nodes = [nid for nid in all_node_ids
                           if in_deg_check.get(nid, 0) > 0]
            errors.append(f"检测到循环连线，涉及节点: {', '.join(cycle_nodes)}")

    # 节点数量警告 (T-3)
    if len(nodes) > 20:
        warnings.append(f"节点数 ({len(nodes)}) 超过20，建议拆分为多个子图以提高可读性")

    # 节点标签长度检查 (T-2)
    for node in nodes:
        label = node.get('label', '')
        if len(label) > 10:
            nid = node.get('id', '?')
            warnings.append(f"节点 {nid} 标签 \"{label}\" 超过10字符，可能溢出节点框")

    return errors, warnings


# =============================================================================
# 拓扑排序
# =============================================================================

def topo_sort_nodes(nodes, edges):
    """对节点进行拓扑排序，返回节点 ID → 拓扑层级的映射。"""
    adj = defaultdict(list)
    in_deg = defaultdict(int)
    node_ids = [n['id'] for n in nodes]

    for nid in node_ids:
        in_deg[nid] = 0

    for edge in edges:
        adj[edge['from']].append(edge['to'])
        in_deg[edge['to']] += 1

    queue = deque([nid for nid in node_ids if in_deg[nid] == 0])
    level_map = {}
    while queue:
        nid = queue.popleft()
        predecessors = [level_map[e['from']] for e in edges
                        if e['to'] == nid and e['from'] in level_map]
        level_map[nid] = (max(predecessors) + 1) if predecessors else 0
        for neighbor in adj[nid]:
            in_deg[neighbor] -= 1
            if in_deg[neighbor] == 0:
                queue.append(neighbor)

    # 处理未排到的节点（环或孤立）
    for nid in node_ids:
        if nid not in level_map:
            level_map[nid] = 0

    return level_map


# =============================================================================
# 布局计算
# =============================================================================

def compute_layout(data):
    """计算所有元素的坐标。

    泳道图: 泳道横向排列（列），流程从上往下。
    返回 (node_positions, lane_geometries, diagram_info)
      - node_positions: node_id → (rel_x, rel_y, w, h) 相对于所属泳道
      - lane_geometries: lane_id → (abs_x, abs_y, w, h)
      - diagram_info: dict with total_width, total_height
    """
    dtype = data['diagram'].get('type', 'flow')
    lanes = data.get('lanes', [])
    nodes = data.get('nodes', [])
    edges = data.get('edges', [])

    level_map = topo_sort_nodes(nodes, edges)
    max_level = max(level_map.values(), default=0)

    node_positions = {}

    if dtype == 'swimlane':
        # ── 泳道横向排列（每条泳道是一个列，流程从上往下）──

        # 按泳道分组节点
        lane_nodes = defaultdict(list)
        for node in nodes:
            lane_nodes[node['lane']].append(node)

        # 计算每条泳道列宽度（取决于同一行最多有几个节点并排）
        lane_widths = {}
        for lane in lanes:
            lid = lane['id']
            row_counts = defaultdict(int)
            for node in lane_nodes.get(lid, []):
                row_counts[level_map[node['id']]] += 1
            max_per_row = max(row_counts.values(), default=1)
            max_nw = max((get_node_size(n)[0]
                          for n in lane_nodes.get(lid, [])), default=120)
            needed = max_per_row * max_nw + (max_per_row - 1) * NODE_X_GAP + LANE_CONTENT_PADDING * 2
            lane_widths[lid] = max(LANE_MIN_WIDTH, int(needed))

        # 泳道列位置（横向排列）
        lane_geometries = {}
        lx = DIAGRAM_MARGIN
        ly = DIAGRAM_MARGIN + TITLE_HEIGHT
        lane_height = int(LANE_HEADER_HEIGHT + ROW_TOP_PADDING
                          + (max_level + 1) * ROW_HEIGHT + ROW_BOTTOM_PADDING)

        for lane in lanes:
            lid = lane['id']
            w = lane_widths[lid]
            lane_geometries[lid] = (lx, ly, w, lane_height)
            lx += w

        total_width = lx + DIAGRAM_MARGIN
        total_height = ly + lane_height + DIAGRAM_MARGIN

        # 节点相对位置（相对于所属泳道左上角）
        for lane in lanes:
            lid = lane['id']
            lw = lane_widths[lid]

            row_groups = defaultdict(list)
            for node in lane_nodes.get(lid, []):
                row = level_map[node['id']]
                row_groups[row].append(node)

            for row, row_nodes_list in row_groups.items():
                n_count = len(row_nodes_list)
                for i, node in enumerate(row_nodes_list):
                    nw, nh = get_node_size(node)
                    # 水平：在泳道列内居中
                    total_w = n_count * nw + (n_count - 1) * NODE_X_GAP
                    start_x = (lw - total_w) / 2
                    rel_x = int(start_x + i * (nw + NODE_X_GAP))
                    # 垂直：按拓扑层级排列
                    rel_y = int(LANE_HEADER_HEIGHT + ROW_TOP_PADDING
                                + row * ROW_HEIGHT + (ROW_HEIGHT - nh) / 2)
                    node_positions[node['id']] = (rel_x, rel_y, nw, nh)

        diagram_info = {
            'total_width': total_width,
            'total_height': total_height,
        }

    else:
        # ── 普通流程图: 从左到右按拓扑排列 ──
        lane_geometries = {}

        col_row_counter = defaultdict(int)
        for node in nodes:
            nid = node['id']
            col = level_map[nid]
            row = col_row_counter[col]
            col_row_counter[col] += 1

            nw, nh = get_node_size(node)
            rel_x = int(DIAGRAM_MARGIN + col * FLOW_H_SPACING + (FLOW_H_SPACING - nw) / 2)
            rel_y = int(DIAGRAM_MARGIN + row * FLOW_V_SPACING + (FLOW_V_SPACING - nh) / 2)
            node_positions[nid] = (rel_x, rel_y, nw, nh)

        max_col = max(level_map.values(), default=0)
        max_rows = max(col_row_counter.values(), default=1)
        diagram_info = {
            'total_width': DIAGRAM_MARGIN * 2 + (max_col + 1) * FLOW_H_SPACING,
            'total_height': DIAGRAM_MARGIN * 2 + max_rows * FLOW_V_SPACING,
        }

    return node_positions, lane_geometries, diagram_info


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
    else:
        fill = DEFAULT_COLOR['fill']
        stroke = DEFAULT_COLOR['stroke']

    base = f"fillColor={fill};strokeColor={stroke};fontFamily=Microsoft YaHei;fontSize=12;"

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


def edge_style(edge_data):
    """根据边样式生成 draw.io style 字符串。"""
    estyle = edge_data.get('style')
    base = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;"
    base += "fontFamily=Microsoft YaHei;fontSize=11;"

    if estyle == 'error':
        return base + f"strokeColor={COLORS['red']['stroke']};strokeWidth=2;"
    elif estyle == 'async':
        return base + "dashed=1;dashPattern=8 4;"
    else:
        return base


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
        title_style = ("text;html=1;align=center;verticalAlign=middle;resizable=0;"
                        "points=[];autosize=0;fontStyle=1;fontSize=16;"
                        "fontFamily=Microsoft YaHei;")
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
                lane_fill = '#ffffff'
                lane_stroke = '#000000'

            lane_style = (f"swimlane;startSize={LANE_HEADER_HEIGHT};horizontal=1;"
                          f"fillColor={lane_fill};strokeColor={lane_stroke};"
                          f"fontFamily=Microsoft YaHei;fontSize=12;fontStyle=1;"
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

            lane_color = (lane_map[node['lane']].get('color')
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
    for edge_data in edges:
        efrom = edge_data['from']
        eto = edge_data['to']
        if efrom not in node_cell_ids or eto not in node_cell_ids:
            continue
        ecid = cell_id
        cell_id += 1

        estyle = edge_style(edge_data)
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

    # 布局计算
    node_positions, lane_geometries, diagram_info = compute_layout(data)

    # 生成 XML
    xml = generate_xml(data, node_positions, lane_geometries, diagram_info)

    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml)

    print(f"✓ 已生成: {output_path}")


if __name__ == '__main__':
    main()
