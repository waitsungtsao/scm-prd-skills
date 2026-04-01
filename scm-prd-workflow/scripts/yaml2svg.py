#!/usr/bin/env python3
"""
yaml2svg.py — 将 YAML 图表 DSL 转换为 SVG 矢量图

复用 yaml2drawio.py 的布局引擎，输出 SVG 格式。支持泳道图、流程图、ER 图。
可选输出 PNG（需 cairosvg）。

用法:
    python yaml2svg.py <input.diagram.yaml>              # → .svg
    python yaml2svg.py <input.diagram.yaml> --png         # → .svg + .png
    python yaml2svg.py <input.diagram.yaml> -o out.svg    # 指定输出路径

依赖: PyYAML (pip install pyyaml)
可选: cairosvg (pip install cairosvg) — 用于 PNG 转换
兼容: Python 3.8+
"""

import sys
import os
import argparse
from xml.sax.saxutils import escape

# 复用 yaml2drawio.py 的布局引擎
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from yaml2drawio import (
    validate, compute_layout, get_node_size,
    COLORS, DEFAULT_COLOR, DEFAULT_LANE_COLOR, STYLE_COLORS,
    LANE_HEADER_HEIGHT, DIAGRAM_MARGIN, TITLE_HEIGHT,
)

# SVG 版默认泳道色（与 yaml2drawio.py DEFAULT_LANE_COLOR 对应）
_DEFAULT_LANE_FILL = DEFAULT_LANE_COLOR['fill']
_DEFAULT_LANE_STROKE = DEFAULT_LANE_COLOR['stroke']

try:
    import yaml
