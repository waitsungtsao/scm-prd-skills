# 知识库结构规范

## 文件组织

```
knowledge-base/
├── _index.md                  # 知识地图（必须）
├── glossary.yaml              # 术语表（YAML格式）
├── domain-{领域名}.md         # 领域知识卡片
├── integration-points.md      # 系统集成点
├── business-rules.md          # 跨领域业务规则
└── decision-log.md            # 历史决策记录
```

## 文件命名规则

- 领域文件：`domain-{英文缩写}.md`（如 domain-oms.md, domain-wms.md）
- 全小写，连字符分隔
- 不使用中文文件名（避免编码问题）

## 知识卡片内部结构

每个领域文件的内部结构：

```markdown
---
domain: OMS
domain_cn: 订单管理系统
last_updated: 2025-03-01
sources:
  # type 枚举: interview(口述), document(文档), inference(推测), observation(观察)
  - type: interview
    date: 2025-03-01
    confirmed: true       # true=用户明确确认, partial=大方向确认但细节待补充, false=尚未经用户确认
  - type: document
    name: "OMS需求说明书V2.1.docx"
    confirmed: partial
completeness: 60%
gaps:
  - 逆向订单流程未梳理
  - 促销规则待补充
---

# OMS 订单管理

## 1. 业务概述
[一段话描述这个领域的定位和边界]

## 2. 核心流程

### 2.1 正向订单流
[文字描述 + Mermaid流程图]

### 2.2 逆向订单流
[文字描述 + Mermaid流程图]

## 3. 业务规则

### 3.1 订单拆分规则
| 规则编号 | 触发条件 | 处理逻辑 | 备注 |
|---------|---------|---------|------|
| R-OMS-001 | 多仓库SKU | 按仓库拆分子订单 | [待确认]拆分后是否生成新单号 |

### 3.2 状态流转
[状态机图 Mermaid]

## 4. 数据实体

### 4.1 订单主表
| 字段 | 说明 | 类型 | 必填 | 来源 |
|------|------|------|------|------|
| order_no | 订单号 | string | Y | 系统生成 |
| ... | ... | ... | ... | ... |

## 5. 系统交互
[本领域与其他系统的接口清单]

## 6. 角色与权限
| 角色 | 核心操作 | 审批权限 | 数据可见范围 |
|------|---------|---------|------------|
| ... | ... | ... | ... |

## 7. 已知问题与历史决策
> 2023年因XX原因，做了YY临时方案，目前仍在使用...

## 8. 待确认事项
- [ ] 大客户订单是否有独立审批流程？
- [ ] 订单超时自动取消的时间阈值？
```

## 术语表格式 (glossary.yaml)

```yaml
# 术语表
# 按字母/拼音排序

terms:
  - term: ASN
    full_name: Advance Shipping Notice
    cn_name: 预到货通知
    definition: 供应商发货前向收货方发送的到货预告
    domain: [WMS, OMS]
    related: [PO, 收货单]

  - term: 波次
    full_name: Wave
    cn_name: 波次
    definition: 将多个出库单按一定规则合并处理的作业单元
    domain: [WMS]
    related: [拣货, 出库单]

  - term: SKU
    full_name: Stock Keeping Unit
    cn_name: 最小存货单位
    definition: 库存管理的最小单位，包含商品+规格+批次等属性
    domain: [WMS, OMS]
    related: [SPU, 商品主数据]
```

## 完整度评估标准

| 完整度 | 标准 |
|--------|------|
| 0-20% | 只有概述，缺少流程、规则、数据定义 |
| 20-40% | 有主流程，但缺少异常处理和详细规则 |
| 40-60% | 主流程和主要规则完整，异常处理和集成点部分缺失 |
| 60-80% | 流程、规则、数据实体基本完整，细节待补充 |
| 80-100% | 全面覆盖，包含异常处理、历史决策、系统集成 |

## 质量标注约定

- `[待确认]`：信息来源不确定，需要向相关人员确认
- `[推测]`：基于已有信息推断，未经验证
- `[过时?]`：可能已过时的信息，需要核实时效性
- `[矛盾]`：与其他文档或描述存在矛盾，需要澄清
