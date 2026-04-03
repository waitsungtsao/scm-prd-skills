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
# draw.io 默认 CJK 字体（draw.io 应用自身支持 CSS font-family fallback，
# 此处为跨平台兼容提供多候选）
DRAWIO_FONT_FAMILY = "PingFang SC,Microsoft YaHei,Noto Sans CJK SC,sans-serif"

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
# 未指定颜色的泳道使用中性灰蓝色，保持视觉一致性
DEFAULT_LANE_COLOR = {'fill': '#f0f0f0', 'stroke': '#b0b0b0'}

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

# 字符宽度估算（12pt 字体基准）
# CJK 全角字符约 14px，ASCII 约 7px，标点/符号按 ASCII 计
CHAR_WIDTH_CJK = 14
CHAR_WIDTH_ASCII = 7
NODE_PADDING = 24  # 节点内边距（左右各 12px，比原来多 4px 做安全余量）


def _estimate_label_width(label):
    """估算标签渲染宽度（px）。
    按 Unicode 区间分类：CJK 统一表意文字及扩展、全角字符用 CJK 宽度，
    其余用 ASCII 宽度。比简单 ord>127 更准确（避免拉丁扩展字符被误判为全角）。"""
    width = 0
    for ch in label:
        cp = ord(ch)
        # CJK Unified Ideographs, CJK Ext-A, CJK Compatibility, Fullwidth Forms,
        # Hangul, Kana, Bopomofo
        if (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF
                or 0xF900 <= cp <= 0xFAFF or 0xFF01 <= cp <= 0xFF60
                or 0x3000 <= cp <= 0x303F or 0x3040 <= cp <= 0x30FF
                or 0xAC00 <= cp <= 0xD7AF):
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
ROW_BOTTOM_PADDING = 50       # 末行节点与泳道底部间距（含边标签/箭头空间）
NODE_X_GAP = 20               # 同行多节点水平间距
DIAGRAM_MARGIN = 30           # 图表外边距（含底部安全区防截断）
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
    if dtype not in ('swimlane', 'flow', 'er'):
        errors.append(f"diagram.type 必须为 swimlane、flow 或 er，当前: {dtype}")

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

    # ER 图专用校验
    if dtype == 'er':
        entities = data.get('entities', [])
        relationships = data.get('relationships', [])
        if not entities:
            errors.append("er 类型必须定义 entities")
        entity_ids = set()
        for entity in entities:
            eid = entity.get('id')
            if not eid:
                errors.append("存在缺少 id 的实体")
            elif eid in entity_ids:
                errors.append(f"实体 ID 重复: {eid}")
            else:
                entity_ids.add(eid)
            if not entity.get('label'):
                errors.append(f"实体 {eid} 缺少 label")
            fields = entity.get('fields', [])
            has_pk = any(f.get('pk') for f in fields)
            if not has_pk and eid:
                errors.append(f"实体 {eid} 至少需要一个 pk: true 字段")
            for field in fields:
                fk_target = field.get('fk')
                if fk_target and fk_target not in entity_ids and fk_target != eid:
                    # 延迟检查：收集所有实体ID后再验证
                    pass
        # FK 引用完整性（第二轮检查）
        for entity in entities:
            for field in entity.get('fields', []):
                fk_target = field.get('fk')
                if fk_target and fk_target not in entity_ids:
                    errors.append(f"实体 {entity.get('id')} 字段 {field.get('name')} 的 fk 引用了不存在的实体: {fk_target}")
        # 关系引用完整性
        for i, rel in enumerate(relationships):
            rfrom = rel.get('from')
            rto = rel.get('to')
            if not rfrom or not rto:
                errors.append(f"第 {i+1} 条关系缺少 from 或 to")
            else:
                if rfrom not in entity_ids:
                    errors.append(f"关系的 from 引用了不存在的实体: {rfrom}")
                if rto not in entity_ids:
                    errors.append(f"关系的 to 引用了不存在的实体: {rto}")
        return errors, warnings

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
        warnings.append(f"T-3 节点数 ({len(nodes)}) 超过20，评估是否仍服务同一表达意图")

    # 节点标签长度检查 (T-2)
    for node in nodes:
        label = node.get('label', '')
        if len(label) > 10:
            nid = node.get('id', '?')
            warnings.append(f"节点 {nid} 标签 \"{label}\" 超过10字符，可能溢出节点框")

    # 结构参考数据 (T-4) — 供 AI 规划参考，不做拆分建议
    multi_out_nodes = []
    for node in nodes:
        nid = node.get('id', '?')
        out_count = sum(1 for e in edges if e.get('from') == nid)
        if out_count > 1:
            multi_out_nodes.append(f"{nid}({out_count}出边)")

    cross_lane_count = 0
    dtype = data.get('diagram', {}).get('type', 'flow')
    if dtype == 'swimlane':
        node_lane = {n['id']: n.get('lane') for n in nodes}
        cross_lane_count = sum(
            1 for e in edges
            if node_lane.get(e.get('from')) != node_lane.get(e.get('to'))
        )

    if multi_out_nodes or cross_lane_count > 3:
        warnings.append(
            f"T-4 结构参考: 多出边节点={', '.join(multi_out_nodes) or '无'}; "
            f"跨泳道边={cross_lane_count}")

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
# 边端口计算（被 yaml2svg.py 和 generate_xml 共用）
# =============================================================================

