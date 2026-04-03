#!/usr/bin/env python3
"""
export-diagrams.py — 批量生成 draw.io 并导出图表为 PNG 图片

遍历指定目录，处理 .diagram.yaml 和 .mermaid 文件：
- .diagram.yaml → yaml2drawio.py → .drawio（默认生成，供用户手动编辑）
- .diagram.yaml → yaml2svg.py → .svg + .png (需 cairosvg)
- .mermaid → mmdc 本地 → .png (优先) 或 mermaid.ink API → .png (远程兜底)

.drawio 生成失败不阻断 PNG 导出流程。

用法:
    python export-diagrams.py <diagrams目录>
    python export-diagrams.py <diagrams目录> --force

依赖: urllib (标准库), yaml2drawio.py + yaml2svg.py (同目录)
可选: cairosvg (pip install cairosvg)
兼容: Python 3.8+
"""

import sys
import os
import base64
import subprocess
import argparse
from pathlib import Path
from urllib.request import urlretrieve, Request, urlopen
from urllib.error import URLError
import time

# =============================================================================
# 常量
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
YAML2SVG = SCRIPT_DIR / "yaml2svg.py"
YAML2DRAWIO = SCRIPT_DIR / "yaml2drawio.py"


def _load_config_flag(key: str, default: bool = True) -> bool:
    """从 .scm-prd-config.yaml 读取布尔配置项。"""
    import json
    # 先查 JSON 缓存
    for candidate in [Path.cwd(), Path.cwd().parent]:
        json_cfg = candidate / ".scm-prd-env-cache.json"
        if json_cfg.exists():
            try:
                data = json.loads(json_cfg.read_text(encoding="utf-8"))
                if key in data:
                    return bool(data[key])
            except Exception:
                pass
    # 再查 YAML 配置
    for candidate in [Path.cwd(), Path.cwd().parent]:
        yaml_cfg = candidate / ".scm-prd-config.yaml"
        if yaml_cfg.exists():
            try:
                text = yaml_cfg.read_text(encoding="utf-8")
                for line in text.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith(f"{key}:"):
                        val = stripped.split(":", 1)[1].strip().lower()
                        return val in ("true", "yes", "1")
            except Exception:
                pass
    return default

# =============================================================================
# 辅助函数
# =============================================================================


def is_newer(target: Path, source: Path) -> bool:
    """target 文件存在且修改时间晚于 source 时返回 True。"""
    if not target.exists():
        return False
    return target.stat().st_mtime >= source.stat().st_mtime