except ImportError:
    print("错误: 需要 PyYAML 库。请运行: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# =============================================================================
# SVG 字体与尺寸
# =============================================================================

# CJK 字体候选列表（按优先级）。cairosvg 使用 fontconfig 解析字体名，
# 不像浏览器那样做字符级 fallback：如果第一个字体匹配到不支持中文的西文字体
# （如 "Microsoft YaHei" 在 macOS 上匹配为 Verdana），中文全部显示为方框。
# 因此必须在运行时检测，把真正可用的 CJK 字体放在最前面。
_CJK_FONT_CANDIDATES = [
    "PingFang SC",          # macOS 内置
    "Microsoft YaHei",      # Windows 内置
    "Noto Sans CJK SC",     # Linux / 手动安装
    "Source Han Sans",       # Adobe 版思源黑体
    "Heiti SC",              # macOS 备选
    "WenQuanYi Micro Hei",  # Linux 常见
    "SimHei",               # Windows 备选
]


def _detect_cjk_font():
    """检测系统中可用的 CJK 字体，返回排好序的 font-family 字符串。

    通过 fontconfig (fc-match) 验证每个候选字体是否真正映射到 CJK 字体
    （而非 fallback 到 Verdana 等西文字体）。
    """
    import subprocess as _sp

    verified = []
    for candidate in _CJK_FONT_CANDIDATES:
        try:
            r = _sp.run(
                ["fc-match", "--format=%{family}", candidate],
                capture_output=True, text=True, timeout=3,
            )
            matched = r.stdout.strip().split(",")[0].strip()
            # 只有 fc-match 返回的字体名与候选名一致才算可用
            if matched.lower() == candidate.lower():
                verified.append(candidate)
        except (FileNotFoundError, _sp.TimeoutExpired, OSError):
            pass

    if not verified:
        # fc-match 不可用或全部未命中 — 按平台猜测
        import platform
        _sys = platform.system()
        if _sys == "Darwin":
            verified = ["PingFang SC", "Heiti SC"]
        elif _sys == "Windows":
            verified = ["Microsoft YaHei", "SimHei"]
        else:
            verified = ["Noto Sans CJK SC", "WenQuanYi Micro Hei"]

    # 拼接 font-family: 已验证的 CJK 字体 + 通用 sans-serif
    return ", ".join(verified + ["sans-serif"])


FONT_FAMILY = _detect_cjk_font()
FONT_SIZE = 12
FONT_SIZE_SMALL = 11
FONT_SIZE_TITLE = 16
ARROW_MARKER_ID = "arrowhead"


# =============================================================================
# SVG 形状渲染
# =============================================================================

def _svg_node(node, abs_x, abs_y, nw, nh, fill, stroke):
    """渲染单个节点为 SVG 元素字符串。"""
    ntype = node.get('type', 'process')
    label = escape(node.get('label', ''))
    cx, cy = abs_x + nw / 2, abs_y + nh / 2
    elements = []

    if ntype == 'decision':
        # 菱形
        points = f"{cx},{abs_y} {abs_x + nw},{cy} {cx},{abs_y + nh} {abs_x},{cy}"
        elements.append(f'  <polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    elif ntype == 'start':
        r = min(nw, nh) / 2
        elements.append(f'  <circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    elif ntype == 'end':
        r = min(nw, nh) / 2
        elements.append(f'  <circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="3"/>')
    elif ntype == 'database':
        # 圆柱体：顶部椭圆 + 矩形 + 底部椭圆弧
        ry = 10
        elements.append(f'  <path d="M{abs_x},{abs_y + ry} '
                        f'L{abs_x},{abs_y + nh - ry} '
                        f'A{nw / 2},{ry} 0 0,0 {abs_x + nw},{abs_y + nh - ry} '
                        f'L{abs_x + nw},{abs_y + ry}" '
                        f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        elements.append(f'  <ellipse cx="{cx}" cy="{abs_y + ry}" rx="{nw / 2}" ry="{ry}" '
                        f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    elif ntype == 'document':
        # 波浪底矩形
        wave = 8
        elements.append(f'  <path d="M{abs_x},{abs_y} L{abs_x + nw},{abs_y} '
                        f'L{abs_x + nw},{abs_y + nh - wave} '
                        f'Q{abs_x + nw * 0.75},{abs_y + nh + wave} {cx},{abs_y + nh - wave} '
                        f'Q{abs_x + nw * 0.25},{abs_y + nh - wave * 3} {abs_x},{abs_y + nh - wave} Z" '
                        f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    elif ntype == 'subprocess':
        # 双边矩形
        elements.append(f'  <rect x="{abs_x}" y="{abs_y}" width="{nw}" height="{nh}" '
                        f'rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        inset = 6
        elements.append(f'  <line x1="{abs_x + inset}" y1="{abs_y}" x2="{abs_x + inset}" y2="{abs_y + nh}" '
                        f'stroke="{stroke}" stroke-width="1"/>')
        elements.append(f'  <line x1="{abs_x + nw - inset}" y1="{abs_y}" x2="{abs_x + nw - inset}" y2="{abs_y + nh}" '
                        f'stroke="{stroke}" stroke-width="1"/>')
    else:
        # process: 圆角矩形
        elements.append(f'  <rect x="{abs_x}" y="{abs_y}" width="{nw}" height="{nh}" '
                        f'rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')

    # 文字标签
    elements.append(f'  <text x="{cx}" y="{cy}" text-anchor="middle" dominant-baseline="central" '
                    f'font-family="{FONT_FAMILY}" font-size="{FONT_SIZE}" fill="#333">{label}</text>')

    return '\n'.join(elements)


def _get_node_color(node, lane_map=None):
    """获取节点颜色，考虑语义样式和泳道颜色。"""
    nstyle = node.get('style')
    if nstyle and nstyle in STYLE_COLORS:
        return STYLE_COLORS[nstyle]['fill'], STYLE_COLORS[nstyle]['stroke']
    lane_id = node.get('lane')
    if lane_id and lane_map and lane_id in lane_map:
        color_name = lane_map[lane_id].get('color')
        if color_name and color_name in COLORS:
            return COLORS[color_name]['fill'], COLORS[color_name]['stroke']
        # 泳道未指定颜色 → 使用默认泳道色
        return _DEFAULT_LANE_FILL, _DEFAULT_LANE_STROKE
    return DEFAULT_COLOR['fill'], DEFAULT_COLOR['stroke']


def _svg_edge(edge, node_positions, lane_geometries, node_map, lane_map):
    """渲染单条连线为 SVG 折线。"""
    efrom, eto = edge['from'], edge['to']
    if efrom not in node_positions or eto not in node_positions:
        return ''

    # 计算绝对坐标
    def abs_center(nid):
        rx, ry, nw, nh = node_positions[nid]
        node = node_map[nid]
        lane_id = node.get('lane')
        ox, oy = 0, 0
        if lane_id and lane_id in lane_geometries:
            ox, oy = lane_geometries[lane_id][0], lane_geometries[lane_id][1]
        return ox + rx + nw / 2, oy + ry + nh / 2, nw, nh

    sx, sy, sw, sh = abs_center(efrom)
    tx, ty, tw, th = abs_center(eto)

    # 连接点：从源节点边缘到目标节点边缘
    if abs(ty - sy) > abs(tx - sx):
        # 主要是垂直方向
        if ty > sy:
            y1, y2 = sy + sh / 2, ty - th / 2
        else:
            y1, y2 = sy - sh / 2, ty + th / 2
        points = f"{sx},{y1} {sx},{(y1 + y2) / 2} {tx},{(y1 + y2) / 2} {tx},{y2}"
    else:
        # 主要是水平方向
        if tx > sx:
            x1, x2 = sx + sw / 2, tx - tw / 2
        else:
            x1, x2 = sx - sw / 2, tx + tw / 2
        points = f"{x1},{sy} {(x1 + x2) / 2},{sy} {(x1 + x2) / 2},{ty} {x2},{ty}"

    estyle = edge.get('style', '')
    stroke_color = '#b85450' if estyle == 'error' else '#666'
    stroke_width = 2 if estyle == 'error' else 1.5
    dash = ' stroke-dasharray="8,4"' if estyle == 'async' else ''

    elements = []
    elements.append(f'  <polyline points="{points}" fill="none" stroke="{stroke_color}" '
                    f'stroke-width="{stroke_width}"{dash} marker-end="url(#{ARROW_MARKER_ID})"/>')

    # 边标签
    label = edge.get('label', '')
    if label:
        # 标签放在连线中点
        mid_x = (sx + tx) / 2
        mid_y = (sy + ty) / 2
        # 如果是垂直线段上的中点，偏移到右侧
        if abs(sx - tx) < 20:
            mid_x += 15
        elements.append(f'  <text x="{mid_x}" y="{mid_y - 6}" text-anchor="middle" '
                        f'font-family="{FONT_FAMILY}" font-size="{FONT_SIZE_SMALL}" fill="{stroke_color}">'
                        f'{escape(label)}</text>')

    return '\n'.join(elements)


# =============================================================================
# SVG 生成 — 泳道图 & 流程图
# =============================================================================

def generate_svg(data, node_positions, lane_geometries, diagram_info):
    """生成泳道图或流程图的 SVG 字符串。"""
    dtype = data['diagram'].get('type', 'flow')
    title = data['diagram'].get('title', '')
    lanes = data.get('lanes', [])
    nodes = data.get('nodes', [])
    edges = data.get('edges', [])

    tw = diagram_info['total_width']
    th = diagram_info['total_height']
    lane_map = {l['id']: l for l in lanes}
    node_map = {n['id']: n for n in nodes}

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{tw}" height="{th}" '
                 f'viewBox="0 0 {tw} {th}">')
    lines.append(f'<rect width="{tw}" height="{th}" fill="white"/>')

    # 箭头标记定义
    lines.append('<defs>')
    lines.append(f'  <marker id="{ARROW_MARKER_ID}" markerWidth="10" markerHeight="7" '
                 f'refX="10" refY="3.5" orient="auto">')
    lines.append(f'    <polygon points="0 0, 10 3.5, 0 7" fill="#666"/>')
    lines.append(f'  </marker>')
    lines.append('</defs>')

    # 标题
    if title:
        lines.append(f'<text x="{tw / 2}" y="{DIAGRAM_MARGIN + TITLE_HEIGHT / 2}" '
                     f'text-anchor="middle" dominant-baseline="central" '
                     f'font-family="{FONT_FAMILY}" font-size="{FONT_SIZE_TITLE}" '
                     f'font-weight="bold" fill="#333">{escape(title)}</text>')

    # 泳道容器
    if dtype == 'swimlane' and lane_geometries:
        for lane in lanes:
            lid = lane['id']
            lx, ly, lw, lh = lane_geometries[lid]
            color_name = lane.get('color')
            if color_name and color_name in COLORS:
                fill = COLORS[color_name]['fill']
                stroke = COLORS[color_name]['stroke']
            else:
                fill = _DEFAULT_LANE_FILL
                stroke = _DEFAULT_LANE_STROKE
            # 泳道背景
            lines.append(f'<rect x="{lx}" y="{ly}" width="{lw}" height="{lh}" '
                         f'fill="{fill}" stroke="{stroke}" stroke-width="1" opacity="0.3"/>')
            # 泳道标题栏
            lines.append(f'<rect x="{lx}" y="{ly}" width="{lw}" height="{LANE_HEADER_HEIGHT}" '
                         f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
            lines.append(f'<text x="{lx + lw / 2}" y="{ly + LANE_HEADER_HEIGHT / 2}" '
                         f'text-anchor="middle" dominant-baseline="central" '
                         f'font-family="{FONT_FAMILY}" font-size="{FONT_SIZE}" '
                         f'font-weight="bold" fill="#333">{escape(lane["label"])}</text>')

    # 连线（先画，节点覆盖在上面）
    for edge in edges:
        svg = _svg_edge(edge, node_positions, lane_geometries, node_map, lane_map)
        if svg:
            lines.append(svg)

    # 节点
    for node in nodes:
        nid = node['id']
        if nid not in node_positions:
            continue
        rx, ry, nw, nh = node_positions[nid]
        # 转换为绝对坐标
        lane_id = node.get('lane')
        ox, oy = 0, 0
        if lane_id and lane_id in lane_geometries:
            ox, oy = lane_geometries[lane_id][0], lane_geometries[lane_id][1]
        abs_x, abs_y = ox + rx, oy + ry
        fill, stroke = _get_node_color(node, lane_map)
        lines.append(_svg_node(node, abs_x, abs_y, nw, nh, fill, stroke))

    lines.append('</svg>')
    return '\n'.join(lines)


# =============================================================================
# SVG 生成 — ER 图
# =============================================================================

def generate_er_svg(data):
    """生成 ER 图的 SVG 字符串。"""
    entities = data.get('entities', [])
    relationships = data.get('relationships', [])
    title = data['diagram'].get('title', 'ER Diagram')

    col_count = max(2, min(4, len(entities)))
    entity_width = 220
    margin_x, margin_y = 60, 60
    header_h, field_h = 30, 24
    title_h = 40
    margin = 30  # 外边距（含底部安全区防截断）

    max_fields = max((len(e.get('fields', [])) for e in entities), default=3)
    entity_max_h = header_h + max_fields * field_h + 8

    rows_needed = (len(entities) + col_count - 1) // col_count
    total_w = margin * 2 + col_count * (entity_width + margin_x)
    total_h = margin * 2 + title_h + margin_y // 2 + rows_needed * (entity_max_h + margin_y) + 20

    # 计算每个实体的位置和实际高度
    entity_positions = {}
    for idx, entity in enumerate(entities):
        col = idx % col_count
        row = idx // col_count
        x = margin + col * (entity_width + margin_x)
        y = margin + title_h + margin_y // 2 + row * (entity_max_h + margin_y)
        fields = entity.get('fields', [])
        eh = header_h + len(fields) * field_h + 8
        entity_positions[entity['id']] = (x, y, entity_width, eh)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}" '
                 f'viewBox="0 0 {total_w} {total_h}">')
    lines.append(f'<rect width="{total_w}" height="{total_h}" fill="white"/>')

    # 箭头
    lines.append('<defs>')
    lines.append(f'  <marker id="{ARROW_MARKER_ID}" markerWidth="10" markerHeight="7" '
                 f'refX="10" refY="3.5" orient="auto">')
    lines.append(f'    <polygon points="0 0, 10 3.5, 0 7" fill="#666"/>')
    lines.append(f'  </marker>')
    lines.append('</defs>')

    # 标题
    lines.append(f'<text x="{total_w / 2}" y="{margin + title_h / 2}" '
                 f'text-anchor="middle" dominant-baseline="central" '
                 f'font-family="{FONT_FAMILY}" font-size="{FONT_SIZE_TITLE}" '
                 f'font-weight="bold" fill="#333">{escape(title)}</text>')

    # 关系连线（先画）
    cardinality = {'1:1': ('1', '1'), '1:N': ('1', '*'), 'N:1': ('*', '1'), 'N:M': ('*', '*')}
    for rel in relationships:
        rfrom, rto = rel.get('from'), rel.get('to')
        if rfrom not in entity_positions or rto not in entity_positions:
            continue
        fx, fy, fw, fh = entity_positions[rfrom]
        tx, ty, tw_, th_ = entity_positions[rto]
        # 连线从源实体右侧中点到目标实体左侧中点
        x1, y1 = fx + fw, fy + fh / 2
        x2, y2 = tx, ty + th_ / 2
        if x1 > x2:
            x1, x2 = fx, tx + tw_
        mid_x = (x1 + x2) / 2
        lines.append(f'<polyline points="{x1},{y1} {mid_x},{y1} {mid_x},{y2} {x2},{y2}" '
                     f'fill="none" stroke="#666" stroke-width="1.5" marker-end="url(#{ARROW_MARKER_ID})"/>')
        # 关系标签
        rlabel = rel.get('label', '')
        if rlabel:
            lines.append(f'<text x="{mid_x}" y="{(y1 + y2) / 2 - 8}" text-anchor="middle" '
                         f'font-family="{FONT_FAMILY}" font-size="{FONT_SIZE_SMALL}" fill="#666">'
                         f'{escape(rlabel)}</text>')
        # 基数标签
        rtype = rel.get('type', '1:N')
        src_c, tgt_c = cardinality.get(rtype, ('', ''))
        if src_c:
            lines.append(f'<text x="{x1 + (5 if x1 < x2 else -15)}" y="{y1 - 8}" '
                         f'font-family="{FONT_FAMILY}" font-size="10" fill="#999">{src_c}</text>')
        if tgt_c:
            lines.append(f'<text x="{x2 + (-15 if x1 < x2 else 5)}" y="{y2 - 8}" '
                         f'font-family="{FONT_FAMILY}" font-size="10" fill="#999">{tgt_c}</text>')

    # 实体
    for entity in entities:
        eid = entity['id']
        x, y, ew, eh = entity_positions[eid]
        fields = entity.get('fields', [])
        color_name = entity.get('color')
        if color_name and color_name in COLORS:
            fill = COLORS[color_name]['fill']
            stroke = COLORS[color_name]['stroke']
        else:
            fill = '#dae8fc'
            stroke = '#6c8ebf'

        # 实体外框
        lines.append(f'<rect x="{x}" y="{y}" width="{ew}" height="{eh}" '
                     f'fill="white" stroke="{stroke}" stroke-width="1.5" rx="4"/>')
        # 标题栏
        lines.append(f'<rect x="{x}" y="{y}" width="{ew}" height="{header_h}" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="1.5" rx="4"/>')
        # 标题栏底部直角（覆盖圆角）
        lines.append(f'<rect x="{x}" y="{y + header_h - 4}" width="{ew}" height="4" '
                     f'fill="{fill}" stroke="none"/>')
        lines.append(f'<line x1="{x}" y1="{y + header_h}" x2="{x + ew}" y2="{y + header_h}" '
                     f'stroke="{stroke}" stroke-width="1.5"/>')
        # 实体标题
        lines.append(f'<text x="{x + ew / 2}" y="{y + header_h / 2}" text-anchor="middle" '
                     f'dominant-baseline="central" font-family="{FONT_FAMILY}" '
                     f'font-size="{FONT_SIZE}" font-weight="bold" fill="#333">'
                     f'{escape(entity.get("label", eid))}</text>')
        # 字段
        for i, field in enumerate(fields):
            fy = y + header_h + 4 + i * field_h
            pk_mark = "PK " if field.get('pk') else ("FK " if field.get('fk') else "")
            field_text = f"{pk_mark}{field.get('name', '')} : {field.get('type', '')}"
            comment = field.get('comment', '')
            lines.append(f'<text x="{x + 8}" y="{fy + field_h / 2}" dominant-baseline="central" '
                         f'font-family="{FONT_FAMILY}" font-size="{FONT_SIZE_SMALL}" fill="#333">'
                         f'{escape(field_text)}</text>')
            if comment:
                lines.append(f'<text x="{x + ew - 8}" y="{fy + field_h / 2}" text-anchor="end" '
                             f'dominant-baseline="central" font-family="{FONT_FAMILY}" '
                             f'font-size="10" fill="#999">{escape(comment)}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# =============================================================================
# PNG 转换
# =============================================================================

def svg_to_png(svg_path, png_path, scale=2):
    """使用 cairosvg 将 SVG 转换为 PNG。"""
    try:
        import cairosvg
    except ImportError:
        print("警告: cairosvg 未安装，跳过 PNG 生成。安装: pip install cairosvg", file=sys.stderr)
        return False
    cairosvg.svg2png(url=svg_path, write_to=png_path, scale=scale)
    return True


# =============================================================================
# 主函数
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='YAML 图表 DSL → SVG 转换器')
    parser.add_argument('input', help='输入 .diagram.yaml 文件路径')
    parser.add_argument('-o', '--output', help='输出 SVG 文件路径')
    parser.add_argument('--png', action='store_true', help='同时生成 PNG (需 cairosvg)')
    parser.add_argument('--scale', type=float, default=2, help='PNG 缩放倍数 (默认 2)')
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"错误: 文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)

    with open(args.input, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    if not data or not isinstance(data, dict):
        print("错误: YAML 文件为空或格式错误", file=sys.stderr)
        sys.exit(1)

    # 校验
    errors, warnings = validate(data)
    if warnings:
        for w in warnings:
            print(f"  ⚠ {w}", file=sys.stderr)
    if errors:
        print("YAML 校验失败:", file=sys.stderr)
        for e in errors:
            print(f"  ✗ {e}", file=sys.stderr)
        sys.exit(1)

    # 确定输出路径
    if args.output:
        svg_path = args.output
    else:
        base = args.input
        if base.endswith('.diagram.yaml'):
            base = base[:-len('.diagram.yaml')]
        elif base.endswith('.yaml') or base.endswith('.yml'):
            base = os.path.splitext(base)[0]
        svg_path = base + '.svg'

    # 生成 SVG
    dtype = data['diagram'].get('type', 'flow')
    if dtype == 'er':
        svg_content = generate_er_svg(data)
    else:
        node_positions, lane_geometries, diagram_info = compute_layout(data)
        svg_content = generate_svg(data, node_positions, lane_geometries, diagram_info)

    with open(svg_path, 'w', encoding='utf-8') as f:
        f.write(svg_content)
    print(f"✓ 已生成 SVG: {svg_path}")

    # PNG 转换
    if args.png:
        png_path = os.path.splitext(svg_path)[0] + '.png'
        if svg_to_png(svg_path, png_path, scale=args.scale):
            print(f"✓ 已生成 PNG: {png_path}")


if __name__ == '__main__':
    main()
