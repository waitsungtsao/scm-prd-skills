#!/usr/bin/env node
/**
 * md2docx.mjs — PRD Markdown → Word (docx-js)
 *
 * 基于 scm-prd-style 规范的 Markdown→Word 转换器。
 * 用法: node md2docx.mjs <PRD.md文件路径>
 * 依赖: npm install -g docx（全局安装，也兼容本地 node_modules）
 */
import fs from "fs";
import path from "path";
import { createRequire } from "module";
import { execSync } from "child_process";

// 依赖解析：优先本地 node_modules → 其次全局（支持 npm install -g docx）
function loadDocx() {
  // 1. 尝试本地 node_modules（兼容项目级安装）
  try {
    const localReq = createRequire(path.join(process.cwd(), "package.json"));
    return localReq("docx");
  } catch {}
  // 2. 尝试全局 node_modules
  try {
    const globalRoot = execSync("npm root -g", { encoding: "utf-8" }).trim();
    const globalReq = createRequire(path.join(path.dirname(globalRoot), "_resolve.js"));
    return globalReq("docx");
  } catch {}
  console.error("错误: 需要 docx 库。请运行: npm install -g docx");
  process.exit(1);
}

const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel,
  BorderStyle, WidthType, ShadingType, PageBreak, PageNumber,
  TabStopType, TabStopPosition,
} = loadDocx();

// ── DESIGN TOKENS (与 scm-prd-style/references/design-tokens.md 一致) ──
const C = {
  black: "1A1A1A", darkGray: "2D2D2D", bodyGray: "333333",
  midGray: "666666", captionGray: "888888", lightGray: "AAAAAA",
  borderGray: "D0D0D0", dividerGray: "E5E5E5",
  bgSubtle: "F2F2F2", bgLight: "F7F7F7", white: "FFFFFF",
  primary: "2B5797", primaryDark: "1E3F6F",
  primaryLight: "E8EEF5", primaryMid: "B8CCE4",
  error: "C0392B", errorLight: "FBEAE9",
  success: "1E7E51", successLight: "E6F4ED",
  warning: "C27D0E", warningLight: "FDF3E3",
};
const FONT_CN = "Microsoft YaHei";
const FONT_EN = "Segoe UI";
const FONT_CODE = "Consolas";
const PAGE_W = 11906;
const PAGE_H = 16838;
const MARGIN = { top: 1440, right: 1260, bottom: 1260, left: 1260 };
const CW = PAGE_W - MARGIN.left - MARGIN.right; // 9386

const CALLOUT_MAP = {
  "[!INFO]":    { color: C.primary,  bg: C.primaryLight, label: "信息提示  INFO" },
  "[!CAUTION]": { color: C.warning,  bg: C.warningLight, label: "注意事项  CAUTION" },
  "[!WARNING]": { color: C.error,    bg: C.errorLight,   label: "风险警告  WARNING" },
  "[!TIP]":     { color: C.success,  bg: C.successLight, label: "最佳实践  TIP" },
  "[待确认]":   { color: C.warning,  bg: C.warningLight, label: "待确认" },
  "[推断]":     { color: C.primary,  bg: C.primaryLight, label: "推断" },
  "[建议]":     { color: C.success,  bg: C.successLight, label: "建议" },
};

// Feature heading 类型配色（与 scm-prd-style 对齐）
// #### F-xxx → H3 featureHeading（粗左边条 + 浅色背景）
// ##### F-xxx.x → H4 subFeatureHeading（浅色背景，无左边条）
const FEAT_TYPES = {
  feature:   { dark: "1E3F6F", light: "E8EEF5" },  // F-xxx   功能点（蓝色系）
  api:       { dark: "155E3D", light: "E6F4ED" },  // IF-xxx  接口（绿色系）
  goal:      { dark: "8E5B08", light: "FDF3E3" },  // G-xxx   目标（琥珀色系）
  change:    { dark: "5B3A8C", light: "F0EBF8" },  // C-xx    变更点（紫色系）
};

/** 检测标题文本是否为 PRD 标记 ID 开头，返回类型名或 null */
function detectFeatType(text) {
  // IF- 必须在 F- 之前检测（避免 IF-001 被 F- 误匹配——实际不会，但语义更清晰）
  if (/^IF-\d/i.test(text)) return "api";
  if (/^F-\d/i.test(text)) return "feature";
  if (/^G-\d/i.test(text)) return "goal";
  if (/^C-\d/i.test(text)) return "change";
  return null;
}

