"""导出所有问题的最终方案为 RoutePlan JSON 文件，并打印各问题求解时间"""
import sys
import json
from pathlib import Path
from dataclasses import asdict

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mm_final.network import load_road_network, REQUIRED_VISIT_NODES
from mm_final.routing.distance_matrix import DistanceMatrix
from mm_final.routing.export import candidate_to_route_plan
from mm_final.routing.bb_solver import BranchAndBoundTspSolver
from mm_final.routing.mtsp_solver import MTSP_Solver
from mm_final.routing.scoring import ObjectiveSpec
from mm_final.routing.min_groups import MinGroupsSolver
from mm_final.routing.minmax_vrp import MinMaxVRP_Solver


def convert_for_json(obj):
    """递归转换 dataclass 或其他非 JSON 类型为可序列化对象"""
    if isinstance(obj, dict):
        return {k: convert_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_for_json(v) for v in obj]
    elif isinstance(obj, frozenset):
        return sorted(list(obj))
    elif isinstance(obj, set):
        return sorted(list(obj))
    elif hasattr(obj, '__dataclass_fields__'):
        return convert_for_json(asdict(obj))
    else:
        return obj


def write_plan(plan, filename, out_dir):
    data = convert_for_json(asdict(plan))
    with open(out_dir / filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    network_result = load_road_network()
    network = network_result.network
    dm = DistanceMatrix.from_network(network)

    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)

    # --- 问题 (0) 单组最优 ---
    print("求解问题 (0)...")
    solver0 = BranchAndBoundTspSolver.from_distance_matrix(dm)
    sol0 = solver0.solve()
    print(f"  耗时: {sol0.runtime_seconds:.2f} s")
    plan0 = candidate_to_route_plan(
        sol0,
        plan_id="single-optimal",
        source="branch_and_bound",
        parameters={"T_hour": 2.0, "t_hour": 1.0, "speed_km_per_hour": 35.0},
        distance_matrix=dm,
        include_expanded_paths=True
    )
    write_plan(plan0, "single_optimal.json", out_dir)
    print("  单组最优已导出。")

    # --- 问题 (1) 3组均衡 ---
    print("求解问题 (1)...")
    spec1 = ObjectiveSpec(
        time_limit_hour=float('inf'),
        mode="weighted",
        weights={"total_distance_km": 1.0, "max_route_distance_km": 0.5, "distance_range_km": 0.5},
        required_visit_nodes=frozenset(REQUIRED_VISIT_NODES)
    )
    solver1 = MTSP_Solver(dm, group_count=3, objective_spec=spec1, time_limit_seconds=600, iterations=50)
    sol1 = solver1.solve()
    print(f"  耗时: {sol1.runtime_seconds:.2f} s")
    plan1 = candidate_to_route_plan(
        sol1,
        plan_id="problem1-3groups",
        source="mtsp_local_search",
        parameters={"T_hour": 2.0, "t_hour": 1.0, "speed_km_per_hour": 35.0},
        distance_matrix=dm,
        include_expanded_paths=True
    )
    write_plan(plan1, "problem1_3groups.json", out_dir)
    print("  3组均衡已导出。")

    # --- 问题 (2) 最少分组数 ---
    print("求解问题 (2)...")
    solver2 = MinGroupsSolver(dm, T_hour=2.0, t_hour=1.0, speed_km_per_hour=35.0,
                              time_limit_hour=24.0, max_group_upper=8, time_limit_seconds=600)
    sol2 = solver2.solve()
    print(f"  耗时: {sol2.runtime_seconds:.2f} s")
    plan2 = candidate_to_route_plan(
        sol2,
        plan_id="problem2-min-groups",
        source="min_groups_search",
        parameters={"T_hour": 2.0, "t_hour": 1.0, "speed_km_per_hour": 35.0, "time_limit_hour": 24.0},
        distance_matrix=dm,
        include_expanded_paths=True
    )
    write_plan(plan2, "problem2_min_groups.json", out_dir)
    print("  最少分组已导出。")

    # --- 问题 (3) 最短完成时间 ---
    print("求解问题 (3)...")
    solver3 = MinMaxVRP_Solver(dm, T_hour=2.0, t_hour=1.0, speed_km_per_hour=35.0,
                               time_limit_seconds=600, max_group_upper=8)
    sol3 = solver3.solve()
    print(f"  耗时: {sol3.runtime_seconds:.2f} s")
    plan3 = candidate_to_route_plan(
        sol3,
        plan_id="problem3-minmax-time",
        source="minmax_vrp_search",
        parameters={"T_hour": 2.0, "t_hour": 1.0, "speed_km_per_hour": 35.0},
        distance_matrix=dm,
        include_expanded_paths=True
    )
    write_plan(plan3, "problem3_minmax_time.json", out_dir)
    print("  最短时间已导出。")

    print("\n所有方案已导出到 outputs/ 目录")
