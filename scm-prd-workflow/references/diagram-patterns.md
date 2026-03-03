# 流程图绘制规范与模式库

## 绘制工具

统一使用Mermaid语法。原因：
- 纯文本，可版本管理
- Claude Code和Claude.ai都能渲染
- 可嵌入Markdown文档
- 可导出为图片

## 图表类型选择

| 场景 | 图表类型 | Mermaid语法 |
|------|---------|------------|
| 跨角色/跨系统的业务流程 | 泳道图 | `graph TD` + subgraph |
| 实体状态变化 | 状态机图 | `stateDiagram-v2` |
| 系统间数据流 | 数据流图 | `graph LR` |
| 复杂时序交互 | 时序图 | `sequenceDiagram` |
| 系统架构概览 | 架构图 | `graph TD` + subgraph |

## 模式 1: 业务泳道图

用于表达跨角色、跨系统的协作流程。

```mermaid
graph TD
    subgraph 用户/客户
        A1[发起操作] --> A2{条件判断}
    end

    subgraph 系统A
        A2 -->|条件1| B1[处理步骤1]
        B1 --> B2[处理步骤2]
    end

    subgraph 系统B
        B2 -->|触发| C1[接收数据]
        C1 --> C2{业务校验}
        C2 -->|通过| C3[执行操作]
        C2 -->|不通过| C4[返回异常]
    end

    subgraph 系统A
        C3 -->|回调| B3[更新状态]
        C4 -->|回调| B4[异常处理]
    end
```

**规范**：
- 每个subgraph代表一个角色或系统
- 节点用中文命名，简洁明了
- 判断节点用菱形 `{}`
- 边上标注条件或数据
- 异常路径用虚线或标红（Mermaid中用style）

## 模式 2: 状态流转图

用于表达实体（订单/任务/单据）的生命周期。

```mermaid
stateDiagram-v2
    [*] --> 待审核: 创建

    待审核 --> 已审核: 审核通过
    待审核 --> 已驳回: 审核驳回
    待审核 --> 已取消: 用户取消

    已驳回 --> 待审核: 修改后重新提交

    已审核 --> 执行中: 开始执行
    已审核 --> 已取消: 超时未执行(24h)

    执行中 --> 已完成: 执行完毕
    执行中 --> 异常中: 出现异常
    执行中 --> 已取消: 强制取消(需审批)

    异常中 --> 执行中: 异常处理完毕
    异常中 --> 已取消: 无法恢复

    已完成 --> [*]
    已取消 --> [*]
```

**规范**：
- 状态名称用中文，简短
- 转换条件标注在箭头上
- 自动触发的转换标注触发条件（如"超时24h"）
- 终态必须明确（[*]）
- 区分正常流转和异常流转

## 模式 3: 数据流向图

用于表达系统间数据传递关系。

```mermaid
graph LR
    ERP[ERP系统] -->|采购订单<br/>API/实时| WMS[WMS仓储系统]
    OMS[OMS订单系统] -->|出库指令<br/>MQ/实时| WMS
    WMS -->|库存变动<br/>API/准实时| OMS
    WMS -->|出库回告<br/>MQ/实时| TMS[TMS运输系统]
    TMS -->|签收回执<br/>API/实时| OMS
    WMS -->|作业费用<br/>文件/T+1| BMS[BMS计费系统]
    TMS -->|运费数据<br/>文件/T+1| BMS
```

**规范**：
- 方向从左到右（LR）
- 节点为系统名称
- 边标注：数据内容 + 传输方式 + 时效
- 用 `<br/>` 换行保持可读

## 模式 4: 时序图

用于表达复杂的系统间交互时序。

```mermaid
sequenceDiagram
    actor 用户
    participant OMS as OMS订单系统
    participant WMS as WMS仓储系统
    participant TMS as TMS运输系统

    用户->>OMS: 提交订单
    activate OMS
    OMS->>OMS: 订单校验
    OMS->>WMS: 查询库存
    WMS-->>OMS: 返回库存信息

    alt 库存充足
        OMS->>WMS: 下发出库指令
        activate WMS
        WMS->>WMS: 拣货/打包
        WMS->>TMS: 请求揽收
        activate TMS
        TMS-->>WMS: 返回运单号
        deactivate TMS
        WMS-->>OMS: 出库回告(含运单号)
        deactivate WMS
        OMS-->>用户: 通知已发货
    else 库存不足
        OMS-->>用户: 通知缺货
    end
    deactivate OMS
```

**规范**：
- participant用中文别名
- 同步调用用实线箭头 `->>` ，返回用虚线 `-->>`
- 用 `alt/else` 表达分支
- 用 `activate/deactivate` 表达生命周期
- 关键业务判断用 `alt/else` 而不是 `opt`

## 模式 5: 供应链常见流程模板

### 入库流程框架

```mermaid
graph TD
    subgraph 供应商
        S1[发送ASN/送货] --> S2[到达仓库]
    end
    subgraph WMS-收货
        S2 --> W1{核对单据}
        W1 -->|一致| W2[系统收货]
        W1 -->|差异| W3[差异登记]
        W3 --> W4{差异处理}
        W4 -->|补发| S1
        W4 -->|按实收| W2
    end
    subgraph WMS-质检
        W2 --> Q1{需要质检?}
        Q1 -->|是| Q2[执行质检]
        Q2 -->|合格| Q3[质检通过]
        Q2 -->|不合格| Q4[不良品处理]
        Q1 -->|否| Q3
    end
    subgraph WMS-上架
        Q3 --> P1[生成上架任务]
        P1 --> P2[系统推荐库位]
        P2 --> P3[执行上架]
        P3 --> P4[PDA确认]
    end
```

### 出库流程框架

```mermaid
graph TD
    subgraph OMS
        O1[出库指令下发]
    end
    subgraph WMS-波次
        O1 --> W1[接收出库单]
        W1 --> W2[波次规划]
        W2 --> W3[生成拣货任务]
    end
    subgraph WMS-拣货
        W3 --> P1[拣货作业]
        P1 --> P2{拣货结果}
        P2 -->|正常| P3[拣货完成]
        P2 -->|缺货| P4[缺货处理]
    end
    subgraph WMS-复核打包
        P3 --> R1[复核]
        R1 --> R2{复核结果}
        R2 -->|一致| R3[打包]
        R2 -->|差异| R4[返回拣货]
        R3 --> R5[称重/贴面单]
    end
    subgraph WMS-交接
        R5 --> H1[集货/装车]
        H1 --> H2[交接签收]
    end
    subgraph TMS
        H2 --> T1[揽收确认]
    end
```

## 绘制注意事项

1. **节点命名**：使用"动宾短语"（如"创建订单"而非"订单创建"）
2. **图表大小**：单张图不超过20个节点，超过则拆分
3. **子图标题**：使用系统/角色名称，不用"步骤1""阶段2"
4. **条件标注**：判断分支必须穷举，不能只有"是"没有"否"
5. **异常路径**：必须画出主要异常路径，不能只画happy path
6. **文件保存**：每张图单独保存为 `.mermaid` 文件，文件名与图表标题对应
