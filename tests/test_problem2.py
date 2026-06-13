"""问题 (2) 集成测试：24h 内完成巡视的最少分组数"""

import pytest
from mm_final.routing.min_groups import MinGroupsSolver
from mm_final.routing.distance_matrix import DistanceMatrix
from mm_final.routing.scoring import score_candidate, ObjectiveSpec
from mm_final.network import load_road_network, REQUIRED_VISIT_NODES, DEPOT


@pytest.fixture(scope="module")
def distance_matrix():
    result = load_road_network()
    network = result.network
    return DistanceMatrix.from_network(network)


class TestProblem2:
    def test_minimum_group_count(self, distance_matrix):
        solver = MinGroupsSolver(
            distance_matrix,
            T_hour=2.0,
            t_hour=1.0,
            speed_km_per_hour=35.0,
            time_limit_hour=24.0,
            max_group_upper=8,
            time_limit_seconds=600,
        )
        solution = solver.solve()

        assert solution is not None, "未找到可行分组"
        visited = set()
        for route in solution.routes:
            visited.update(route.required_visit_order)
        assert visited == set(REQUIRED_VISIT_NODES)

        spec = ObjectiveSpec(
            T_hour=2.0,
            t_hour=1.0,
            speed_km_per_hour=35.0,
            time_limit_hour=24.0,
            time_limit_penalty_weight=1000.0,
        )
        score = score_candidate(solution, distance_matrix, spec)
        assert score.penalty == 0.0, f"存在超时路线，最大时间={score.max_route_time_hour:.2f}h"
        for i, route in enumerate(solution.routes, 1):
            route_dist = distance_matrix.route_path(route.required_visit_order, depot=DEPOT).distance_km
            stop_time = sum(2.0 if node in "ABCDEFGHIJKLMNOPQR" else 1.0 for node in route.required_visit_order)
            route_time = route_dist / 35.0 + stop_time
            assert route_time <= 24.0 + 1e-6, f"路线 {i} 超时: {route_time:.2f}h"

        print("\n=== 问题 (2) 结果 ===")
        print(f"最少分组数: {len(solution.routes)}")
        for i, route in enumerate(solution.routes, 1):
            route_dist = distance_matrix.route_path(route.required_visit_order, depot=DEPOT).distance_km
            stop_time = sum(2.0 if node in "ABCDEFGHIJKLMNOPQR" else 1.0 for node in route.required_visit_order)
            route_time = route_dist / 35.0 + stop_time
            print(f"路线 {i}: 点数 {len(route.required_visit_order)}, 里程 {route_dist:.2f} km, 时间 {route_time:.2f} h")
        print(f"总里程: {score.total_distance_km:.2f} km")
