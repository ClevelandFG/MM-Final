"""B8 路线动画导出包。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import csv
import hashlib
import json
import subprocess
from typing import Optional, Union

from mm_final.contracts import SCHEMA_VERSION, AuditResult, RoutePlan, ValidationResult, load_route_plan_json
from mm_final.evaluation import EvaluationParameters, EvaluationResult, audit_validation_result, evaluate_route_plan
from mm_final.network import DEFAULT_ROAD_NETWORK_PATH, RoadNetwork, load_road_network
from mm_final.visualization.layout import DEFAULT_LAYOUT_PATH, RoadNetworkLayout, load_layout_json, make_fallback_layout
from mm_final.visualization.rendering import (
    RenderOptions,
    export_animation_gif,
    export_animation_mp4,
    render_snapshot_png,
)
from mm_final.visualization.timeline import RouteAnimationTimeline


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class VisualizationInputError(ValueError):
    """输入方案不能作为正式 B8 可视化结果。"""

    def __init__(self, message: str, audit_result: Optional[AuditResult] = None):
        super().__init__(message)
        self.audit_result = audit_result


@dataclass(frozen=True)
class DataVersionInfo:
    """导出物版本锁定信息。"""

    git_commit: str
    road_network_path: str
    road_network_sha256: str
    route_plan_contract_version: str

    @classmethod
    def collect(cls, road_network_path: Union[str, Path] = DEFAULT_ROAD_NETWORK_PATH) -> "DataVersionInfo":
        path = Path(road_network_path)
        return cls(
            git_commit=_git_commit(),
            road_network_path=_relative_to_root(path),
            road_network_sha256=_sha256(path),
            route_plan_contract_version=SCHEMA_VERSION,
        )

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class RouteAnimationBundle:
    """B8 可视化入口的核心数据包。"""

    plan: RoutePlan
    audit_result: AuditResult
    evaluation_result: EvaluationResult
    timeline: RouteAnimationTimeline
    layout: RoadNetworkLayout
    data_version: DataVersionInfo
    formal_result: bool
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan.plan_id,
            "source": self.plan.source,
            "formal_result": self.formal_result,
            "warnings": list(self.warnings),
            "audit": {
                "schema_valid": self.audit_result.schema_valid,
                "coverage_valid": self.audit_result.coverage_valid,
                "route_valid": self.audit_result.route_valid,
                "metric_valid": self.audit_result.metric_valid,
                "errors": list(self.audit_result.errors),
                "warnings": list(self.audit_result.warnings),
            },
            "data_version": self.data_version.to_dict(),
            "timeline": self.timeline.to_dict(),
        }


@dataclass(frozen=True)
class RouteAnimationExportResult:
    """B8 导出结果清单。"""

    output_dir: Path
    files: tuple[Path, ...]
    bundle: RouteAnimationBundle


def build_route_animation_bundle(
    plan: RoutePlan,
    road_network: RoadNetwork,
    *,
    parameters: Optional[EvaluationParameters] = None,
    layout: Optional[RoadNetworkLayout] = None,
    strict_final: bool = True,
    data_version: Optional[DataVersionInfo] = None,
) -> RouteAnimationBundle:
    """构造可视化数据包，默认要求通过 B3 final 审计。"""

    params = EvaluationParameters.from_route_plan(plan) if parameters is None else parameters
    audit = audit_validation_result(ValidationResult(plan=plan, diagnostics=[]), road_network, params, mode="final")
    formal = audit.schema_valid and audit.coverage_valid and audit.route_valid and audit.metric_valid
    if strict_final and not formal:
        raise VisualizationInputError("RoutePlan failed B3 final audit and cannot enter formal B8 export.", audit)

    evaluation = evaluate_route_plan(plan, road_network, params)
    timeline = RouteAnimationTimeline.from_route_plan(plan, road_network, params)
    resolved_layout = layout or _load_default_layout_or_fallback(road_network)
    warnings = tuple(audit.warnings)
    if not formal:
        warnings = ("debug-only visualization: this candidate is not a formal result.", *warnings)
    return RouteAnimationBundle(
        plan=plan,
        audit_result=audit,
        evaluation_result=evaluation,
        timeline=timeline,
        layout=resolved_layout,
        data_version=data_version or DataVersionInfo.collect(),
        formal_result=formal,
        warnings=warnings,
    )


def export_route_animation_package(
    route_plan_path: Union[str, Path],
    output_dir: Optional[Union[str, Path]] = None,
    *,
    road_network_path: Union[str, Path] = DEFAULT_ROAD_NETWORK_PATH,
    layout_path: Union[str, Path] = DEFAULT_LAYOUT_PATH,
    strict_final: bool = True,
    render_frames: bool = False,
    export_gif: bool = False,
    export_mp4: bool = False,
    fps: int = 10,
    model_hours_per_second: float = 1.0,
) -> RouteAnimationExportResult:
    """导出 B8 路线动画包。"""

    plan_path = Path(route_plan_path)
    validation = load_route_plan_json(plan_path)
    network_result = load_road_network(road_network_path)
    if network_result.network is None:
        details = "; ".join(item.to_text() for item in network_result.errors)
        raise VisualizationInputError(f"Road network failed to load: {details}")
    if validation.plan is None:
        raise VisualizationInputError(
            "RoutePlan failed B0 schema validation and cannot enter formal B8 export.",
            audit_result=None,
        )

    layout = load_layout_json(layout_path) if Path(layout_path).exists() else make_fallback_layout(network_result.network)
    bundle = build_route_animation_bundle(
        validation.plan,
        network_result.network,
        layout=layout,
        strict_final=strict_final,
        data_version=DataVersionInfo.collect(road_network_path),
    )

    export_dir = Path(output_dir) if output_dir is not None else _default_output_dir()
    export_dir.mkdir(parents=True, exist_ok=True)
    files = [
        _write_json(export_dir / "timeline-summary.json", bundle.to_dict()),
        _write_route_summary_csv(export_dir / "route-summary.csv", bundle),
        _write_readme(export_dir / "README.md", bundle, plan_path, fps, model_hours_per_second),
    ]

    if render_frames:
        options = RenderOptions(title=f"{bundle.plan.plan_id} route animation")
        files.append(
            render_snapshot_png(
                bundle.timeline,
                network_result.network,
                bundle.layout,
                export_dir / "frame-start.png",
                time_hour=0.0,
                options=options,
            )
        )
        files.append(
            render_snapshot_png(
                bundle.timeline,
                network_result.network,
                bundle.layout,
                export_dir / "frame-end.png",
                time_hour=bundle.timeline.completion_time_hour,
                options=options,
            )
        )
    if export_gif:
        files.append(
            export_animation_gif(
                bundle.timeline,
                network_result.network,
                bundle.layout,
                export_dir / "route-animation.gif",
                fps=fps,
                model_hours_per_second=model_hours_per_second,
            )
        )
    if export_mp4:
        files.append(
            export_animation_mp4(
                bundle.timeline,
                network_result.network,
                bundle.layout,
                export_dir / "route-animation.mp4",
                fps=fps,
                model_hours_per_second=model_hours_per_second,
            )
        )

    return RouteAnimationExportResult(output_dir=export_dir, files=tuple(files), bundle=bundle)


def _load_default_layout_or_fallback(road_network: RoadNetwork) -> RoadNetworkLayout:
    return load_layout_json(DEFAULT_LAYOUT_PATH) if DEFAULT_LAYOUT_PATH.exists() else make_fallback_layout(road_network)


def _write_json(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_route_summary_csv(path: Path, bundle: RouteAnimationBundle) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["route_id", "distance_km", "total_time_hour", "segment_count"],
        )
        writer.writeheader()
        for route_id, segments in bundle.timeline.segments_by_route_id.items():
            writer.writerow(
                {
                    "route_id": route_id,
                    "distance_km": bundle.timeline.route_distance_km[route_id],
                    "total_time_hour": bundle.timeline.route_total_time_hour[route_id],
                    "segment_count": len(segments),
                }
            )
    return path


def _write_readme(
    path: Path,
    bundle: RouteAnimationBundle,
    input_path: Path,
    fps: int,
    model_hours_per_second: float,
) -> Path:
    audit = bundle.audit_result
    lines = [
        "# B8 Route Animation Export",
        "",
        f"- plan_id: {bundle.plan.plan_id}",
        f"- source: {bundle.plan.source}",
        f"- input_path: {_relative_to_root(input_path)}",
        f"- formal_result: {bundle.formal_result}",
        f"- completion_time_hour: {bundle.timeline.completion_time_hour:.6f}",
        f"- playback_scale: 1 second = {model_hours_per_second:g} model hour(s)",
        f"- fps: {fps}",
        f"- git_commit: {bundle.data_version.git_commit}",
        f"- road_network_path: {bundle.data_version.road_network_path}",
        f"- road_network_sha256: {bundle.data_version.road_network_sha256}",
        f"- route_plan_contract_version: {bundle.data_version.route_plan_contract_version}",
        "",
        "## Audit",
        "",
        f"- schema_valid: {audit.schema_valid}",
        f"- coverage_valid: {audit.coverage_valid}",
        f"- route_valid: {audit.route_valid}",
        f"- metric_valid: {audit.metric_valid}",
    ]
    if not bundle.formal_result:
        lines.extend(["", "## Warnings", "", "- CONTRACT MISMATCH: this export is debug-only."])
    for warning in bundle.warnings:
        lines.append(f"- {warning}")
    if audit.errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in audit.errors)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _default_output_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return PROJECT_ROOT / "outputs" / "b8" / timestamp


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:  # pragma: no cover - 非 Git 环境仅影响复现元数据
        return "unknown"
    return result.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_to_root(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)
