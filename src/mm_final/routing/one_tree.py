"""1-树下界计算与次梯度优化，用于分支定界法求解 TSP。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

import networkx as nx


@dataclass(frozen=True)
class OneTreeResult:
    lower_bound: float
    one_tree_weight: float
    pi_sum: float
    node_degrees: List[int]
    is_tour: bool
    edges: Set[Tuple[int, int]] = field(default_factory=set)


class OneTreeComputer:
    def __init__(self, distances: List[List[float]], nodes: List[str]) -> None:
        """
        distances: n×n 对称距离矩阵，distances[i][j] 为节点 i 到 j 的原始距离。
        nodes: 节点名称列表，nodes[0] 必须是 depot（巡视起点/终点）。
        """
        self.nodes = nodes
        self.n = len(nodes)
        self.original_dist = distances

    def compute(
        self,
        pi: List[float],
        force_edges: Optional[Set[Tuple[int, int]]] = None,
        forbidden_edges: Optional[Set[Tuple[int, int]]] = None,
    ) -> OneTreeResult:
        if force_edges is None:
            force_edges = set()
        if forbidden_edges is None:
            forbidden_edges = set()

        n = self.n
        c_prime = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                c_prime[i][j] = self.original_dist[i][j] + pi[i] + pi[j]

        INF = float('inf')
        for u, v in forbidden_edges:
            c_prime[u][v] = INF
            c_prime[v][u] = INF

        graph = nx.Graph()
        for i in range(1, n):
            for j in range(i + 1, n):
                weight = c_prime[i][j]
                if weight < INF:
                    graph.add_edge(i, j, weight=weight)

        original_weights = {}
        for u, v in force_edges:
            if u != 0 and v != 0:
                key = (u, v) if u < v else (v, u)
                if graph.has_edge(*key):
                    original_weights[key] = graph[key[0]][key[1]]['weight']
                else:
                    graph.add_edge(key[0], key[1], weight=INF)
                    original_weights[key] = INF
                graph[key[0]][key[1]]['weight'] = -1e18

        mst = nx.minimum_spanning_tree(graph, weight='weight')

        for u, v in force_edges:
            if u != 0 and v != 0:
                key = (u, v) if u < v else (v, u)
                if mst.has_edge(*key):
                    mst[key[0]][key[1]]['weight'] = original_weights[key]

        mst_weight = 0.0
        for u, v, data in mst.edges(data=True):
            mst_weight += data['weight']

        depot_edges = []
        for v in range(1, n):
            w = c_prime[0][v]
            if w < INF and (0, v) not in forbidden_edges and (v, 0) not in forbidden_edges:
                depot_edges.append((w, v))
        depot_edges.sort(key=lambda x: x[0])

        forced_depot_neighbors = set()
        for u, v in force_edges:
            if u == 0:
                forced_depot_neighbors.add(v)
            elif v == 0:
                forced_depot_neighbors.add(u)

        selected_depot_edges = []
        total_depot_weight = 0.0

        for w, v in depot_edges:
            if v in forced_depot_neighbors:
                selected_depot_edges.append((w, v))
                total_depot_weight += w
                forced_depot_neighbors.discard(v)

        remaining = [e for e in depot_edges if e[1] not in [v for _, v in selected_depot_edges]]
        remaining.sort(key=lambda x: x[0])
        for w, v in remaining:
            if len(selected_depot_edges) >= 2:
                break
            selected_depot_edges.append((w, v))
            total_depot_weight += w

        one_tree_weight = mst_weight + total_depot_weight

        degree = [0] * n
        for u, v in mst.edges():
            degree[u] += 1
            degree[v] += 1
        for _, v in selected_depot_edges:
            degree[0] += 1
            degree[v] += 1

        edges: Set[Tuple[int, int]] = set()
        for u, v in mst.edges():
            edges.add((u, v))
        for _, v in selected_depot_edges:
            edges.add((0, v))

        pi_sum = sum(pi)
        lower_bound = one_tree_weight - 2.0 * pi_sum

        if all(d == 2 for d in degree):
            visited = set()
            stack = [0]
            while stack:
                u = stack.pop()
                if u in visited:
                    continue
                visited.add(u)
                for (a, b) in edges:
                    if a == u and b not in visited:
                        stack.append(b)
                    elif b == u and a not in visited:
                        stack.append(a)
            is_tour = (len(visited) == self.n)
        else:
            is_tour = False

        return OneTreeResult(
            lower_bound=lower_bound,
            one_tree_weight=one_tree_weight,
            pi_sum=pi_sum,
            node_degrees=degree,
            is_tour=is_tour,
            edges=edges,
        )


class SubgradientOptimizer:
    """次梯度优化器，最大化 1-树下界。"""

    def __init__(
        self,
        computer: OneTreeComputer,
        max_iterations: int = 1000,
        alpha: float = 1.0,
        halve_after: int = 50,
        min_alpha: float = 1e-6,
    ) -> None:
        self.computer = computer
        self.max_iter = max_iterations
        self.alpha = alpha
        self.halve_after = halve_after
        self.min_alpha = min_alpha

    def optimize(
        self,
        ub: float,
        force_edges: Optional[Set[Tuple[int, int]]] = None,
        forbidden_edges: Optional[Set[Tuple[int, int]]] = None,
        initial_pi: Optional[List[float]] = None,
    ) -> Tuple[float, OneTreeResult, List[float]]:
        """
        返回 (best_lb, best_result, best_pi)
        ub: 当前已知的最优回路长度（上界），用于步长计算。
        """
        n = self.computer.n
        if initial_pi is not None:
            pi = list(initial_pi)
        else:
            pi = [0.0] * n

        best_lb = -float('inf')
        best_result: Optional[OneTreeResult] = None
        best_pi = pi.copy()
        alpha = self.alpha
        no_improve = 0

        for _ in range(self.max_iter):
            result = self.computer.compute(pi, force_edges, forbidden_edges)
            lb = result.lower_bound

            if lb > best_lb + 1e-12:
                best_lb = lb
                best_result = result
                best_pi = pi.copy()
                no_improve = 0
            else:
                no_improve += 1

            if result.is_tour and abs(lb - ub) < 1e-6:
                break

            g = [d - 2 for d in result.node_degrees]
            sum_g2 = sum(x * x for x in g)
            if sum_g2 < 1e-12:
                break

            t = alpha * (ub - lb) / sum_g2

            for i in range(n):
                pi[i] += t * g[i]

            if no_improve >= self.halve_after:
                alpha /= 2.0
                no_improve = 0
                if alpha < self.min_alpha:
                    break

        if best_result is None:
            result = self.computer.compute(pi, force_edges, forbidden_edges)
            best_lb = result.lower_bound
            best_result = result
            best_pi = pi

        return best_lb, best_result, best_pi