# 决策分支标签分类 — 匹配时忽略大小写并 strip
_PRIMARY_LABELS = frozenset({
    '是', 'yes', 'y', '通过', '成功', '正常', '一致', '合格', '有',
})
_ALTERNATE_LABELS = frozenset({
    '否', 'no', 'n', '拒绝', '失败', '异常', '差异', '不通过', '不合格',
    '无', '缺货', '超时',
})

# 端口常量：(x, y) 相对于节点 bounding box (0..1)
PORT_BOTTOM = (0.5, 1)
PORT_TOP    = (0.5, 0)
PORT_RIGHT  = (1, 0.5)
PORT_LEFT   = (0, 0.5)


def compute_edge_ports(edges, nodes, node_positions, lane_geometries,
                       is_swimlane=True):
    """为每条边计算 exit/entry 端口坐标。

    根据节点类型、边标签、源/目标位置关系，自动推断最佳连接端口，
    解决决策节点分支重叠和跨泳道连线混乱问题。

    返回: dict{ (from_id, to_id): {'exit': (x,y), 'entry': (x,y)} }
    """
    node_map = {n['id']: n for n in nodes}
    # 每个节点的出边列表（保持 YAML 顺序）
    out_edges = defaultdict(list)
    for edge in edges:
        out_edges[edge['from']].append(edge)

    # 获取节点绝对中心坐标
    def _abs_center(nid):
        if nid not in node_positions:
            return (0, 0)
        rx, ry, nw, nh = node_positions[nid]
        node = node_map.get(nid, {})
        lane_id = node.get('lane')
        ox, oy = 0, 0
        if lane_id and lane_id in lane_geometries:
            ox, oy = lane_geometries[lane_id][0], lane_geometries[lane_id][1]
        return (ox + rx + nw / 2, oy + ry + nh / 2)

    # 获取节点所在泳道的 x 位置（用于判断左/右/同泳道）
    def _lane_x(nid):
        node = node_map.get(nid, {})
        lane_id = node.get('lane')
        if lane_id and lane_id in lane_geometries:
            return lane_geometries[lane_id][0]
        return 0

    def _classify_branch(edge, siblings):
        """分类决策分支：primary / alternate / tertiary。"""
        label = edge.get('label', '').strip().lower()
        if edge.get('style') == 'error':
            return 'alternate'
        if label in _ALTERNATE_LABELS:
            return 'alternate'
        if label in _PRIMARY_LABELS:
            return 'primary'
        # 无法通过标签分类 → 按 YAML 顺序
        idx = next((i for i, e in enumerate(siblings) if e is edge), 0)
        if idx == 0:
            return 'primary'
        elif idx == 1:
            return 'alternate'
        else:
            return 'tertiary'

    port_map = {}

    for edge in edges:
        efrom, eto = edge['from'], edge['to']
        if efrom not in node_positions or eto not in node_positions:
            continue

        source_node = node_map.get(efrom, {})
        siblings = out_edges.get(efrom, [])
        is_decision = source_node.get('type') == 'decision' and len(siblings) >= 2

        # 先算位置关系（exit 端口分配可能需要）
        sx, sy = _abs_center(efrom)
        tx, ty = _abs_center(eto)
        src_lane_x = _lane_x(efrom)
        tgt_lane_x = _lane_x(eto)
        same_lane = (src_lane_x == tgt_lane_x)
        dx, dy = tx - sx, ty - sy

        # ── Exit 端口 ──
        has_multi_out = len(siblings) >= 2

        if is_decision:
            branch = _classify_branch(edge, siblings)
            if branch == 'primary':
                exit_port = PORT_BOTTOM
            elif branch == 'alternate':
                # 根据目标位置决定从哪侧出：目标在右侧→右出，在左侧→左出
                if dx > 0 or same_lane:
                    exit_port = PORT_RIGHT
                else:
                    exit_port = PORT_LEFT
            else:
                # 第三条分支：取 alternate 的反方向
                exit_port = PORT_LEFT if dx > 0 else PORT_RIGHT
        elif has_multi_out:
            # 非决策节点但有多条出边 → 按目标位置分配端口
            if same_lane or abs(dx) < 50:
                exit_port = PORT_BOTTOM  # 同泳道目标：底部出
            elif dx > 0:
                exit_port = PORT_RIGHT   # 右侧泳道目标：右出
            else:
                exit_port = PORT_LEFT    # 左侧泳道目标：左出
        else:
            # 单出边：泳道模式从底部出，流程模式从右侧出
            exit_port = PORT_BOTTOM if is_swimlane else PORT_RIGHT

        if exit_port == PORT_BOTTOM:
            if same_lane or abs(dx) < 50:
                entry_port = PORT_TOP  # 同泳道垂直下行
            elif dx > 0:
                entry_port = PORT_LEFT  # 目标在右侧泳道
            else:
                entry_port = PORT_RIGHT  # 目标在左侧泳道
        elif exit_port == PORT_RIGHT:
            if dx > 0 and not same_lane:
                entry_port = PORT_LEFT  # 向右跨泳道
            elif same_lane and dy > 0:
                entry_port = PORT_TOP  # 同泳道下方
            else:
                entry_port = PORT_TOP if dy > 0 else PORT_BOTTOM
        elif exit_port == PORT_LEFT:
            if dx < 0 and not same_lane:
                entry_port = PORT_RIGHT  # 向左跨泳道
            elif same_lane and dy > 0:
                entry_port = PORT_TOP
            else:
                entry_port = PORT_TOP if dy > 0 else PORT_BOTTOM
        else:  # PORT_TOP（回退边）
            entry_port = PORT_BOTTOM

        port_map[(efrom, eto)] = {'exit': exit_port, 'entry': entry_port}

    # ── 自动修正 pass（顺序重要：先修方向，再修冲突）──

    def _recalc_entry(new_exit, efrom, eto):
        """根据新的 exit 端口重新计算 entry。"""
        sx, sy = _abs_center(efrom)
        tx, ty = _abs_center(eto)
        dx = tx - sx
        if new_exit == PORT_BOTTOM:
            return PORT_TOP if abs(dx) < 50 else (PORT_LEFT if dx > 0 else PORT_RIGHT)
        elif new_exit == PORT_RIGHT:
            return PORT_LEFT if dx > 0 else PORT_TOP
        elif new_exit == PORT_LEFT:
            return PORT_RIGHT if dx < 0 else PORT_TOP
        else:
            return PORT_BOTTOM

    # V-4 修正（先）：exit 方向与目标方向相反 → 翻转 exit
    for (efrom, eto), ports in port_map.items():
        ex, ey = ports['exit']
        sx, sy = _abs_center(efrom)
        tx, ty = _abs_center(eto)
        dx, dy = tx - sx, ty - sy
        evx, evy = ex - 0.5, ey - 0.5
        if evx * dx + evy * dy < -30:
            if abs(dy) > abs(dx):
                new_exit = PORT_BOTTOM if dy > 0 else PORT_TOP
            else:
                new_exit = PORT_RIGHT if dx > 0 else PORT_LEFT
            ports['exit'] = new_exit
            ports['entry'] = _recalc_entry(new_exit, efrom, eto)

    # V-1 修正（后）：同节点同出口的多条边 → 轮转分配不同端口
    _ROTATE_PORTS = [PORT_BOTTOM, PORT_RIGHT, PORT_LEFT, PORT_TOP]
    # 先收集每个源节点已占用的全部出口
    node_used_exits = defaultdict(set)
    for (efrom, eto), ports in port_map.items():
        node_used_exits[efrom].add(ports['exit'])

    exit_usage = defaultdict(list)
    for (efrom, eto), ports in port_map.items():
        exit_usage[(efrom, ports['exit'])].append((efrom, eto))
    for (src, port), keys in exit_usage.items():
        if len(keys) <= 1:
            continue
        # 保留第一条不变，后续轮转到该节点未占用的端口
        for key in keys[1:]:
            for candidate in _ROTATE_PORTS:
                if candidate not in node_used_exits[src]:
                    port_map[key]['exit'] = candidate
                    node_used_exits[src].add(candidate)
                    port_map[key]['entry'] = _recalc_entry(candidate, key[0], key[1])
                    break

    return port_map