// ── IMAGE HELPERS ──
const EMU_PER_INCH = 914400;
const IMAGE_MAX_WIDTH = 6 * EMU_PER_INCH; // 6 inches, matching Python version

/** 解析图片路径：原路径 → .drawio/.svg/.mermaid 同名 .png → diagrams/ 子目录 */
function resolveImagePath(rawSrc, mdDir) {
  const raw = rawSrc.trim();
  const candidate = path.isAbsolute(raw) ? raw : path.resolve(mdDir, raw);
  if (fs.existsSync(candidate)) return candidate;
  // .drawio / .svg / .mermaid → try same-name .png
  const ext = path.extname(candidate).toLowerCase();
  if ([".drawio", ".svg", ".mermaid"].includes(ext)) {
    const png = candidate.replace(/\.[^.]+$/, ".png");
    if (fs.existsSync(png)) return png;
  }
  // Try diagrams/ subdirectory
  const pngName = path.basename(raw, path.extname(raw)) + ".png";
  const diagCandidate = path.join(mdDir, "diagrams", pngName);
  if (fs.existsSync(diagCandidate)) return diagCandidate;
  return null;
}

/** 从 PNG 文件头读取宽高（px），非 PNG 返回 null */
function readPngSize(buf) {
  if (buf.length >= 24 && buf[0] === 0x89 && buf[1] === 0x50) {
    return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
  }
  return null;
}

// ── SHARED PRIMITIVES ──
const thinBorder = { style: BorderStyle.SINGLE, size: 1, color: C.borderGray };
const noBorder   = { style: BorderStyle.NONE, size: 0, color: C.white };
const allBorders = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder };
const noBorders  = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };
const pad        = { top: 80, bottom: 80, left: 120, right: 120 };
const padTight   = { top: 50, bottom: 50, left: 100, right: 100 };

// ── HELPER FUNCTIONS (对齐 design-tokens.md boilerplate) ──

function txt(text, opts = {}) {
  return new TextRun({
    text,
    font: opts.font || FONT_CN,
    size: opts.size || 22,
    bold: opts.bold || false,
    italics: opts.italics || false,
    color: opts.color || C.bodyGray,
    shading: opts.shading,
  });
}

function para(children, opts = {}) {
  const config = { children: Array.isArray(children) ? children : [children] };
  if (opts.spacing) config.spacing = opts.spacing;
  if (opts.alignment) config.alignment = opts.alignment;
  if (opts.indent) config.indent = opts.indent;
  if (opts.border) config.border = opts.border;
  if (opts.shading) config.shading = opts.shading;
  if (opts.heading) config.heading = opts.heading;
  if (opts.numbering) config.numbering = opts.numbering;
  if (opts.tabStops) config.tabStops = opts.tabStops;
  if (opts.pageBreakBefore) config.pageBreakBefore = true;
  return new Paragraph(config);
}

function mkCell(children, opts = {}) {
  return new TableCell({
    borders: opts.borders || allBorders,
    width: { size: opts.w, type: WidthType.DXA },
    margins: opts.pad || pad,
    shading: opts.bg ? { fill: opts.bg, type: ShadingType.CLEAR } : undefined,
    verticalAlign: opts.valign || "top",
    children: Array.isArray(children) ? children : [children],
  });
}

function spacer(h = 100) {
  return para(txt(" ", { size: 2 }), { spacing: { before: h } });
}

/** Parse inline **bold** and `code` into TextRun[] */
function parseInline(text, baseOpts = {}) {
  const sz = baseOpts.size || 22;
  const clr = baseOpts.color || C.bodyGray;
  const bld = baseOpts.bold || false;
  const fn = baseOpts.font || FONT_CN;
  const runs = [];
  const re = /(\*\*.*?\*\*|`.*?`)/g;
  let last = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last)
      runs.push(txt(text.slice(last, m.index), { size: sz, color: clr, bold: bld, font: fn }));
    const seg = m[0];
    if (seg.startsWith("**"))
      runs.push(txt(seg.slice(2, -2), { size: sz, color: clr, bold: true, font: fn }));
    else
      runs.push(txt(seg.slice(1, -1), { size: 20, color: clr, font: FONT_CODE,
        shading: { fill: C.bgSubtle, type: ShadingType.CLEAR } }));
    last = m.index + m[0].length;
  }
  if (last < text.length)
    runs.push(txt(text.slice(last), { size: sz, color: clr, bold: bld, font: fn }));
  return runs.length ? runs : [txt(text, { size: sz, color: clr, bold: bld, font: fn })];
}

