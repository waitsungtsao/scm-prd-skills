#!/usr/bin/env python3
"""
diagram_core.py — YAML 图表 DSL 的共享核心模块

提供校验、布局引擎、颜色常量、CJK 工具等公共功能，
被 yaml2drawio.py 和 yaml2svg.py 共同使用。

不可直接执行，仅作为库导入。
"""

import os
import sys
from collections import defaultdict, deque


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
# 边端口计算（被 yaml2svg.py 和 yaml2drawio.py 共用）
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
# CJK 字体检测
# =============================================================================

# CJK 字体候选列表（按优先级）。cairosvg 使用 fontconfig/Cairo 解析字体名，
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
    "Noto Sans SC",         # Noto 非 CJK 合集版
    "Droid Sans Fallback",  # 旧版 Android / Linux
]

# 每个平台的已知字体文件路径（不依赖 fontconfig）
# 支持 glob 通配符以匹配 macOS Asset 管理的动态哈希路径
_FONT_FILE_HINTS = {
    "PingFang SC":        [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/PingFang.ttc",
        "/System/Library/AssetsV2/com_apple_MobileAsset_Font*/*/AssetData/PingFang.ttc",
    ],
    "Microsoft YaHei":    [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhl.ttc",
    ],
    "Heiti SC":           [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
    ],
    "SimHei":             [
        "C:/Windows/Fonts/simhei.ttf",
    ],
    "Noto Sans CJK SC":  [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    ],
    "WenQuanYi Micro Hei": [
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/wenquanyi/wqy-microhei/wqy-microhei.ttc",
    ],
}


def detect_cjk_font():
    """多层级检测系统可用 CJK 字体，返回 font-family 字符串。

    检测策略（按可靠性从高到低）：
      Layer 1 — fc-list :lang=zh 获取系统所有中文字体，与候选列表取交集
      Layer 2 — fc-match 逐个验证候选字体名（检查是否映射为自身而非西文）
      Layer 3 — 扫描已知字体文件路径（不依赖 fontconfig，覆盖 Windows 和无 fc 的 macOS）
      Layer 4 — 按平台猜测（最终兜底）

    任一层级找到可用字体即停止。
    """
    import subprocess as _sp

    verified = []

    # ── Layer 1: fc-list :lang=zh ──
    # 一次性获取所有支持中文的字体族名，精确且快速
    try:
        r = _sp.run(
            ["fc-list", ":lang=zh", "--format=%{family}\n"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            # fc-list 每行可能是 "Font A,Font B"（多名称），全部拆开
            system_cjk = set()
            for line in r.stdout.strip().splitlines():
                for name in line.split(","):
                    system_cjk.add(name.strip())
            # 按候选优先级排序取交集
            for candidate in _CJK_FONT_CANDIDATES:
                if candidate in system_cjk:
                    verified.append(candidate)
    except (FileNotFoundError, _sp.TimeoutExpired, OSError):
        pass

    if verified:
        return ", ".join(verified + ["sans-serif"])

    # ── Layer 2: fc-match 逐个验证 ──
    # 仅当 fc-list 失败或无结果时使用（比 fc-list 慢且有模糊匹配风险）
    for candidate in _CJK_FONT_CANDIDATES:
        try:
            r = _sp.run(
                ["fc-match", "--format=%{family}", candidate],
                capture_output=True, text=True, timeout=3,
            )
            matched = r.stdout.strip().split(",")[0].strip()
            if matched.lower() == candidate.lower():
                verified.append(candidate)
        except (FileNotFoundError, _sp.TimeoutExpired, OSError):
            break  # fc-match 本身不可用，跳到 Layer 3

    if verified:
        return ", ".join(verified + ["sans-serif"])

    # ── Layer 3: 字体文件路径扫描 ──
    # 不依赖 fontconfig，覆盖 Windows 和无 fc 的 macOS / Docker
    import glob as _glob
    for candidate in _CJK_FONT_CANDIDATES:
        paths = _FONT_FILE_HINTS.get(candidate, [])
        found = False
        for pattern in paths:
            if '*' in pattern:
                if _glob.glob(pattern):
                    found = True
                    break
            elif os.path.isfile(pattern):
                found = True
                break
        if found:
            verified.append(candidate)

    if verified:
        return ", ".join(verified + ["sans-serif"])

    # ── Layer 4: 按平台猜测（兜底） ──
    import platform
    _sys = platform.system()
    if _sys == "Darwin":
        verified = ["PingFang SC", "Heiti SC"]
    elif _sys == "Windows":
        verified = ["Microsoft YaHei", "SimHei"]
    else:
        verified = ["Noto Sans CJK SC", "WenQuanYi Micro Hei"]

    print(f"警告: 未能验证 CJK 字体可用性，使用平台默认猜测: {verified[0]}。"
          f"如中文显示异常，请安装: Noto Sans CJK SC (apt/brew install fonts-noto-cjk)",
          file=sys.stderr)

    return ", ".join(verified + ["sans-serif"])
