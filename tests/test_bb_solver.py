"""测试分支定界 TSP 求解器。"""

import pytest
from mm_final.routing.bb_solver import BranchAndBoundTspSolver
from mm_final.routing.candidate import CandidateSolution


def make_tsp_solver(nodes, dist):
    return BranchAndBoundTspSolver(dist, nodes)


class TestBranchAndBoundTsp:

    def test_three_node_triangle_optimal(self):
        nodes = ["O", "A", "B"]
        dist = [
            [0, 10, 20],
            [10, 0, 10],
            [20, 10, 0]
        ]
        solver = make_tsp_solver(nodes, dist)
        solution = solver.solve()

        assert isinstance(solution, CandidateSolution)
        assert len(solution.routes) == 1
        route = solution.routes[0]
        assert route.required_visit_order == ("A", "B")
        assert solution.method == "branch_and_bound"

    def test_four_node_square_optimal(self):
        nodes = ["O", "A", "B", "C"]
        dist = [
            [0, 10, 15, 20],
            [10, 0, 5, 15],
            [15, 5, 0, 10],
            [20, 15, 10, 0]
        ]
        solver = make_tsp_solver(nodes, dist)
        solution = solver.solve()

        assert len(solution.routes) == 1
        route = solution.routes[0]
        visited = set(route.required_visit_order)
        assert visited == {"A", "B", "C"}
        assert len(route.required_visit_order) == 3

    def test_solution_can_be_exported_to_route_plan(self):
        nodes = ["O", "A", "B"]
        dist = [
            [0, 10, 20],
            [10, 0, 10],
            [20, 10, 0]
        ]
        solver = make_tsp_solver(nodes, dist)
        solution = solver.solve()
        assert solution.method == "branch_and_bound"
        assert solution.seed is None
        assert isinstance(solution.runtime_seconds, float)
        assert solution.runtime_seconds >= 0

    def test_with_edge_constraints_respected(self):
        nodes = ["O", "A", "B", "C"]
        dist = [
            [0, 100, 10, 200],
            [100, 0, 10, 100],
            [10, 10, 0, 10],
            [200, 100, 10, 0]
        ]
        solver = make_tsp_solver(nodes, dist)
        solution = solver.solve()
        assert len(solution.routes) == 1
        assert len(solution.routes[0].required_visit_order) == 3