// ── TABLE COLUMN WIDTH (弹性分配策略) ──

function charWidth(text) {
  let w = 0;
  for (const ch of text) w += ch.charCodeAt(0) > 0x7F ? 2 : 1;
  return w;
}

function isSeqCol(values) {
  return values.every(v => !v.trim() || /^(\d{1,3}|#|序号|No\.?)$/.test(v.trim()));
}

/**
 * 计算列宽（DXA），总和 = CW。
 * 策略：序号列固定窄宽 → 标题行决定最小宽度 → 最宽列为弹性列获取剩余空间。
 * 硬规则：最小列宽 800 DXA，弹性列 ≥ 35% CW。
 */
function computeColWidths(rows) {
  const nc = rows[0].length;
  if (nc <= 1) return [CW];

  const MIN_COL = 800;
  const MIN_FLEX_RATIO = 0.35;
  const SEQ_W = 650;

  // 检测序号列
  const seq = nc > 1 && rows.length > 1 && isSeqCol(rows.slice(1).map(r => r[0]));

  // 每列估算所需宽度（基于标题 + 数据内容）
  const estimates = [];
  for (let c = 0; c < nc; c++) {
    if (c === 0 && seq) { estimates.push(SEQ_W); continue; }
    // 标题行权重 ×2（确保标题不换行）
    const headerNeed = charWidth(rows[0][c]) * 2.0;
    // 数据行取 P80 宽度
    const dataWs = rows.slice(1).map(r => charWidth(r[c] || "")).sort((a, b) => b - a);
    const p80 = dataWs.length ? dataWs[Math.min(Math.floor(dataWs.length * 0.2), dataWs.length - 1)] : 0;
    // 字符宽度 → DXA：每字符约 120 DXA (10pt 字体)
    const dxa = Math.max(MIN_COL, Math.round(Math.max(headerNeed, p80) * 120));
    estimates.push(dxa);
  }

  // 找出弹性列（最宽的非序号列）
  let flexIdx = 0;
  let maxEst = 0;
  for (let c = 0; c < nc; c++) {
    if (c === 0 && seq) continue;
    if (estimates[c] > maxEst) { maxEst = estimates[c]; flexIdx = c; }
  }

  // 固定列总和（不含弹性列）
  const fixedTotal = estimates.reduce((a, b) => a + b, 0) - estimates[flexIdx];
  // 弹性列获取剩余，但不小于 35% CW
  let flexW = CW - fixedTotal;
  const minFlex = Math.round(CW * MIN_FLEX_RATIO);
  if (flexW < minFlex) {
    // 压缩固定列腾空间
    const shrinkFactor = (CW - minFlex) / fixedTotal;
    for (let c = 0; c < nc; c++) {
      if (c === flexIdx) continue;
      estimates[c] = Math.max(MIN_COL, Math.round(estimates[c] * shrinkFactor));
    }
    flexW = CW - estimates.reduce((a, b, idx) => idx === flexIdx ? a : a + b, 0);
  }
  estimates[flexIdx] = flexW;

  // 归一化到 CW
  const total = estimates.reduce((a, b) => a + b, 0);
  if (total !== CW) {
    const diff = CW - total;
    estimates[flexIdx] += diff;
  }

  return estimates;
}

// ── ELEMENT BUILDERS ──

function makeCallout(marker, content) {
  const info = CALLOUT_MAP[marker];
  if (!info) return para(parseInline(content), { spacing: { after: 160, line: 360 } });
  const barW = 120;
  const contentW = CW - barW;
  return new Table({
    width: { size: CW, type: WidthType.DXA },
    columnWidths: [barW, contentW],
    rows: [new TableRow({ cantSplit: true, children: [
      new TableCell({
        borders: noBorders, width: { size: barW, type: WidthType.DXA },
        shading: { fill: info.color, type: ShadingType.CLEAR },
        margins: { top: 0, bottom: 0, left: 0, right: 0 },
        children: [para(txt(" ", { size: 4 }))],
      }),
      new TableCell({
        borders: noBorders, width: { size: contentW, type: WidthType.DXA },
        shading: { fill: info.bg, type: ShadingType.CLEAR },
        margins: { top: 100, bottom: 100, left: 180, right: 160 },
        children: [
          para(txt(info.label, { size: 21, bold: true, color: info.color }), { spacing: { after: 60 } }),
          para(parseInline(content, { size: 20 }), { spacing: { after: 0 } }),
        ],
      }),
    ]})]
  });
}

// 根据表头文本判断该列是否应使用代码字体
const CODE_COL_HEADERS = /^(字段名?|字段|类型|数据类型|参数名?|参数|接口|路径|URL|API|方法|Method|端点|Endpoint|枚举值?|默认值)$/i;
// 根据单元格内容判断是否为代码/字段值（英文标识符、API路径、类型名等）
const CODE_CONTENT_RE = /^(GET|POST|PUT|DELETE|PATCH)\s|^\/[a-z]|^[a-z_][a-z0-9_.]*$/i;
const TYPE_CONTENT_RE = /^(String|Integer|Int|Long|Boolean|Float|Double|Decimal|Date|DateTime|Timestamp|List|Map|Array|JSON|BigDecimal|Enum|Object|Void)(\(.+\))?$/i;

function makeTable(rows) {
  const colWidths = computeColWidths(rows);

  // 检测哪些列应使用代码字体（根据表头名）
  const headers = rows[0] || [];
  const isCodeCol = headers.map(h => CODE_COL_HEADERS.test(h.trim()));

  const tableRows = rows.map((row, ri) => {
    while (row.length < colWidths.length) row.push("");
    const cells = row.map((text, ci) => {
      const w = colWidths[ci];
      // 数据行：代码列 或 内容匹配代码模式 → 使用 FONT_CODE
      const useCode = ri > 0 && (isCodeCol[ci] || CODE_CONTENT_RE.test(text.trim()) || TYPE_CONTENT_RE.test(text.trim()));
      const cellPara = para(parseInline(text, {
        size: 20,
        color: ri === 0 ? C.white : C.bodyGray,
        bold: ri === 0,
        font: useCode ? FONT_CODE : FONT_CN,
      }), { spacing: { before: 0, after: 0, line: 288 } });

      return mkCell(cellPara, {
        w,
        bg: ri === 0 ? C.primary : (ri % 2 === 0 ? C.bgLight : undefined),
        valign: "center",
      });
    });
    return new TableRow({ tableHeader: ri === 0, children: cells });
  });
  return new Table({
    width: { size: CW, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: tableRows,
  });
}

// ── MARKDOWN PARSER ──

function parseMarkdown(text) {
  const lines = text.split("\n");
  const elements = [];
  let i = 0;
  let docTitle = "";

  // Skip YAML front matter
  if (lines[0]?.trim() === "---") {
    i = 1;
    while (i < lines.length && lines[i].trim() !== "---") i++;
    i++;
  }

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (/^---+\s*$/.test(line)) { i++; continue; } // skip hr

    // Table note: ^ prefix
    if (/^\^\s/.test(line)) {
      const noteLines = [];
      while (i < lines.length && /^\^\s/.test(lines[i])) {
        noteLines.push(lines[i].replace(/^\^\s/, ""));
        i++;
      }
      elements.push({ type: "table-note", lines: noteLines });
      continue;
    }

    // Heading: # → title, ## → H1, ### → H2, #### → H3, ##### → H4
    const hm = line.match(/^(#{1,5})\s+(.+)$/);
    if (hm) {
      const mdLv = hm[1].length;
      const htxt = hm[2].trim();
      if (mdLv === 1) { docTitle = htxt; elements.push({ type: "title", text: htxt }); }
      else elements.push({ type: "heading", level: mdLv - 1, text: htxt });
      i++; continue;
    }

    // Code fence
    const cm = line.match(/^```(\w*)/);
    if (cm) {
      i++;
      const codeLines = [];
      while (i < lines.length && !lines[i].match(/^```/)) { codeLines.push(lines[i]); i++; }
      if (i < lines.length) i++;
      elements.push({ type: "code", lang: cm[1], lines: codeLines });
      continue;
    }

    // Image
    const im = line.match(/^!\[([^\]]*)\]\(([^)]+)\)\s*$/);
    if (im) { elements.push({ type: "image", alt: im[1], src: im[2] }); i++; continue; }

    // Table
    if (/^\|.+\|\s*$/.test(line)) {
      const rows = [];
      while (i < lines.length && /^\|.+\|\s*$/.test(lines[i])) {
        if (/^\|[\s:]*-{2,}[\s:|-]*\|\s*$/.test(lines[i])) { i++; continue; }
        rows.push(lines[i].trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim()));
        i++;
      }
      if (rows.length) elements.push({ type: "table", rows });
      continue;
    }

    // Blockquote / Callout
    if (/^>\s?/.test(line)) {
      const bqLines = [];
      while (i < lines.length) {
        const bm = lines[i].match(/^>\s?(.*)/);
        if (bm) { bqLines.push(bm[1]); i++; }
        else if (!lines[i].trim() && i + 1 < lines.length && /^>/.test(lines[i + 1])) { i++; }
        else break;
      }
      const bqText = bqLines.join("\n");
      let marker = null;
      for (const k of Object.keys(CALLOUT_MAP)) {
        if (bqText.includes(k)) { marker = k; break; }
      }
      if (marker) elements.push({ type: "callout", marker, content: bqText.replace(marker, "").trim() });
      else elements.push({ type: "quote", text: bqText });
      continue;
    }

    // Unordered list
    if (/^\s*[-*]\s+/.test(line)) {
      const items = [];
      while (i < lines.length) {
        const lm = lines[i].match(/^\s*[-*]\s+(.*)/);
        if (lm) { items.push(lm[1]); i++; }
        else if (!lines[i].trim() && i + 1 < lines.length && /^\s*[-*]\s+/.test(lines[i + 1])) { i++; }
        else break;
      }
      elements.push({ type: "ul", items });
      continue;
    }

    // Ordered list
    if (/^\s*\d+\.\s+/.test(line)) {
      const items = [];
      while (i < lines.length) {
        const lm = lines[i].match(/^\s*\d+\.\s+(.*)/);
        if (lm) { items.push(lm[1]); i++; }
        else if (!lines[i].trim() && i + 1 < lines.length && /^\s*\d+\.\s+/.test(lines[i + 1])) { i++; }
        else break;
      }
      elements.push({ type: "ol", items });
      continue;
    }

    // Paragraph
    const paraLines = [line];
    i++;
    while (i < lines.length && lines[i].trim() &&
      !/^#{1,4}\s|^```|^!\[|^\|.+\||^>\s?|^\s*[-*]\s+|^\s*\d+\.\s+|^---+\s*$/.test(lines[i])) {
      paraLines.push(lines[i]); i++;
    }
    elements.push({ type: "para", text: paraLines.join(" ") });
  }

  return { docTitle, elements };
}

