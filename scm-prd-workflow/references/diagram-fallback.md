# 运行环境与降级策略

本文档说明 flow-architect 的运行依赖、缺失依赖时的降级路径、以及生成失败时的自动重试规则。

---

## 1. 运行依赖

| 依赖 | 必需 | 用途 | 缺失行为 |
|---|---|---|---|
| **Python ≥ 3.8** | ✓ | 跑所有脚本 | 报错并提示安装 |
| **PyYAML** | ✓ | 解析 `.diagram.yaml` 输入 | 报错并提示 `pip install pyyaml` |
| `cairosvg` | 可选 | SVG → PNG 转换 | 跳过 PNG，只输出 `.drawio` + `.svg` |
| `mmdc`（mermaid-cli） | 可选 | `.mermaid` 文件本地渲染为 PNG | 自动降级到 `mermaid.ink` 远程 API |
| 网络访问 | 可选 | mmdc 不可用时的远程兜底 | 同时缺 → 保留 `.mermaid` 源文件，告知用户 |

**最小安装**：`pip install -r scripts/requirements.txt`（仅 PyYAML，~30s）。

---

## 2. PyYAML 缺失时

`yaml2drawio.py` / `yaml2svg.py` / `export-diagrams.py` 启动时检测 `import yaml` 失败 → 退出码 1，stderr 输出：

```
错误: 缺少 PyYAML
解决: pip install pyyaml
```

skill 在伙伴模式渲染失败后应**先**引导用户安装 PyYAML，再考虑 fallback。

---

## 3. cairosvg 缺失时（PNG 输出）

`yaml2svg.py --png` 在 cairosvg 不可用时**静默跳过 PNG 生成**，输出仍含 `.svg`，stderr 仅一行警告：

```
[警告] cairosvg 未安装，跳过 PNG 转换；如需 PNG: pip install cairosvg
```

不阻断 `.drawio` / `.svg` 输出。

---

## 4. mermaid 文件渲染：mmdc → mermaid.ink

`export-diagrams.py` 处理 `.mermaid` 文件时按如下顺序：

1. **优先 mmdc 本地命令**：
   ```bash
   mmdc -i input.mermaid -o output.png -b white -s 2 -C scripts/mmdc-cjk.css -p scripts/mmdc-puppeteer.json
   ```
   失败（命令不存在 / Puppeteer 启动失败）→ fallback。

2. **fallback 到 mermaid.ink 远程 API**（base64 编码 + HTTPS GET）：
   ```
   https://mermaid.ink/img/<base64-encoded-source>?type=png
   ```
   通过项目配置 `.scm-prd-config.yaml` 或 `.scm-prd-env-cache.json` 中的 `allow_remote_render: true/false` 开关控制是否允许远程渲染。

3. **远程也失败**（无网/被墙/API 故障）→ 保留 `.mermaid` 源文件，stderr 提示用户手动处理。

---

## 5. yaml2drawio / yaml2svg 运行时错误

YAML 校验通过后，端口路由仍可能因几何冲突报警告（V-1~V-4，见 §6）；YAML 本身错误（拼写、缺引用）则直接报错。

**处理规则**：
- YAML 语法错误 / 节点引用错 → 退出码 1，stderr 输出具体行号 → skill 应直接修改 YAML 后重试，**最多 2 次**
- 几何警告（V-1~V-4）→ 退出码 0，stderr 有警告但仍输出文件 → skill 可选择修改 YAML 重试或保留当前版本

**自动重试边界**：
- 不要无限循环重试同一类错误
- 2 次后仍失败 → 保留 `.diagram.yaml` 源文件，告知用户具体错误

---

## 6. 几何校验（V-1 ~ V-4）

`compute_edge_ports()` 内置自动修正，`validate_edge_layout()` 检测残留：

| 编号 | 检查项 | 自动修正 | 残留时的处理 |
|---|---|---|---|
| **V-1** | 同源同出口多边重叠 | ✅ 轮转分配不同端口 | 调整边顺序或拆分节点 |
| **V-2** | 路径穿越中间节点 | ❌ 需改 YAML 结构 | 调整节点层级或拆图 |
| **V-3** | 标签距离 < 20px | ❌ 需改标签文字 | 缩短标签或调整边顺序 |
| **V-4** | exit 方向与目标夹角 > 90° | ✅ 翻转 exit 方向 | 因 V-1 折中无法修正时：评估是否拆图 |

V-1 和 V-4 在多数情况下静默自动修正，用户无感知；V-2 / V-3 残留时 skill 应**直接修改 YAML**（调整边顺序、缩短标签、调整节点层级）后重试。

---

## 7. 降级决策记忆

同一 skill 会话中，用户对 fallback 选项的选择应被记忆，避免重复询问：

- 例：用户选择"无 PyYAML 时仅保留 YAML 源文件" → 后续同类图表自动按此处理
- 例：用户允许远程 mermaid 渲染 → 后续 .mermaid 文件直接走 mermaid.ink

**重启会话后**：决策被清空，重新问询（防止旧决策与新环境不匹配）。

---

## 8. 完整降级路径示意

```
                    用户给出 YAML
                          ↓
                    PyYAML 可用？
                    ↙           ↘
                  否              是
                  ↓                ↓
            报错 + 引导安装     yaml2drawio.py
                                  ↓
                            生成成功？
                            ↙       ↘
                          否          是
                          ↓            ↓
                    最多 2 次重试   .drawio 完成
                                      ↓
                                  cairosvg 可用？
                                  ↙       ↘
                                否          是
                                ↓            ↓
                          仅 .svg 输出    .png 一并输出
```

mermaid 路径独立：mmdc → mermaid.ink → 保留 .mermaid 源。

---

## 9. 错误信息约定

skill 向用户报错时：

1. **明确缺失**："缺少 PyYAML，需要 `pip install pyyaml`"
2. **明确范围**："本张 `.diagram.yaml` 转换失败，已保留源文件"，不夸大为"全部失败"
3. **给出下一步**："你可以稍后手动安装后跑 `python3 scripts/export-diagrams.py <dir>` 重新生成"
4. **不阻断当前对话**：渲染失败应作为局部信息反馈，不应让伙伴模式整个工作流退出
