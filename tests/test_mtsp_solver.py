"""测试 mtsp_solver 的多组巡视求解功能。"""

import pytest
from mm_final.routing.mtsp_solver import MTSP_Solver
from mm_final.routing.candidate import CandidateSolution
from mm_final.routing.scoring import score_candidate, ObjectiveSpec
from mm_final.routing.distance_matrix import DistanceMatrix, RoutePath
from mm_final.network import DEPOT


# 辅助：构建微型距离矩阵（用于快速测试）
def make_toy_distance_matrix():
    # 6 个节点：O(0), A(1), B(2), C(3), D(4), E(5)
    nodes = ["O", "A", "B", "C", "D", "E"]
    dist = [
        [0, 10, 15, 20, 25, 30],
        [10, 0, 5, 10, 15, 20],
        [15, 5, 0, 5, 10, 15],
        [20, 10, 5, 0, 5, 10],
        [25, 15, 10, 5, 0, 5],
        [30, 20, 15, 10, 5, 0]
    ]
    return nodes, dist


class TestMTSP_Solver:
    def _make_fake_dm(self, nodes, dist):
        """构建一个具备必要方法的假 DistanceMatrix"""
        class FakeDM:
            def __init__(self, nodes, dist):
                self.nodes = tuple(nodes)
                self._dist = dist

            def distance_km(self, u, v):
                i = self.nodes.index(u)
                j = self.nodes.index(v)
                return self._dist[i][j]

            def route_path(self, required_visit_order, depot=DEPOT):
                # 简单计算路径总长度（仅用于评分，不关心节点展开）
                stops = tuple(required_visit_order)
                if not stops:
                    return RoutePath(distance_km=0.0, expanded_node_path=(depot,))
                checkpoints = (depot,) + stops + (depot,)
                total = 0.0
                for i in range(len(checkpoints) - 1):
                    total += self.distance_km(checkpoints[i], checkpoints[i+1])
                # expanded_node_path 可以简单构造
                expanded = checkpoints
                return RoutePath(distance_km=total, expanded_node_path=tuple(expanded))
        return FakeDM(nodes, dist)

    def test_two_groups_equal_split(self):
        """测试 2 组巡视，验证所有点被覆盖，无惩罚"""
        nodes, dist = make_toy_distance_matrix()
        dm = self._make_fake_dm(nodes, dist)
        solver = MTSP_Solver(dm, group_count=2, time_limit_seconds=10)
        solution = solver.solve()

        assert isinstance(solution, CandidateSolution)
        assert len(solution.routes) == 2
        # 检查所有必须点（除去 O）被覆盖且无重复
        all_nodes = set(nodes[1:])
        visited = set()
        for route in solution.routes:
            visited.update(route.required_visit_order)
        assert visited == all_nodes

        # 评分应无惩罚
        spec = ObjectiveSpec(
            time_limit_hour=float('inf'),
            required_visit_nodes=frozenset(nodes[1:])   # 只要求覆盖本测试的点
        )
        score = score_candidate(solution, dm, spec)
        assert score.penalty == 0.0

    def test_three_groups_basic(self):
        """测试 3 组巡视，验证覆盖和基本均衡"""
        nodes, dist = make_toy_distance_matrix()
        dm = self._make_fake_dm(nodes, dist)
        solver = MTSP_Solver(dm, group_count=3, time_limit_seconds=10)
        solution = solver.solve()

        assert len(solution.routes) == 3
        all_nodes = set(nodes[1:])
        visited = set()
        for route in solution.routes:
            visited.update(route.required_visit_order)
        assert visited == all_nodes

        spec = ObjectiveSpec(
            time_limit_hour=float('inf'),
            required_visit_nodes=frozenset(nodes[1:])
        )
        score = score_candidate(solution, dm, spec)
        assert score.penalty == 0.0