// ── BUILD DOCUMENT ──

function buildDoc(mdPath) {
  const mdText = fs.readFileSync(mdPath, "utf-8");
  const { docTitle, elements } = parseMarkdown(mdText);

  const content = [];
  let prevType = null; // 跟踪上一个元素类型
  let olInstance = 0;  // 有序列表实例计数，每个 ol 独立编号

  // 表格/表注后间距：遇到后续元素时插入标准间隔（200 DXA）
  function flushTableGap() {
    if (prevType === "table" || prevType === "table-note") {
      content.push(spacer(200));
    }
  }

  // 表注由 Markdown 中 ^ 前缀显式标记，渲染器不做语义猜测

  for (const el of elements) {
    switch (el.type) {
      case "heading": {
        flushTableGap();
        const headingLevels = [null, HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3, HeadingLevel.HEADING_4];
        const headingSizes = [0, 36, 28, 24, 22];
        const headingColors = [0, C.black, C.primary, C.darkGray, C.primary];

        // #### F-xxx / IF-xxx 等 → featureHeading（彩色左边条 + 浅背景）
        // ##### F-xxx.x 等 → subFeatureHeading（浅背景，无左边条）
        const feat = (el.level === 3 || el.level === 4) ? detectFeatType(el.text) : null;
        if (feat) {
          const ft = FEAT_TYPES[feat];
          const isSub = el.level === 4;
          content.push(para(
            parseInline(el.text, { size: isSub ? 22 : 24, color: ft.dark, bold: true }),
            {
              heading: isSub ? HeadingLevel.HEADING_4 : HeadingLevel.HEADING_3,
              ...(isSub ? {} : { border: { left: { style: BorderStyle.SINGLE, size: 12, color: ft.dark, space: 8 } } }),
              shading: { fill: ft.light, type: ShadingType.CLEAR },
              indent: { left: isSub ? 240 : 120 },
            }
          ));
        } else {
          content.push(para(
            parseInline(el.text, { size: headingSizes[el.level], color: headingColors[el.level], bold: true }),
            { heading: headingLevels[el.level] }
          ));
        }
        prevType = "heading";
        break;
      }

      case "para":
        flushTableGap();
        content.push(para(parseInline(el.text), { spacing: { after: 160, line: 360 } }));
        prevType = "para";
        break;

      case "table":
        flushTableGap();
        content.push(makeTable(el.rows));
        prevType = "table";
        break;

      case "table-note":
        // 表注紧贴表格，不插入间隔；用 caption 样式（9pt 灰色）
        for (const noteLine of el.lines) {
          content.push(para(parseInline(noteLine, { size: 18, color: C.captionGray }), {
            spacing: { before: 0, after: 40 },
          }));
        }
        prevType = "table-note";
        break;

      case "callout":
        flushTableGap();
        content.push(spacer(120));
        content.push(makeCallout(el.marker, el.content));
        content.push(spacer(120));
        prevType = "callout";
        break;

      case "ul":
        flushTableGap();
        for (const item of el.items)
          content.push(para(parseInline(item), { numbering: { reference: "bullets", level: 0 }, spacing: { after: 80, line: 360 } }));
        prevType = "ul";
        break;

      case "ol":
        flushTableGap();
        olInstance++;
        for (const item of el.items)
          content.push(para(parseInline(item), { numbering: { reference: "numbers", level: 0, instance: olInstance }, spacing: { after: 80, line: 360 } }));
        prevType = "ol";
        break;

      case "code": {
        flushTableGap();
        // 图表 DSL（mermaid/plantuml/dot）：不逐行渲染源码，输出一行占位说明
        const DIAGRAM_LANGS = ["mermaid", "plantuml", "dot", "graphviz"];
        if (DIAGRAM_LANGS.includes(el.lang)) {
          content.push(para(
            txt(`[${el.lang} 图表源码，见 diagrams/ 目录]`, { size: 18, color: C.captionGray, italics: true }),
            { alignment: AlignmentType.CENTER, spacing: { before: 60, after: 60 } }
          ));
        } else {
          for (const codeLine of el.lines)
            content.push(para(txt(codeLine || " ", { size: 20, font: FONT_CODE }), {
              spacing: { after: 0 }, indent: { left: 480 },
              shading: { fill: C.bgSubtle, type: ShadingType.CLEAR },
            }));
          content.push(spacer(120));
        }
        prevType = "code";
        break;
      }

      case "quote":
        flushTableGap();
        content.push(para(parseInline(el.text, { size: 20, color: C.midGray, italics: true }), {
          indent: { left: 240 },
          border: { left: { style: BorderStyle.SINGLE, size: 10, color: C.borderGray, space: 10 } },
        }));
        prevType = "quote";
        break;

      case "image": {
        flushTableGap();
        const resolved = resolveImagePath(el.src, path.dirname(mdPath));
        if (resolved) {
          try {
            const imgBuf = fs.readFileSync(resolved);
            const dims = readPngSize(imgBuf);
            let w = IMAGE_MAX_WIDTH, h = Math.round(IMAGE_MAX_WIDTH * 0.6);
            if (dims && dims.w > 0) { const s = IMAGE_MAX_WIDTH / dims.w; w = IMAGE_MAX_WIDTH; h = Math.round(dims.h * s); }
            content.push(para(
              new ImageRun({ data: imgBuf, transformation: { width: w, height: h }, altText: { title: el.alt || "", description: el.alt || "" } }),
              { alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 } }
            ));
            if (el.alt) {
              content.push(para(txt(el.alt, { size: 18, color: C.captionGray, italics: true }), { alignment: AlignmentType.CENTER, spacing: { after: 120 } }));
            }
          } catch (e) {
            content.push(para(txt(`[图表加载失败: ${path.basename(resolved)} — ${e.message}]`, { size: 20, color: C.captionGray, italics: true }),
              { alignment: AlignmentType.CENTER, spacing: { before: 120, after: 120 } }));
          }
        } else {
          content.push(para(txt(`[图表: ${el.alt || el.src}，见 diagrams/ 目录]`, { size: 20, color: C.captionGray, italics: true }),
            { alignment: AlignmentType.CENTER, spacing: { before: 120, after: 120 } }));
        }
        prevType = "image";
        break;
      }
    }
  }
  // 末尾如果最后元素是表格/表注，也需要 flush
  flushTableGap();

  // ── COVER PAGE ──
  const coverChildren = [
    spacer(3600),
    para(txt(docTitle || path.basename(mdPath, ".md"), { size: 60, bold: true, color: C.black }), {
      indent: { left: 400 },
      border: { left: { style: BorderStyle.SINGLE, size: 20, color: C.primary, space: 16 } },
      spacing: { after: 100 },
    }),
    spacer(2000),
    new Table({
      width: { size: 5000, type: WidthType.DXA },
      columnWidths: [1200, 3800],
      rows: [["版本", "V1.0"], ["状态", "草稿"], ["日期", new Date().toISOString().slice(0, 10)]].map(([k, v]) =>
        new TableRow({ children: [
          mkCell(para(txt(k, { size: 18, color: C.captionGray })), { w: 1200, borders: noBorders, pad: padTight }),
          mkCell(para(txt(v, { size: 18, color: C.midGray })), { w: 3800, borders: noBorders, pad: padTight }),
        ]})
      ),
    }),
  ];

  // ── DOCUMENT ──
  return new Document({
    styles: {
      default: { document: { run: { font: FONT_CN, size: 22, color: C.bodyGray } } },
      paragraphStyles: [
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: 36, bold: true, font: FONT_CN, color: C.black },
          paragraph: { pageBreakBefore: true, spacing: { before: 480, after: 200 }, outlineLevel: 0,
            border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: C.primary, space: 8 } } } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: 28, bold: true, font: FONT_CN, color: C.primary },
          paragraph: { keepNext: true, spacing: { before: 360, after: 160 }, outlineLevel: 1 } },
        { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: 24, bold: true, font: FONT_CN, color: C.darkGray },
          paragraph: { keepNext: true, spacing: { before: 240, after: 120 }, outlineLevel: 2 } },
        { id: "Heading4", name: "Heading 4", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: 22, bold: true, font: FONT_CN, color: C.primary },
          paragraph: { keepNext: true, spacing: { before: 200, after: 100 }, outlineLevel: 3 } },
      ],
    },
    numbering: {
      config: [
        { reference: "bullets", levels: [
          { level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
          { level: 1, format: LevelFormat.BULLET, text: "\u25E6", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 1080, hanging: 360 } } } },
        ]},
        { reference: "numbers", levels: [
          { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
          { level: 1, format: LevelFormat.DECIMAL, text: "%1.%2", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 1080, hanging: 420 } } } },
        ]},
      ],
    },
    sections: [
      // Section 1: Cover (no header/footer)
      {
        properties: { page: { size: { width: PAGE_W, height: PAGE_H }, margin: MARGIN } },
        children: coverChildren,
      },
      // Section 2: Main content
      {
        properties: { page: { size: { width: PAGE_W, height: PAGE_H }, margin: MARGIN } },
        headers: {
          default: new Header({ children: [
            para([
              txt(docTitle || "", { size: 16, color: C.captionGray }),
            ], {
              alignment: AlignmentType.RIGHT,
              border: { bottom: { style: BorderStyle.SINGLE, size: 2, color: C.dividerGray, space: 6 } },
            }),
          ]}),
        },
        footers: {
          default: new Footer({ children: [
            para([
              txt("Page ", { size: 16, color: C.captionGray, font: FONT_EN }),
              new TextRun({ children: [PageNumber.CURRENT], font: FONT_EN, size: 16, color: C.captionGray }),
            ], {
              alignment: AlignmentType.CENTER,
              border: { top: { style: BorderStyle.SINGLE, size: 1, color: C.dividerGray, space: 6 } },
            }),
          ]}),
        },
        children: content,
      },
    ],
  });
}

// ── CLI ──
const mdPath = process.argv[2];
if (!mdPath) { console.error("用法: node md2docx.mjs <PRD.md>"); process.exit(1); }
if (!fs.existsSync(mdPath)) { console.error(`错误: 文件不存在 — ${mdPath}`); process.exit(1); }

const outPath = mdPath.replace(/\.md$/, ".docx");
Packer.toBuffer(buildDoc(mdPath)).then(buf => {
  fs.writeFileSync(outPath, buf);
  console.log(`✓ 已生成: ${outPath}`);
});