def validate_edge_layout(edges, nodes, node_positions, lane_geometries,
                         port_map):
    """校验边布局的几何合理性，返回警告列表。

    校验项（全部为非阻断警告）：
      V-1  同一节点多条出边共用同一 exit 端口 → 线段可能重叠
      V-2  边路径穿越非端点节点的 bounding box → 线段遮挡节点
      V-3  两条边标签坐标距离 <20px → 标签可能重叠
      V-4  exit 方向与目标方向相反（夹角>90°）→ 路径可能绕路
    """
    node_map = {n['id']: n for n in nodes}
    warnings = []

    # 节点绝对 bounding box
    def _abs_bbox(nid):
        if nid not in node_positions:
            return None
        rx, ry, nw, nh = node_positions[nid]
        node = node_map.get(nid, {})
        lane_id = node.get('lane')
        ox, oy = 0, 0
        if lane_id and lane_id in lane_geometries:
            ox, oy = lane_geometries[lane_id][0], lane_geometries[lane_id][1]
        return (ox + rx, oy + ry, nw, nh)

    def _abs_center(nid):
        bb = _abs_bbox(nid)
        if not bb:
            return (0, 0)
        return (bb[0] + bb[2] / 2, bb[1] + bb[3] / 2)

    # ── V-1: 同节点同出口 ──
    from collections import defaultdict
    exit_groups = defaultdict(list)  # (source_id, exit_port) → [edge_labels]
    for (efrom, eto), ports in port_map.items():
        label = ''
        for e in edges:
            if e['from'] == efrom and e['to'] == eto:
                label = e.get('label', '')
                break
        exit_groups[(efrom, ports['exit'])].append(
            f"{efrom}→{eto}" + (f"({label})" if label else ""))
    for (src, port), members in exit_groups.items():
        if len(members) > 1:
            warnings.append(
                f"V-1 同出口: 节点 {src} 的 {len(members)} 条出边共用"
                f" exit={port}: {', '.join(members)}")

    # ── V-2: 边路径穿越节点 ──
    all_bboxes = {}
    for n in nodes:
        bb = _abs_bbox(n['id'])
        if bb:
            all_bboxes[n['id']] = bb

    def _segment_crosses_bbox(x1, y1, x2, y2, bx, by, bw, bh, margin=5):
        """简化检测：轴对齐线段是否穿过 bbox（缩小 margin 避免端点误报）。"""
        bx1, by1 = bx + margin, by + margin
        bx2, by2 = bx + bw - margin, by + bh - margin
        if x1 == x2:  # 垂直线段
            miny, maxy = min(y1, y2), max(y1, y2)
            return bx1 < x1 < bx2 and miny < by2 and maxy > by1
        elif y1 == y2:  # 水平线段
            minx, maxx = min(x1, x2), max(x1, x2)
            return by1 < y1 < by2 and minx < bx2 and maxx > bx1
        return False

    for (efrom, eto), ports in port_map.items():
        bb_src = _abs_bbox(efrom)
        bb_tgt = _abs_bbox(eto)
        if not bb_src or not bb_tgt:
            continue
        # 计算起止点
        ex, ey = ports['exit']
        nx, ny = ports['entry']
        x1 = bb_src[0] + bb_src[2] * ex
        y1 = bb_src[1] + bb_src[3] * ey
        x2 = bb_tgt[0] + bb_tgt[2] * nx
        y2 = bb_tgt[1] + bb_tgt[3] * ny
        # 中间折点（简化：只检查直连线段）
        segments = [(x1, y1, x2, y2)]
        if abs(x1 - x2) > 10 and abs(y1 - y2) > 10:
            mid_y = (y1 + y2) / 2
            segments = [(x1, y1, x1, mid_y), (x1, mid_y, x2, mid_y),
                        (x2, mid_y, x2, y2)]
        for nid, bb in all_bboxes.items():
            if nid in (efrom, eto):
                continue
            for sx1, sy1, sx2, sy2 in segments:
                if _segment_crosses_bbox(sx1, sy1, sx2, sy2, *bb):
                    warnings.append(
                        f"V-2 穿越: 边 {efrom}→{eto} 的路径可能穿过节点 {nid}")
                    break

    # ── V-3: 标签坐标重叠 ──
    label_positions = []
    for (efrom, eto), ports in port_map.items():
        label = ''
        for e in edges:
            if e['from'] == efrom and e['to'] == eto:
                label = e.get('label', '')
                break
        if not label:
            continue
        sc = _abs_center(efrom)
        tc = _abs_center(eto)
        lx = (sc[0] + tc[0]) / 2
        ly = (sc[1] + tc[1]) / 2
        label_positions.append((efrom, eto, label, lx, ly))
    for i, (f1, t1, l1, x1, y1) in enumerate(label_positions):
        for f2, t2, l2, x2, y2 in label_positions[i + 1:]:
            if abs(x1 - x2) < 20 and abs(y1 - y2) < 20:
                warnings.append(
                    f"V-3 标签重叠: \"{l1}\"({f1}→{t1}) 与"
                    f" \"{l2}\"({f2}→{t2}) 坐标过近")

    # ── V-4: 出口方向与目标方向相反 ──
    for (efrom, eto), ports in port_map.items():
        ex, ey = ports['exit']
        sc = _abs_center(efrom)
        tc = _abs_center(eto)
        dx, dy = tc[0] - sc[0], tc[1] - sc[1]
        # exit 方向向量
        evx = ex - 0.5  # >0 朝右, <0 朝左, 0 中间
        evy = ey - 0.5  # >0 朝下, <0 朝上, 0 中间
        # 简化点积检查：exit 方向与 target 方向是否大致一致
        dot = evx * dx + evy * dy
        if dot < -30:  # 阈值：允许小角度偏差
            warnings.append(
                f"V-4 绕路: 边 {efrom}→{eto} 的 exit={ports['exit']}"
                f" 与目标方向相反 (dx={dx:.0f}, dy={dy:.0f})")

    return warnings


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
