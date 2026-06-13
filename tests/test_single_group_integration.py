"""集成测试：使用官方路网运行分支定界求解单组最优巡视路线。"""

import pytest
from mm_final.routing.bb_solver import BranchAndBoundTspSolver
from mm_final.routing.distance_matrix import DistanceMatrix
from mm_final.routing.export import candidate_to_route_plan
from mm_final.routing.scoring import score_candidate, ObjectiveSpec
from mm_final.network import load_road_network, REQUIRED_VISIT_NODES, DEPOT


@pytest.fixture(scope="module")
def distance_matrix():
    result = load_road_network()
    network = result.network
    return DistanceMatrix.from_network(network)


class TestSingleGroupIntegration:

    def test_solve_single_group_official_network(self, distance_matrix):
        solver = BranchAndBoundTspSolver.from_distance_matrix(distance_matrix)
        solution = solver.solve()

        assert len(solution.routes) == 1
        route = solution.routes[0]
        visited = set(route.required_visit_order)
        expected = set(REQUIRED_VISIT_NODES)
        assert visited == expected
        assert len(route.required_visit_order) == len(expected)

        spec = ObjectiveSpec(time_limit_hour=float('inf'))
        score = score_candidate(solution, distance_matrix, spec)
        assert score.penalty == 0.0
        assert score.total_distance_km > 0

        plan = candidate_to_route_plan(
            solution,
            plan_id="integration-test-single",
            distance_matrix=distance_matrix,
            include_expanded_paths=True
        )
        assert plan.routes[0].distance_km == score.total_distance_km

        print(f"\n单组最优巡视总里程: {score.total_distance_km:.2f} km")
        print(f"求解耗时: {solution.runtime_seconds:.2f} s")
        print(f"巡视点数量: {len(route.required_visit_order)}")

    def test_solution_reproducibility(self, distance_matrix):
        solver1 = BranchAndBoundTspSolver.from_distance_matrix(distance_matrix)
        solver2 = BranchAndBoundTspSolver.from_distance_matrix(distance_matrix)
        sol1 = solver1.solve()
        sol2 = solver2.solve()
        spec = ObjectiveSpec()
        score1 = score_candidate(sol1, distance_matrix, spec)
        score2 = score_candidate(sol2, distance_matrix, spec)
        assert abs(score1.total_distance_km - score2.total_distance_km) < 1e-6
