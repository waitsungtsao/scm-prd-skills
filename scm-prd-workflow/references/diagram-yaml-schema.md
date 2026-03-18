# YAML 图表 DSL 规范

## 概述

本规范定义了一种 YAML 描述语言，用于精确描述泳道图和复杂流程图。YAML 文件通过 `yaml2drawio.py` 脚本转换为 draw.io XML 文件，获得真正的泳道容器和精确布局能力。

**泳道图布局**：泳道横向排列（每条泳道是一个竖直的列），流程从上往下流转，跨泳道连线在列之间横向连接。每条泳道列有独立边框，形成清晰的列分隔。

**适用场景**：
- 泳道图（跨角色/跨系统协作流程）
- 复杂流程图（>12 节点 + 交叉连线）

**不适用场景**（继续使用 Mermaid）：
- 状态流转图 → `stateDiagram-v2`
- 时序图 → `sequenceDiagram`
- 数据流向图 → `graph LR`
- 简单流程（≤12 节点）→ `graph TD`

## 文件格式

文件扩展名：`.diagram.yaml`，保存在 `diagrams/` 目录下。

## Schema 定义

### 顶层结构

```yaml
diagram:
  title: "图表标题"          # 必填
  type: swimlane | flow      # 必填，图表类型

lanes:                        # type=swimlane 时必填，按从左到右的列顺序定义
  - id: lane_id               # 泳道唯一标识（英文）
    label: "泳道显示名称"      # 中文标签
    color: blue | green | orange | purple  # 可选，SCM 系统色板

nodes:                        # 必填，节点列表
  - id: node_id               # 节点唯一标识（英文）
    label: "节点显示名称"      # 中文标签
    type: process | decision | start | end | subprocess | database | document
    lane: lane_id             # type=swimlane 时必填，所属泳道
    style: error | highlight | async  # 可选，语义样式

edges:                        # 必填，连线列表
  - from: node_id             # 起始节点 ID
    to: node_id               # 目标节点 ID
    label: "条件/说明"         # 可选，边标签
    style: error | async      # 可选，语义样式
```

### 节点类型说明

| 类型 | 形状 | 用途 | draw.io 尺寸 |
|------|------|------|-------------|
| `process` | 矩形 | 普通处理步骤 | 120×60 |
| `decision` | 菱形 | 条件判断 | 100×60 |
| `start` | 圆形 | 流程起点 | 60×60 |
| `end` | 粗边圆形 | 流程终点 | 60×60 |
| `subprocess` | 双边矩形 | 子流程引用 | 120×60 |
| `database` | 圆柱 | 数据库/数据存储 | 120×60 |
| `document` | 波浪底矩形 | 单据/文档 | 120×60 |

### 语义样式

| 样式 | 适用于 | 效果 |
|------|--------|------|
| `error` | 节点/边 | 红色填充/红色线条，表示异常路径 |
| `highlight` | 节点 | 黄色高亮背景，表示重点关注 |
| `async` | 边 | 虚线，表示异步调用 |

### SCM 领域系统色板

泳道 `color` 字段使用以下预定义色板，对应供应链核心系统：

| 色板名称 | 填充色 | 边框色 | 对应系统 |
|---------|--------|--------|---------|
| `blue` | `#dae8fc` | `#6c8ebf` | OMS 订单系统 |
| `green` | `#d5e8d4` | `#82b366` | WMS 仓储系统 |
| `orange` | `#ffe6cc` | `#d6b656` | TMS 运输系统 |
| `purple` | `#e1d5e7` | `#9673a6` | BMS 计费系统 |

未指定 color 时，使用 draw.io 默认白色背景。

## 校验规则

脚本在转换前执行以下校验，不通过则报错退出：

