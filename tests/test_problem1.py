"""问题 (1) 集成测试：分 3 组巡视，总路程最短且尽量均衡。"""

import pytest
from mm_final.routing.mtsp_solver import MTSP_Solver
from mm_final.routing.distance_matrix import DistanceMatrix
from mm_final.routing.export import candidate_to_route_plan
from mm_final.routing.scoring import score_candidate, ObjectiveSpec
from mm_final.network import load_road_network, REQUIRED_VISIT_NODES, DEPOT


@pytest.fixture(scope="module")
def distance_matrix():
    result = load_road_network()
    network = result.network
    return DistanceMatrix.from_network(network)


class TestProblem1:
    def test_three_group_balanced(self, distance_matrix):
        spec = ObjectiveSpec(
            time_limit_hour=float('inf'),
            mode="weighted",
            weights={
                "total_distance_km": 1.0,
                "max_route_distance_km": 0.5,
                "distance_range_km": 0.5
            },
            required_visit_nodes=frozenset(REQUIRED_VISIT_NODES)
        )

        solver = MTSP_Solver(
            distance_matrix,
            group_count=3,
            objective_spec=spec,
            time_limit_seconds=600,
            iterations=50
        )
        solution = solver.solve()

        assert len(solution.routes) == 3
        visited = set()
        for route in solution.routes:
            visited.update(route.required_visit_order)
        assert visited == set(REQUIRED_VISIT_NODES)

        score = score_candidate(solution, distance_matrix, spec)
        assert score.penalty == 0.0

        print(f"\n=== 问题 (1) 结果 ===")
        for i, route in enumerate(solution.routes, 1):
            route_dist = distance_matrix.route_path(route.required_visit_order, depot=DEPOT).distance_km
            print(f"路线 {i}: 点数 {len(route.required_visit_order)}, 里程 {route_dist:.2f} km")
        print(f"总里程: {score.total_distance_km:.2f} km")
        print(f"最长路线里程: {score.max_route_distance_km:.2f} km")
        print(f"里程极差: {score.distance_range_km:.2f} km")
        print(f"求解耗时: {solution.runtime_seconds:.2f} s")

        plan = candidate_to_route_plan(
            solution,
            plan_id="problem1-three-groups",
            distance_matrix=distance_matrix,
            include_expanded_paths=True
        )
        assert len(plan.routes) == 3
