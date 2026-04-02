#!/usr/bin/env node
/**
 * fix-bundle-fileproto.mjs — 修复打包后 HTML 的 file:// 协议兼容性
 *
 * 背景知识（来自实际排障经验）：
 * - Parcel 等工具输出 <script type="module">，浏览器对 file:// 协议拒绝执行 ES modules
 * - modulepreload 在 file:// 下也无效
 * - 内联 JS 时若包含 </script> 字面量，HTML 解析器会提前截断 script 块
 *   → 修复方式：将 JS 中的 </script 转义为 <\/script
 * - String.prototype.replace 的替换字符串中 $& $1 等有特殊含义
 *   → 修复方式：用函数作为替换参数，避免 $ 被解释
 *
 * 本脚本用于 web-artifacts-builder 打包后的安全网检查。
 * 原型 HTML 应由打包工具（Parcel + html-inline）生成为自包含文件，
 * 本脚本仅处理残留的 module/preload 问题，不负责下载外部 CDN 资源。
 * 如原型仍依赖外部 CDN，应从源头修复（使用打包工具或手动内联）。
 *
 * 用法: node fix-bundle-fileproto.mjs <bundle.html路径>
 */
import fs from "fs";

const filePath = process.argv[2];
if (!filePath) {
  console.error("用法: node fix-bundle-fileproto.mjs <bundle.html>");
  process.exit(1);
}
if (!fs.existsSync(filePath)) {
  console.error(`错误: 文件不存在 — ${filePath}`);
  process.exit(1);
}

let html = fs.readFileSync(filePath, "utf-8");
const fixes = [];

// ── 检查：外部 CDN 依赖预警 ──
const cdnScripts = [...html.matchAll(/<script\s+src\s*=\s*["'](https?:\/\/[^"']+)["']/gi)];
const cdnLinks = [...html.matchAll(/<link\s+[^>]*href\s*=\s*["'](https?:\/\/[^"']+)["']/gi)];
if (cdnScripts.length + cdnLinks.length > 0) {
  console.warn(`⚠ 检测到 ${cdnScripts.length + cdnLinks.length} 个外部 CDN 依赖，原型离线无法使用：`);
  for (const m of cdnScripts) console.warn(`  - ${m[1]}`);
  for (const m of cdnLinks) console.warn(`  - ${m[1]}`);
  console.warn("  建议：使用 web-artifacts-builder 打包，或手动内联所有依赖。");
}

// ── 修复1：移除 type="module" ──
const moduleFixed = html.replace(/<script\s+type\s*=\s*["']module["']/gi, "<script");
if (moduleFixed !== html) { html = moduleFixed; fixes.push('移除 type="module"'); }

// ── 修复2：移除 modulepreload ──
const preloadFixed = html.replace(/<link\s+[^>]*rel\s*=\s*["']modulepreload["'][^>]*>/gi, "");
if (preloadFixed !== html) { html = preloadFixed; fixes.push("移除 modulepreload"); }

// ── 修复3：确保 charset（防止中文乱码）──
if (!/<meta\s+charset/i.test(html)) {
  html = html.replace(/<head>/i, '<head>\n<meta charset="UTF-8">');
  fixes.push("补充 charset");
}

// ── 写回 ──
if (fixes.length > 0) {
  fs.writeFileSync(filePath, html, "utf-8");
  console.log(`✓ 已修复 (${fixes.length} 项): ${filePath}`);
  fixes.forEach((f) => console.log(`  - ${f}`));
} else if (cdnScripts.length + cdnLinks.length === 0) {
  console.log(`- 无需修复: ${filePath}`);
}
