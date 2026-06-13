"""基于 1-树下界的分支定界 TSP 精确求解器。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from heapq import heappop, heappush
from typing import List, Optional, Set, Tuple

from mm_final.routing.candidate import CandidateRoute, CandidateSolution
from mm_final.routing.distance_matrix import DistanceMatrix
from mm_final.routing.one_tree import OneTreeComputer, OneTreeResult, SubgradientOptimizer


@dataclass(order=False)
class BBNode:
    """分支定界树中的一个搜索节点"""
    force_edges: Set[Tuple[int, int]]
    forbidden_edges: Set[Tuple[int, int]]
    lb: float
    pi: List[float]
    one_tree: OneTreeResult

    def __lt__(self, other: 'BBNode') -> bool:
        return self.lb < other.lb


class BranchAndBoundTspSolver:
    """精确求解对称 TSP，返回最优 CandidateSolution（单条路线）"""

    def __init__(self, distances: List[List[float]], nodes: List[str],
                 max_iterations: int = 200,
                 time_limit_seconds: float = 300.0):
        self.distances = distances
        self.nodes = nodes
        self.n = len(nodes)
        self.computer = OneTreeComputer(distances, nodes)
        self.optimizer = SubgradientOptimizer(self.computer, max_iterations=max_iterations)
        self.time_limit = time_limit_seconds

    @classmethod
    def from_distance_matrix(cls, dm: 'DistanceMatrix') -> 'BranchAndBoundTspSolver':
        nodes = list(dm.nodes)
        dist = [[dm.distance_km(u, v) for v in nodes] for u in nodes]
        return cls(dist, nodes)

    def solve(self) -> CandidateSolution:
        start_time = time.time()
        n = self.n

        tour, ub = self._greedy_tour()
        best_tour = tour
        best_ub = ub

        optimizer = SubgradientOptimizer(self.computer, max_iterations=200)
        root_lb, root_result, root_pi = optimizer.optimize(ub=float('inf'))

        if root_result.is_tour and root_result.lower_bound < best_ub:
            pass

        counter = 0
        queue = []
        root_node = BBNode(
            force_edges=set(),
            forbidden_edges=set(),
            lb=root_lb,
            pi=root_pi,
            one_tree=root_result
        )
        heappush(queue, (root_lb, counter, root_node))
        counter += 1

        while queue:
            if time.time() - start_time > self.time_limit:
                break

            lb, _, node = heappop(queue)
            if lb >= best_ub:
                continue

            if node.one_tree.is_tour:
                tour = self._extract_tour_from_one_tree(node.one_tree, node.force_edges)
                tour_length = self._calculate_tour_length(tour)
                if tour_length < best_ub:
                    best_ub = tour_length
                    best_tour = tour
                continue

            e = self._choose_branch_edge(node)
            if e is None:
                continue

            u, v = e
            child_force = node.force_edges | {(u, v)}
            if self._depot_degree_ok(child_force):
                child_lb, child_res, child_pi = optimizer.optimize(
                    ub=best_ub,
                    force_edges=child_force,
                    forbidden_edges=node.forbidden_edges,
                    initial_pi=node.pi
                )
                if child_lb < best_ub:
                    child_node = BBNode(
                        force_edges=child_force,
                        forbidden_edges=node.forbidden_edges,
                        lb=child_lb,
                        pi=child_pi,
                        one_tree=child_res
                    )
                    heappush(queue, (child_lb, counter, child_node))
                    counter += 1

            child_forbidden = node.forbidden_edges | {(u, v)}
            child_lb, child_res, child_pi = optimizer.optimize(
                ub=best_ub,
                force_edges=node.force_edges,
                forbidden_edges=child_forbidden,
                initial_pi=node.pi
            )
            if child_lb < best_ub:
                child_node = BBNode(
                    force_edges=node.force_edges,
                    forbidden_edges=child_forbidden,
                    lb=child_lb,
                    pi=child_pi,
                    one_tree=child_res
                )
                heappush(queue, (child_lb, counter, child_node))
                counter += 1

        runtime = time.time() - start_time
        visit_indices = best_tour[1:-1]
        visit_names = tuple(self.nodes[i] for i in visit_indices)
        route = CandidateRoute(route_id="R1", required_visit_order=visit_names)
        solution = CandidateSolution(
            routes=(route,),
            method="branch_and_bound",
            parameters={"upper_bound": best_ub, "time_limit": self.time_limit},
            runtime_seconds=runtime
        )
        return solution

    def _greedy_tour(self) -> Tuple[List[int], float]:
        unvisited = set(range(1, self.n))
        current = 0
        tour = [0]
        while unvisited:
            next_node = min(unvisited, key=lambda v: self.distances[current][v])
            tour.append(next_node)
            unvisited.remove(next_node)
            current = next_node
        tour.append(0)
        length = sum(self.distances[tour[i]][tour[i+1]] for i in range(len(tour)-1))
        return tour, length

    def _choose_branch_edge(self, node: BBNode) -> Optional[Tuple[int, int]]:
        if not hasattr(node.one_tree, 'edges'):
            deg = node.one_tree.node_degrees
            for i in range(self.n):
                if deg[i] > 2:
                    for j in range(self.n):
                        if i != j and (i, j) not in node.force_edges and (j, i) not in node.force_edges \
                                and (i, j) not in node.forbidden_edges and (j, i) not in node.forbidden_edges:
                            return (i, j)
            return None

        for (u, v) in node.one_tree.edges:
            if (u, v) not in node.force_edges and (v, u) not in node.force_edges \
                    and (u, v) not in node.forbidden_edges and (v, u) not in node.forbidden_edges:
                deg_u = node.one_tree.node_degrees[u]
                deg_v = node.one_tree.node_degrees[v]
                if deg_u > 2 or deg_v > 2:
                    return (u, v)
        for (u, v) in node.one_tree.edges:
            if (u, v) not in node.force_edges and (v, u) not in node.force_edges \
                    and (u, v) not in node.forbidden_edges and (v, u) not in node.forbidden_edges:
                return (u, v)
        return None

    def _depot_degree_ok(self, force_edges: Set[Tuple[int, int]]) -> bool:
        depot_edges_count = sum(1 for (u, v) in force_edges if u == 0 or v == 0)
        return depot_edges_count <= 2

    def _extract_tour_from_one_tree(self, result: OneTreeResult, force_edges: Set[Tuple[int, int]]) -> List[int]:
        if not hasattr(result, 'edges'):
            tour, _ = self._greedy_tour()
            return tour
        adj = {i: [] for i in range(self.n)}
        for u, v in result.edges:
            adj[u].append(v)
            adj[v].append(u)
        visited = set()
        tour = []

        def dfs(u):
            visited.add(u)
            tour.append(u)
            for v in adj[u]:
                if v not in visited:
                    dfs(v)
        dfs(0)
        tour.append(0)
        return tour

    def _calculate_tour_length(self, tour: List[int]) -> float:
        return sum(self.distances[tour[i]][tour[i+1]] for i in range(len(tour)-1))
