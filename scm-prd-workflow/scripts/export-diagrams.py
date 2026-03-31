#!/usr/bin/env python3
"""
export-diagrams.py — 批量导出图表为 PNG 图片

遍历指定目录，将 .diagram.yaml 和 .mermaid 文件导出为 PNG。
- .diagram.yaml → yaml2svg.py → .svg + .png (需 cairosvg)
- .mermaid → mermaid.ink API → .png (需联网)

用法:
    python export-diagrams.py <diagrams目录>
    python export-diagrams.py <diagrams目录> --force

依赖: urllib (标准库), yaml2svg.py (同目录)
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

# =============================================================================
# 常量
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
YAML2SVG = SCRIPT_DIR / "yaml2svg.py"

# =============================================================================
# 辅助函数
# =============================================================================


def is_newer(target: Path, source: Path) -> bool:
    """target 文件存在且修改时间晚于 source 时返回 True。"""
    if not target.exists():
        return False
    return target.stat().st_mtime >= source.stat().st_mtime


def export_diagram_yaml(yaml_path: Path, force: bool) -> str:
    """
    导出 .diagram.yaml → .png（经由 yaml2svg.py）。

    返回: "success" | "skipped" | "failed"
    """
    png_path = yaml_path.with_suffix("").with_suffix(".png")  # foo.diagram.yaml → foo.png

    # 增量检查
    if not force and is_newer(png_path, yaml_path):
        print(f"  跳过 (已最新): {yaml_path.name}")
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


def export_mermaid(mermaid_path: Path, force: bool) -> str:
    """
    导出 .mermaid → .png（经由 mermaid.ink API）。

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

    # base64 URL-safe 编码
    encoded = base64.urlsafe_b64encode(content.encode("utf-8")).decode("ascii")
    url = f"https://mermaid.ink/img/{encoded}?type=png&bgColor=white"

    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (scm-prd-skill)"})
        resp = urlopen(req, timeout=30)
        png_path.write_bytes(resp.read())
        print(f"  导出: {mermaid_path.name} -> .png")
        return "success"
    except URLError as exc:
        reason = getattr(exc, 'reason', str(exc))
        print(f"  跳过 (网络不可用): {mermaid_path.name} — {reason}", file=sys.stderr)
        return "failed"
    except Exception as exc:
        print(f"  失败: {mermaid_path.name} — {exc}", file=sys.stderr)
        return "failed"


# =============================================================================
# 主流程
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="批量导出图表为 PNG 图片",
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

    success = 0
    skipped = 0
    failed = 0

    # 导出 .diagram.yaml
    for f in yaml_files:
        result = export_diagram_yaml(f, force=args.force)
        if result == "success":
            success += 1
        elif result == "skipped":
            skipped += 1
        else:
            failed += 1

    # 导出 .mermaid
    for f in mermaid_files:
        result = export_mermaid(f, force=args.force)
        if result == "success":
            success += 1
        elif result == "skipped":
            skipped += 1
        else:
            failed += 1

    print(f"\n\u2713 导出完成: {success} 成功, {skipped} 跳过, {failed} 失败")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