def generate_drawio(yaml_path: Path, force: bool) -> str:
    """
    转换 .diagram.yaml → .drawio（经由 yaml2drawio.py）。

    .drawio 文件始终保留供用户手动编辑，此步骤独立于 PNG 导出。
    返回: "success" | "skipped" | "failed"
    """
    drawio_path = yaml_path.with_suffix("").with_suffix(".drawio")  # foo.diagram.yaml → foo.drawio

    # 增量检查
    if not force and is_newer(drawio_path, yaml_path):
        print(f"  跳过 drawio (已最新): {yaml_path.name}")
        return "skipped"

    if not YAML2DRAWIO.exists():
        print(f"  跳过 drawio: 未找到 {YAML2DRAWIO}", file=sys.stderr)
        return "failed"

    try:
        result = subprocess.run(
            [sys.executable, str(YAML2DRAWIO), str(yaml_path), str(drawio_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            print(f"  drawio 失败: {yaml_path.name}", file=sys.stderr)
            if stderr:
                print(f"    {stderr}", file=sys.stderr)
            return "failed"
        print(f"  生成: {yaml_path.name} -> .drawio")
        return "success"
    except FileNotFoundError:
        print(f"  drawio 失败: 无法执行 Python 解释器 ({sys.executable})", file=sys.stderr)
        return "failed"
    except subprocess.TimeoutExpired:
        print(f"  drawio 失败: 超时 — {yaml_path.name}", file=sys.stderr)
        return "failed"
    except Exception as exc:
        print(f"  drawio 失败: {yaml_path.name} — {exc}", file=sys.stderr)
        return "failed"


def export_diagram_yaml(yaml_path: Path, force: bool) -> str:
    """
    导出 .diagram.yaml → .png（经由 yaml2svg.py）。

    返回: "success" | "skipped" | "failed"
    """
    png_path = yaml_path.with_suffix("").with_suffix(".png")  # foo.diagram.yaml → foo.png

    # 增量检查
    if not force and is_newer(png_path, yaml_path):
        print(f"  跳过 png (已最新): {yaml_path.name}")
        return "skipped"

    if not YAML2SVG.exists():
        print(f"  失败: 未找到 {YAML2SVG}", file=sys.stderr)
        return "failed"

    try:
        result = subprocess.run(
            [sys.executable, str(YAML2SVG), str(yaml_path), "--png"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            print(f"  失败: {yaml_path.name}", file=sys.stderr)
            if stderr:
                print(f"    {stderr}", file=sys.stderr)
            return "failed"
        print(f"  导出: {yaml_path.name} -> .png")
        return "success"
    except FileNotFoundError:
        print(f"  失败: 无法执行 Python 解释器 ({sys.executable})", file=sys.stderr)
        return "failed"
    except subprocess.TimeoutExpired:
        print(f"  失败: 超时 — {yaml_path.name}", file=sys.stderr)
        return "failed"
    except Exception as exc:
        print(f"  失败: {yaml_path.name} — {exc}", file=sys.stderr)
        return "failed"


def _mmdc_available() -> bool:
    """检测本地 mermaid-cli (mmdc) 是否可用。"""
    import shutil
    return shutil.which("mmdc") is not None


def _export_mermaid_mmdc(mermaid_path: Path, png_path: Path) -> bool:
    """尝试用本地 mmdc 导出，成功返回 True。附带 CJK 字体栈和跨平台 Puppeteer 配置。"""
    scripts_dir = Path(__file__).resolve().parent
    css_file = scripts_dir / "mmdc-cjk.css"
    puppeteer_cfg = scripts_dir / "mmdc-puppeteer.json"

    cmd = ["mmdc", "-i", str(mermaid_path), "-o", str(png_path), "-b", "white", "-s", "2"]
    if css_file.exists():
        cmd += ["-C", str(css_file)]
    if puppeteer_cfg.exists():
        cmd += ["-p", str(puppeteer_cfg)]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode == 0 and png_path.exists():
            print(f"  导出 (mmdc): {mermaid_path.name} -> .png")
            return True
        return False
    except Exception:
        return False


def _export_mermaid_ink(mermaid_path: Path, png_path: Path, content: str) -> bool:
    """尝试用 mermaid.ink API 导出，成功返回 True。
    注意: 会将图表内容发送到第三方服务器，含敏感业务流程时建议安装 mmdc 本地渲染。
    """
    encoded = base64.urlsafe_b64encode(content.encode("utf-8")).decode("ascii")
    url = f"https://mermaid.ink/img/{encoded}?type=png&bgColor=white"
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (scm-prd-skill)"})
        resp = urlopen(req, timeout=30)
        png_path.write_bytes(resp.read())
        print(f"  导出 (mermaid.ink): {mermaid_path.name} -> .png")
        return True
    except Exception:
        return False


def export_mermaid(mermaid_path: Path, force: bool) -> str:
    """
    导出 .mermaid → .png。
    优先级：本地 mmdc → mermaid.ink API → 失败。

    返回: "success" | "skipped" | "failed"
    """
    png_path = mermaid_path.with_suffix(".png")

    # 增量检查
    if not force and is_newer(png_path, mermaid_path):
        print(f"  跳过 (已最新): {mermaid_path.name}")
        return "skipped"

    try:
        content = mermaid_path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"  失败: 无法读取 {mermaid_path.name} — {exc}", file=sys.stderr)
        return "failed"

    # 1. 本地 mmdc 优先
    if _mmdc_available() and _export_mermaid_mmdc(mermaid_path, png_path):
        return "success"

    # 2. mermaid.ink 远程兜底（隐私提示：图表内容将发送到第三方服务器）
    if not _load_config_flag("allow_remote_render", default=True):
        print(f"  跳过远程渲染: allow_remote_render=false — {mermaid_path.name}", file=sys.stderr)
        print("    如需远程渲染，在 .scm-prd-config.yaml 中设置 allow_remote_render: true", file=sys.stderr)
        print(f"  失败: {mermaid_path.name} — mmdc 不可用且远程渲染已禁用", file=sys.stderr)
        return "failed"
    if not hasattr(export_mermaid, "_ink_warned"):
        print("  ⚠ 隐私提示: mmdc 不可用，将使用 mermaid.ink 远程渲染（图表内容会发送到第三方服务器）", file=sys.stderr)
        print("    建议安装本地渲染: npm install -g @mermaid-js/mermaid-cli", file=sys.stderr)
        print("    或在 .scm-prd-config.yaml 中设置 allow_remote_render: false 永久禁用", file=sys.stderr)
        export_mermaid._ink_warned = True
    if _export_mermaid_ink(mermaid_path, png_path, content):
        return "success"

    print(f"  失败: {mermaid_path.name} — mmdc 不可用且 mermaid.ink 不可达", file=sys.stderr)
    return "failed"


# =============================================================================
# 主流程
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="批量导出图表: .diagram.yaml → .drawio + .png, .mermaid → .png",
    )
    parser.add_argument(
        "directory",
        type=str,
        help="图表目录路径 (diagrams/)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="忽略时间戳，全部重新导出",
    )
    args = parser.parse_args()

    diagrams_dir = Path(args.directory).resolve()
    if not diagrams_dir.is_dir():
        print(f"错误: 目录不存在 — {diagrams_dir}", file=sys.stderr)
        return 1

    # 收集文件
    yaml_files = sorted(diagrams_dir.glob("*.diagram.yaml"))
    mermaid_files = sorted(diagrams_dir.glob("*.mermaid"))

    total = len(yaml_files) + len(mermaid_files)
    if total == 0:
        print(f"未找到图表文件 (.diagram.yaml / .mermaid): {diagrams_dir}")
        return 0

    print(f"扫描目录: {diagrams_dir}")
    print(f"发现 {len(yaml_files)} 个 .diagram.yaml, {len(mermaid_files)} 个 .mermaid\n")

    drawio_success = 0
    drawio_skipped = 0
    drawio_failed = 0
    png_success = 0
    png_skipped = 0
    png_failed = 0

    # 阶段1: .diagram.yaml → .drawio（默认生成，供用户手动编辑）
    if yaml_files:
        print("--- 生成 .drawio ---")
        for f in yaml_files:
            result = generate_drawio(f, force=args.force)
            if result == "success":
                drawio_success += 1
            elif result == "skipped":
                drawio_skipped += 1
            else:
                drawio_failed += 1
        print()

    # 阶段2: .diagram.yaml → .png（经由 yaml2svg.py，用于 Word 嵌入）
    if yaml_files:
        print("--- 导出 PNG ---")
        for f in yaml_files:
            result = export_diagram_yaml(f, force=args.force)
            if result == "success":
                png_success += 1
            elif result == "skipped":
                png_skipped += 1
            else:
                png_failed += 1

    # 阶段3: .mermaid → .png（经由 mmdc 本地 或 mermaid.ink API）
    _last_ink_call = 0
    for f in mermaid_files:
        # mermaid.ink API 限流：至少间隔 1 秒，避免批量导出触发 429
        now = time.monotonic()
        if now - _last_ink_call < 1.0:
            time.sleep(1.0 - (now - _last_ink_call))
        result = export_mermaid(f, force=args.force)
        _last_ink_call = time.monotonic()
        if result == "success":
            png_success += 1
        elif result == "skipped":
            png_skipped += 1
        else:
            png_failed += 1

    # 汇总
    if yaml_files:
        print(f"\n\u2713 drawio: {drawio_success} 成功, {drawio_skipped} 跳过, {drawio_failed} 失败")
    print(f"\u2713 png:    {png_success} 成功, {png_skipped} 跳过, {png_failed} 失败")

    total_failed = drawio_failed + png_failed
    return 1 if total_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
