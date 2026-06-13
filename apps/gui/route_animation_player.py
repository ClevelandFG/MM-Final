"""B8 路线动画导出入口。

第一版是无 GUI 依赖的轻量播放器/导出器骨架：负责加载 RoutePlan、
调用 `mm_final.visualization` 后端并写出 README、表格、帧和动画文件。
后续 PySide6/Qt 播放器应复用同一套后端。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from mm_final.visualization import export_route_animation_package
from mm_final.visualization.exports import VisualizationInputError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export B8 route animation assets from a RoutePlan JSON.")
    parser.add_argument("route_plan", type=Path, help="RoutePlan JSON path.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory. Defaults to outputs/b8/<timestamp>.")
    parser.add_argument("--road-network", type=Path, default=None, help="Optional road network TSV path.")
    parser.add_argument("--layout", type=Path, default=None, help="Optional layout JSON path.")
    parser.add_argument("--render-frames", action="store_true", help="Export start/end PNG frames.")
    parser.add_argument("--gif", action="store_true", help="Export route-animation.gif.")
    parser.add_argument("--mp4", action="store_true", help="Export silent route-animation.mp4.")
    parser.add_argument("--fps", type=int, default=10, help="Animation frames per second.")
    parser.add_argument(
        "--model-hours-per-second",
        type=float,
        default=1.0,
        help="Playback scale. Default: 1 real second represents 1 model hour.",
    )
    parser.add_argument(
        "--allow-debug-invalid",
        action="store_true",
        help="Allow invalid candidates to be exported as debug-only assets. Formal exports stay strict by default.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    kwargs = {
        "output_dir": args.output_dir,
        "strict_final": not args.allow_debug_invalid,
        "render_frames": args.render_frames,
        "export_gif": args.gif,
        "export_mp4": args.mp4,
        "fps": args.fps,
        "model_hours_per_second": args.model_hours_per_second,
    }
    if args.road_network is not None:
        kwargs["road_network_path"] = args.road_network
    if args.layout is not None:
        kwargs["layout_path"] = args.layout

    try:
        result = export_route_animation_package(args.route_plan, **kwargs)
    except VisualizationInputError as exc:
        print(f"B8 export rejected: {exc}")
        if exc.audit_result is not None:
            for error in exc.audit_result.errors:
                print(f"ERROR: {error}")
            for warning in exc.audit_result.warnings:
                print(f"WARNING: {warning}")
        return 2

    print(f"B8 export written to: {result.output_dir}")
    for file_path in result.files:
        print(f"- {file_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
