"""第 (4) 问固定组数参数网格批量重优化脚本。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, is_dataclass
from itertools import product
from pathlib import Path
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mm_final.evaluation.route_plan_auditor import audit_route_plan
from mm_final.evaluation.route_plan_evaluator import EvaluationParameters, evaluate_route_plan
from mm_final.network import REQUIRED_VISIT_NODES, load_road_network
from mm_final.routing.distance_matrix import DistanceMatrix
from mm_final.routing.export import candidate_to_route_plan
from mm_final.routing.mtsp_solver import MTSP_Solver
from mm_final.routing.scoring import ObjectiveSpec


DEFAULT_T_VALUES = (1.0, 1.5, 2.0, 2.5, 3.0)
DEFAULT_T_SMALL_VALUES = (0.5, 1.0, 1.5)
DEFAULT_SPEED_VALUES = (25.0, 30.0, 35.0, 40.0, 45.0)
DEFAULT_GROUP_COUNT = 3
DEFAULT_TIME_LIMIT_SECONDS = 60.0
DEFAULT_ITERATIONS = 50
DEFAULT_SEED = 20260614
NO_HARD_TIME_LIMIT_HOUR = 1_000_000.0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    scenarios = build_scenarios(args.T_values, args.t_values, args.v_values)
    total = len(scenarios)

    print(f"参数网格：{len(args.T_values)} x {len(args.t_values)} x {len(args.v_values)} = {total} 组")
    print(f"固定组数 k={args.group_count}，每组重新运行固定组数最短完成时间优化")
    print(f"单组求解预算：{args.time_limit_seconds:g} s，iterations={args.iterations}")
    if args.dry_run:
        for index, scenario in enumerate(scenarios, start=1):
            print(f"[dry-run] {index:02d}/{total} {scenario_id(*scenario)}")
        return 0

    output_dir = args.output_dir.resolve()
    plans_dir = output_dir / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)

    network_result = load_road_network(args.road_network)
    if not network_result.is_valid or network_result.network is None:
        for diagnostic in network_result.diagnostics:
            print(diagnostic.to_text(), file=sys.stderr)
        return 2
    network = network_result.network
    distance_matrix = DistanceMatrix.from_network(network)

    records: list[dict[str, Any]] = []
    batch_start = time.time()
    for index, (T_hour, t_hour, speed_km_per_hour) in enumerate(scenarios, start=1):
        sid = scenario_id(T_hour, t_hour, speed_km_per_hour)
        seed = args.seed + index - 1 if args.seed is not None else None
        print(f"开始：{index}/{total} {sid}")
        scenario_started = time.time()
        try:
            record = solve_one_scenario(
                distance_matrix=distance_matrix,
                network=network,
                output_dir=output_dir,
                plans_dir=plans_dir,
                scenario_index=index,
                scenario_id=sid,
                T_hour=T_hour,
                t_hour=t_hour,
                speed_km_per_hour=speed_km_per_hour,
                group_count=args.group_count,
                time_limit_seconds=args.time_limit_seconds,
                iterations=args.iterations,
                seed=seed,
            )
        except Exception as exc:  # pragma: no cover - 批处理入口保留单情景容错
            if args.fail_fast:
                raise
            record = failed_record(
                scenario_index=index,
                scenario_id=sid,
                T_hour=T_hour,
                t_hour=t_hour,
                speed_km_per_hour=speed_km_per_hour,
                group_count=args.group_count,
                seed=seed,
                error=str(exc),
                elapsed_seconds=time.time() - scenario_started,
            )
        records.append(record)
        completion = record.get("completion_time_hour")
        completion_text = "-" if completion is None else f"{float(completion):.4g} h"
        print(f"已计算：{index}/{total} {sid} status={record['status']} completion={completion_text}")

    metadata = {
        "problem": "q4_fixed_group_parameter_grid",
        "objective": "fixed k routes, minimize completion_time_hour",
        "group_count": args.group_count,
        "T_values": list(args.T_values),
        "t_values": list(args.t_values),
        "speed_values": list(args.v_values),
        "time_limit_seconds": args.time_limit_seconds,
        "iterations": args.iterations,
        "seed": args.seed,
        "scenario_count": total,
        "elapsed_seconds": time.time() - batch_start,
        "notes": [
            "Each scenario reruns the fixed-group solver.",
            "The optimization target is lexicographic: penalty, completion time, time range, total distance, distance range.",
            "The result is heuristic unless a separate proof is provided.",
        ],
    }
    write_outputs(output_dir, metadata, records)
    print(f"批量结果已写入：{output_dir}")
    return 0


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="固定 k 组下，对 T/t/v 三参数全组合网格逐点重新优化并导出结果。",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "parameter_batch")
    parser.add_argument("--road-network", type=Path, default=None)
    parser.add_argument("--group-count", type=int, default=DEFAULT_GROUP_COUNT)
    parser.add_argument("--T-values", type=parse_float_list, default=DEFAULT_T_VALUES)
    parser.add_argument("--t-values", type=parse_float_list, default=DEFAULT_T_SMALL_VALUES)
    parser.add_argument("--v-values", type=parse_float_list, default=DEFAULT_SPEED_VALUES)
    parser.add_argument("--time-limit-seconds", type=float, default=DEFAULT_TIME_LIMIT_SECONDS)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--dry-run", action="store_true", help="只打印参数网格和进度，不运行求解器。")
    parser.add_argument("--fail-fast", action="store_true", help="任一情景失败时立即退出。")
    args = parser.parse_args(argv)
    validate_args(args)
    return args


def validate_args(args: argparse.Namespace) -> None:
    if args.group_count <= 0:
        raise SystemExit("--group-count must be > 0")
    if args.time_limit_seconds <= 0:
        raise SystemExit("--time-limit-seconds must be > 0")
    if args.iterations <= 0:
        raise SystemExit("--iterations must be > 0")
    for name in ("T_values", "t_values", "v_values"):
        values = getattr(args, name)
        if not values:
            raise SystemExit(f"--{name.replace('_', '-')} must not be empty")
    if any(value < 0 for value in args.T_values):
        raise SystemExit("--T-values must be >= 0")
    if any(value < 0 for value in args.t_values):
        raise SystemExit("--t-values must be >= 0")
    if any(value <= 0 for value in args.v_values):
        raise SystemExit("--v-values must be > 0")


def parse_float_list(text: str) -> tuple[float, ...]:
    try:
        values = tuple(float(part.strip()) for part in text.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated numbers") from exc
    if not values:
        raise argparse.ArgumentTypeError("expected at least one number")
    return values


def build_scenarios(
    T_values: Iterable[float],
    t_values: Iterable[float],
    speed_values: Iterable[float],
) -> list[tuple[float, float, float]]:
    return [(float(T), float(t), float(v)) for T, t, v in product(T_values, t_values, speed_values)]


def solve_one_scenario(
    *,
    distance_matrix: DistanceMatrix,
    network,
    output_dir: Path,
    plans_dir: Path,
    scenario_index: int,
    scenario_id: str,
    T_hour: float,
    t_hour: float,
    speed_km_per_hour: float,
    group_count: int,
    time_limit_seconds: float,
    iterations: int,
    seed: int | None,
) -> dict[str, Any]:
    scenario_started = time.time()
    objective = ObjectiveSpec(
        T_hour=T_hour,
        t_hour=t_hour,
        speed_km_per_hour=speed_km_per_hour,
        time_limit_hour=NO_HARD_TIME_LIMIT_HOUR,
        required_visit_nodes=frozenset(REQUIRED_VISIT_NODES),
        fixed_group_count=group_count,
        mode="lexicographic",
    )
    solver = MTSP_Solver(
        distance_matrix,
        group_count=group_count,
        objective_spec=objective,
        time_limit_seconds=time_limit_seconds,
        iterations=iterations,
        random_seed=seed,
    )
    solution = solver.solve()
    plan_id = f"q4_k{group_count}_{scenario_id}"
    plan = candidate_to_route_plan(
        solution,
        plan_id=plan_id,
        source="q4_fixed_k_min_completion_time",
        parameters={
            "problem": "q4",
            "scenario_id": scenario_id,
            "T_hour": T_hour,
            "t_hour": t_hour,
            "speed_km_per_hour": speed_km_per_hour,
            "time_limit_hour": NO_HARD_TIME_LIMIT_HOUR,
            "group_count": group_count,
            "time_limit_seconds": time_limit_seconds,
            "iterations": iterations,
            "seed": seed,
            "objective": "minimize_completion_time_fixed_group_count",
        },
        distance_matrix=distance_matrix,
        include_expanded_paths=True,
    )
    eval_params = EvaluationParameters(
        T_hour=T_hour,
        t_hour=t_hour,
        speed_km_per_hour=speed_km_per_hour,
        time_limit_hour=NO_HARD_TIME_LIMIT_HOUR,
        required_visit_nodes=frozenset(REQUIRED_VISIT_NODES),
    )
    audit = audit_route_plan(plan, network, eval_params, mode="final")
    evaluation = evaluate_route_plan(plan, network, eval_params)
    plan_path = plans_dir / f"{plan_id}.json"
    write_json(plan_path, dataclass_to_jsonable(plan))
    metrics = evaluation.plan_metrics
    route_times = {
        route_id: route_metrics.total_time_hour
        for route_id, route_metrics in evaluation.route_metrics_by_id.items()
    }
    route_distances = {
        route_id: route_metrics.distance_km
        for route_id, route_metrics in evaluation.route_metrics_by_id.items()
    }
    return {
        "status": "completed",
        "scenario_index": scenario_index,
        "scenario_id": scenario_id,
        "T_hour": T_hour,
        "t_hour": t_hour,
        "speed_km_per_hour": speed_km_per_hour,
        "group_count": group_count,
        "seed": seed,
        "plan_id": plan_id,
        "plan_path": str(plan_path.relative_to(output_dir)),
        "solver_runtime_seconds": solution.runtime_seconds,
        "elapsed_seconds": time.time() - scenario_started,
        "schema_valid": audit.schema_valid,
        "coverage_valid": audit.coverage_valid,
        "route_valid": audit.route_valid,
        "metric_valid": audit.metric_valid,
        "completion_time_hour": None if metrics is None else metrics.completion_time_hour,
        "total_distance_km": None if metrics is None else metrics.total_distance_km,
        "max_route_distance_km": None if metrics is None else metrics.max_route_distance_km,
        "distance_range_km": None if metrics is None else metrics.distance_range_km,
        "time_range_hour": None if metrics is None else metrics.time_range_hour,
        "bottleneck_route_ids": ",".join(evaluation.bottleneck_route_ids),
        "route_times_hour": compact_mapping(route_times),
        "route_distances_km": compact_mapping(route_distances),
        "errors": " | ".join(audit.errors),
        "warnings": " | ".join(audit.warnings),
    }


def failed_record(
    *,
    scenario_index: int,
    scenario_id: str,
    T_hour: float,
    t_hour: float,
    speed_km_per_hour: float,
    group_count: int,
    seed: int | None,
    error: str,
    elapsed_seconds: float,
) -> dict[str, Any]:
    return {
        "status": "failed",
        "scenario_index": scenario_index,
        "scenario_id": scenario_id,
        "T_hour": T_hour,
        "t_hour": t_hour,
        "speed_km_per_hour": speed_km_per_hour,
        "group_count": group_count,
        "seed": seed,
        "plan_id": "",
        "plan_path": "",
        "solver_runtime_seconds": None,
        "elapsed_seconds": elapsed_seconds,
        "schema_valid": False,
        "coverage_valid": False,
        "route_valid": False,
        "metric_valid": False,
        "completion_time_hour": None,
        "total_distance_km": None,
        "max_route_distance_km": None,
        "distance_range_km": None,
        "time_range_hour": None,
        "bottleneck_route_ids": "",
        "route_times_hour": "",
        "route_distances_km": "",
        "errors": error,
        "warnings": "",
    }


def write_outputs(output_dir: Path, metadata: dict[str, Any], records: list[dict[str, Any]]) -> None:
    write_json(output_dir / "batch_results.json", {"metadata": metadata, "records": records})
    write_csv(output_dir / "batch_results.csv", records)
    (output_dir / "summary.md").write_text(build_summary(metadata, records), encoding="utf-8")


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)


def build_summary(metadata: dict[str, Any], records: list[dict[str, Any]]) -> str:
    completed = [record for record in records if record["status"] == "completed" and record["completion_time_hour"] is not None]
    failed_count = len(records) - len(completed)
    lines = [
        "# 第 (4) 问参数网格批量重优化摘要",
        "",
        f"- 固定组数：{metadata['group_count']}",
        f"- 参数组数：{metadata['scenario_count']}",
        f"- 求解预算：每组 {metadata['time_limit_seconds']:g} s，iterations={metadata['iterations']}",
        f"- 完成/失败：{len(completed)} / {failed_count}",
    ]
    if completed:
        best = min(completed, key=lambda record: float(record["completion_time_hour"]))
        worst = max(completed, key=lambda record: float(record["completion_time_hour"]))
        lines.extend(
            [
                f"- 最短完成时间：{float(best['completion_time_hour']):.4g} h（{best['scenario_id']}）",
                f"- 最长完成时间：{float(worst['completion_time_hour']):.4g} h（{worst['scenario_id']}）",
            ]
        )
    lines.extend(
        [
            "",
            "## 输出文件",
            "",
            "- `batch_results.csv`：画热力图的主表。",
            "- `batch_results.json`：完整批量结果。",
            "- `plans/`：每个参数点对应的 RoutePlan JSON。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)


def dataclass_to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return dataclass_to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): dataclass_to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [dataclass_to_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(dataclass_to_jsonable(item) for item in value)
    if isinstance(value, Path):
        return str(value)
    return value


def compact_mapping(values: dict[str, float]) -> str:
    return ";".join(f"{key}={value:.6g}" for key, value in sorted(values.items(), key=lambda item: item[0]))


def scenario_id(T_hour: float, t_hour: float, speed_km_per_hour: float) -> str:
    return f"T{format_token(T_hour)}_t{format_token(t_hour)}_v{format_token(speed_km_per_hour)}"


def format_token(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:g}".replace(".", "p")


if __name__ == "__main__":
    raise SystemExit(main())