1. **节点引用完整性**：所有 `edges[].from` 和 `edges[].to` 必须引用已存在的 `nodes[].id`
2. **泳道引用完整性**：当 `type=swimlane` 时，所有 `nodes[].lane` 必须引用已存在的 `lanes[].id`
3. **ID 唯一性**：所有 `nodes[].id` 和 `lanes[].id` 不得重复
4. **必填字段**：`diagram.title`、`diagram.type`、节点的 `id`/`label`/`type`、边的 `from`/`to` 不得为空
5. **判断节点出边**：`decision` 类型的节点至少有 2 条出边（对应不同分支）

## 完整示例：SCM 出库流程泳道图

```yaml
diagram:
  title: "出库主流程"
  type: swimlane

lanes:
  - id: oms
    label: "OMS 订单系统"
    color: blue
  - id: wms_wave
    label: "WMS-波次"
    color: green
  - id: wms_pick
    label: "WMS-拣货"
    color: green
  - id: wms_check
    label: "WMS-复核打包"
    color: green
  - id: tms
    label: "TMS 运输系统"
    color: orange

nodes:
  # OMS
  - id: o1
    label: "出库指令下发"
    type: process
    lane: oms

  # WMS-波次
  - id: w1
    label: "接收出库单"
    type: process
    lane: wms_wave
  - id: w2
    label: "波次规划"
    type: process
    lane: wms_wave
  - id: w3
    label: "生成拣货任务"
    type: process
    lane: wms_wave

  # WMS-拣货
  - id: p1
    label: "拣货作业"
    type: process
    lane: wms_pick
  - id: p2
    label: "拣货结果"
    type: decision
    lane: wms_pick
  - id: p3
    label: "拣货完成"
    type: process
    lane: wms_pick
  - id: p4
    label: "缺货处理"
    type: process
    lane: wms_pick
    style: error

  # WMS-复核打包
  - id: r1
    label: "复核"
    type: process
    lane: wms_check
  - id: r2
    label: "复核结果"
    type: decision
    lane: wms_check
  - id: r3
    label: "打包"
    type: process
    lane: wms_check
  - id: r4
    label: "返回拣货"
    type: process
    lane: wms_check
    style: error
  - id: r5
    label: "称重/贴面单"
    type: process
    lane: wms_check
  - id: h1
    label: "集货/装车"
    type: process
    lane: wms_check
  - id: h2
    label: "交接签收"
    type: process
    lane: wms_check

  # TMS
  - id: t1
    label: "揽收确认"
    type: process
    lane: tms

edges:
  - from: o1
    to: w1
  - from: w1
    to: w2
  - from: w2
    to: w3
  - from: w3
    to: p1
  - from: p1
    to: p2
  - from: p2
    to: p3
    label: "正常"
  - from: p2
    to: p4
    label: "缺货"
    style: error
  - from: p3
    to: r1
  - from: r1
    to: r2
  - from: r2
    to: r3
    label: "一致"
  - from: r2
    to: r4
    label: "差异"
    style: error
  - from: r3
    to: r5
  - from: r5
    to: h1
  - from: h1
    to: h2
  - from: h2
    to: t1
```

## 转换命令

需要 Python 3.8+ 和 PyYAML（`pip install pyyaml`）。

```bash
# macOS / Linux
python3 scm-prd-workflow/scripts/yaml2drawio.py \
    requirements/REQ-xxx/diagrams/main-flow.diagram.yaml

# Windows（根据环境使用 python 或 py -3）
python scm-prd-workflow/scripts/yaml2drawio.py ^
    requirements/REQ-xxx/diagrams/main-flow.diagram.yaml

# → 输出: requirements/REQ-xxx/diagrams/main-flow.drawio
```

转换后的 `.drawio` 文件可用 VS Code draw.io 扩展或 draw.io 桌面应用打开和编辑。

**Python 不可用时**：`.diagram.yaml` 源文件本身是完整的图表描述，可在 Python 环境就绪后再转换，或回退到 Mermaid 方案。详见 SKILL.md 3.2 节降级处理。
