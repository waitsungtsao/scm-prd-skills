# 环境检测与依赖引导

本文件包含启动初始化步骤 5-8 的完整操作细节。读取时机：初始化阶段。

---

## 环境检测流程（步骤 5-7）

### 步骤 5: 检测 Node.js + docx 环境（Word 生成推荐方案）

依次尝试：`node -e "require('docx')"` → `node -e "import('docx')"` → `NODE_PATH=$(npm root -g) node -e "require('docx')"`（依次检测本地 CJS → 本地 ESM → 全局安装）
- 任一成功 → `node_docx_available = true`，`docx_engine = "js"`
- 全部失败 → `node_docx_available = false`，继续检测 Python 降级方案

### 步骤 6: 检测 Python 环境（跨平台）

依次尝试以下命令，使用第一个成功的：
- `python3 -c "import yaml; print('ok')"`（macOS / Linux 优先）
- `python -c "import yaml; print('ok')"`（Windows 常见）
- `py -3 -c "import yaml; print('ok')"`（Windows Python Launcher）
- 记录成功的命令为 `python_cmd`（如 `python3`），后续所有 Python 调用统一使用该命令
- 全部失败 → 记录 `python_available = false`，后续泳道图仅输出 `.diagram.yaml` 源文件（不转换为 `.drawio`），并在首次需要生成泳道图时提示用户
- 轻量模式仅使用 Mermaid，不依赖 Python 环境

### 步骤 7: 检测图表导出能力 + Word 降级引擎（Python 可用时追加）

- `{python_cmd} -c "import cairosvg; print('ok')"` → `cairosvg_available`（SVG→PNG 转换）
- `{python_cmd} -c "import docx; print('ok')"` → `python_docx_available`（Python Word 降级方案）
- 检测 Mermaid 图片导出能力（优先本地）：
  - `mmdc --version` → `mmdc_available`（本地 mermaid-cli，优先；自带 CJK 字体栈 `scripts/mmdc-cjk.css` + 跨平台 Puppeteer 配置 `scripts/mmdc-puppeteer.json`）
  - 如 mmdc 不可用：`{python_cmd} -c "import urllib.request; urllib.request.urlopen('https://mermaid.ink/img/Z3JhcGggVEQKICAgIEFbU3RhcnRd', timeout=5); print('ok')"` → `mermaid_ink_available`（远程兜底）
  - 导出优先级：mmdc 本地 → mermaid.ink 远程 → 仅保留 `.mermaid` 源文件
  - 两者均不可用时提示：**`npm install -g @mermaid-js/mermaid-cli`**
- 如果 `node_docx_available = false` 且 `python_docx_available = true` → `docx_engine = "python"`
- 如果两者均不可用 → `docx_engine = null`

---

## 环境状态播报（ENV-01）

初始化检测（步骤 5-7）完成后，**始终**输出环境状态摘要。如有关键依赖缺失，使用 `AskUserQuestion` 引导用户选择。

**摘要格式**（全部就绪时标题用"环境就绪"，有缺失时用"环境状态"）：

```
━━━ 环境就绪 ━━━
  Word 引擎  : JS (docx)           ✓
  Python     : python3              ✓
  PyYAML     : 已安装               ✓
  Mermaid    : mmdc (本地)          ✓   ← mmdc 不可用时显示 "mermaid.ink (远程) ⚠隐私" 或 "不可用 ⚠"
  cairosvg   : 未安装 → SVG only    ⚠
━━━━━━━━━━━━━━━
```

- 缺失项用 `⚠` 标记并注明降级方案；可用项用 `✓` 标记
- 此摘要为纯展示，不阻断流程（除非 Word 引擎缺失需引导）
- **Mermaid 隐私提示**：当 mmdc 不可用、降级为 mermaid.ink 远程渲染时，在摘要中标注 `⚠隐私`，并附加说明："mermaid.ink 会将图表内容发送到第三方服务器渲染，含敏感业务流程的图表建议安装 **`npm install -g @mermaid-js/mermaid-cli`** 使用本地渲染"

---

## Word 依赖引导（`docx_engine != "js"` 时触发）

使用 `AskUserQuestion`：

> header: "Word 依赖"
> 问题: "当前未检测到 Node.js docx 库，Word 文档{将使用 Python 降级方案（排版精度较低） / 生成不可用}。\n\n请选择处理方式："
> 选项：
> - **安装依赖（推荐）**：运行 **`npm install -g docx`** 安装到全局环境
> - **使用降级方案**：{使用 Python 生成 / 仅输出 Markdown，不生成 Word}
> - **稍后处理**：跳过，在交付阶段再决定

用户选择"安装依赖"时：
1. 执行 `npm install -g docx`
2. 验证：`NODE_PATH=$(npm root -g) node -e "require('docx')"`
3. 成功 → 更新 `docx_engine = "js"`，输出：`━━━ 环境已更新 ━━━\n  Word 引擎  : JS (docx)  ✓`
4. 失败 → 告知具体原因（权限不足 / npm 不可用 / 网络问题），回退展示降级选项（去掉"安装依赖"）

用户选择"稍后处理"时：按当前 `docx_engine` 值继续，交付阶段生成 Word 前再次提示（参见 SKILL.md "图表导出与 Word 生成"章节）。
