"""问题 (3) 集成测试：人员足够多，最短完成时间"""

import pytest
from mm_final.routing.minmax_vrp import MinMaxVRP_Solver
from mm_final.routing.distance_matrix import DistanceMatrix
from mm_final.routing.scoring import score_candidate, ObjectiveSpec
from mm_final.network import load_road_network, REQUIRED_VISIT_NODES, DEPOT


@pytest.fixture(scope="module")
def distance_matrix():
    result = load_road_network()
    network = result.network
    return DistanceMatrix.from_network(network)


class TestProblem3:
    def test_unlimited_personnel_time(self, distance_matrix):
        solver = MinMaxVRP_Solver(
            distance_matrix,
            T_hour=2.0,
            t_hour=1.0,
            speed_km_per_hour=35.0,
            time_limit_seconds=600,
            max_group_upper=8
        )
        solution = solver.solve()

        assert solution is not None
        visited = set()
        for route in solution.routes:
            visited.update(route.required_visit_order)
        assert visited == set(REQUIRED_VISIT_NODES)

        spec = ObjectiveSpec(
            T_hour=2.0,
            t_hour=1.0,
            speed_km_per_hour=35.0,
            time_limit_hour=float('inf'),
        )
        score = score_candidate(solution, distance_matrix, spec)
        assert score.penalty == 0.0

        print(f"\n=== 问题 (3) 结果 ===")
        print(f"使用组数: {len(solution.routes)}")
        for i, route in enumerate(solution.routes, 1):
            route_time = (distance_matrix.route_path(route.required_visit_order, depot=DEPOT).distance_km / 35.0
                          + sum(2.0 if node in "ABCDEFGHIJKLMNOPQR" else 1.0 for node in route.required_visit_order))
            print(f"路线 {i}: 点数 {len(route.required_visit_order)}, 时间 {route_time:.2f} h")
        print(f"最晚完工时间: {score.max_route_time_hour:.2f} h")
