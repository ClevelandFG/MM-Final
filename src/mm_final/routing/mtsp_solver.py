"""固定分组数的多旅行商问题求解器（启发式局部搜索 + 精确 TSP 子程序）"""

from __future__ import annotations

import time
import random
from typing import List, Optional, Tuple

from mm_final.routing.candidate import CandidateRoute, CandidateSolution
from mm_final.routing.bb_solver import BranchAndBoundTspSolver
from mm_final.routing.distance_matrix import DistanceMatrix
from mm_final.routing.scoring import score_candidate, ObjectiveSpec, Score
from mm_final.routing.pool import SolutionPool


class MTSP_Solver:
    def __init__(
        self,
        distance_matrix: DistanceMatrix,
        group_count: int,
        objective_spec: Optional[ObjectiveSpec] = None,
        time_limit_seconds: float = 300.0,
        iterations: int = 100,
        random_seed: Optional[int] = None
    ):
        self.dm = distance_matrix
        self.nodes = list(distance_matrix.nodes)
        self.depot = self.nodes[0]
        self.must_visit = self.nodes[1:]
        self.k = group_count
        self.time_limit = time_limit_seconds
        self.max_iter = iterations
        self.random = random.Random(random_seed)
        self.spec = ObjectiveSpec(time_limit_hour=float('inf'))
        self._tsp_cache: dict[tuple, tuple[str, ...]] = {}
        if objective_spec is None:
            self.spec = ObjectiveSpec(
                time_limit_hour=float('inf'),
                mode="weighted",
                weights={
                    "total_distance_km": 1.0,
                    "max_route_distance_km": 0.5,
                    "distance_range_km": 0.5
                }
            )
        else:
            self.spec = objective_spec

    def solve(self) -> CandidateSolution:
        start_time = time.time()
        groups = self._initial_clustering()
        solution = self._build_solution(groups)
        current_score = score_candidate(solution, self.dm, self.spec)
        best_solution = solution
        best_score = current_score

        pool = SolutionPool(max_size=5)
        pool.add(solution, current_score)

        no_improve = 0
        iteration = 0
        while iteration < self.max_iter and time.time() - start_time < self.time_limit:
            if self.random.random() < 0.7:
                new_sol = self._try_relocate(solution, current_score)
            else:
                new_sol = self._try_swap(solution, current_score)

            if new_sol is not None:
                solution = new_sol
                current_score = score_candidate(solution, self.dm, self.spec)
                if current_score.sort_key < best_score.sort_key:
                    best_solution = solution
                    best_score = current_score
                pool.add(solution, current_score)
                no_improve = 0
            else:
                no_improve += 1

            if no_improve >= 10 and len(pool.items) > 1:
                candidate = self.random.choice(pool.items)
                solution = CandidateSolution(
                    routes=candidate.solution.routes,
                    method=candidate.solution.method,
                    parameters=candidate.solution.parameters,
                    seed=candidate.solution.seed,
                    runtime_seconds=candidate.solution.runtime_seconds
                )
                current_score = candidate.score
                no_improve = 0
            iteration += 1

        final_sol = CandidateSolution(
            routes=best_solution.routes,
            method="mtsp_local_search",
            parameters={"group_count": self.k, "iterations": iteration},
            runtime_seconds=time.time() - start_time
        )
        return final_sol

    def _initial_clustering(self) -> List[List[str]]:
        sorted_nodes = sorted(self.must_visit, key=lambda v: self.dm.distance_km(self.depot, v), reverse=True)
        groups = [[] for _ in range(self.k)]
        for i, node in enumerate(sorted_nodes):
            groups[i % self.k].append(node)
        for g in groups:
            self.random.shuffle(g)
        return groups

    def _build_solution(self, groups: List[List[str]]) -> CandidateSolution:
        routes = []
        for idx, group in enumerate(groups, start=1):
            visit_order = self._solve_tsp_for_group(group) if group else ()
            routes.append(CandidateRoute(route_id=f"R{idx}", required_visit_order=visit_order))
        return CandidateSolution(routes=tuple(routes), method="mtsp_init")

    def _solve_tsp_for_group(self, group: List[str]) -> tuple[str, ...]:
        key = tuple(sorted(group))
        if key in self._tsp_cache:
            return self._tsp_cache[key]
        nodes_sub = [self.depot] + group
        n = len(nodes_sub)
        dist_sub = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                dist_sub[i][j] = self.dm.distance_km(nodes_sub[i], nodes_sub[j])
        solver = BranchAndBoundTspSolver(dist_sub, nodes_sub, time_limit_seconds=30)
        sol = solver.solve()
        visit_order = sol.routes[0].required_visit_order
        self._tsp_cache[key] = visit_order
        return visit_order

    def _try_relocate(self, solution: CandidateSolution, current_score: Score) -> Optional[CandidateSolution]:
        routes = list(solution.routes)
        k = len(routes)
        from_idx = self.random.randrange(k)
        if len(routes[from_idx].required_visit_order) == 0:
            return None
        to_idx = self.random.randrange(k)
        while to_idx == from_idx:
            to_idx = self.random.randrange(k)

        node_idx = self.random.randrange(len(routes[from_idx].required_visit_order))
        insert_pos = self.random.randint(0, len(routes[to_idx].required_visit_order))

        from_route = routes[from_idx]
        to_route = routes[to_idx]

        from_nodes = list(from_route.required_visit_order)
        to_nodes = list(to_route.required_visit_order)
        node = from_nodes.pop(node_idx)
        if from_idx == to_idx and insert_pos > node_idx:
            insert_pos -= 1
        to_nodes.insert(insert_pos, node)

        new_from_order = self._solve_tsp_for_group(from_nodes) if from_nodes else ()
        new_to_order = self._solve_tsp_for_group(to_nodes) if to_nodes else ()

        new_routes = list(solution.routes)
        new_routes[from_idx] = CandidateRoute(route_id=from_route.route_id, required_visit_order=new_from_order)
        new_routes[to_idx] = CandidateRoute(route_id=to_route.route_id, required_visit_order=new_to_order)

        new_sol = CandidateSolution(
            routes=tuple(new_routes),
            method="mtsp_relocate",
            parameters=solution.parameters,
            runtime_seconds=0.0
        )
        new_score = score_candidate(new_sol, self.dm, self.spec)
        if new_score.sort_key < current_score.sort_key:
            return new_sol
        return None

    def _try_swap(self, solution: CandidateSolution, current_score: Score) -> Optional[CandidateSolution]:
        routes = list(solution.routes)
        k = len(routes)
        idx1 = self.random.randrange(k)
        idx2 = self.random.randrange(k)
        while idx2 == idx1:
            idx2 = self.random.randrange(k)
        route1 = routes[idx1]
        route2 = routes[idx2]
        if len(route1.required_visit_order) == 0 or len(route2.required_visit_order) == 0:
            return None

        n1 = len(route1.required_visit_order)
        n2 = len(route2.required_visit_order)
        pos1 = self.random.randrange(n1)
        pos2 = self.random.randrange(n2)

        nodes1 = list(route1.required_visit_order)
        nodes2 = list(route2.required_visit_order)
        nodes1[pos1], nodes2[pos2] = nodes2[pos2], nodes1[pos1]

        new_order1 = self._solve_tsp_for_group(nodes1) if nodes1 else ()
        new_order2 = self._solve_tsp_for_group(nodes2) if nodes2 else ()

        new_routes = list(solution.routes)
        new_routes[idx1] = CandidateRoute(route_id=route1.route_id, required_visit_order=new_order1)
        new_routes[idx2] = CandidateRoute(route_id=route2.route_id, required_visit_order=new_order2)

        new_sol = CandidateSolution(
            routes=tuple(new_routes),
            method="mtsp_swap",
            parameters=solution.parameters,
            runtime_seconds=0.0
        )
        new_score = score_candidate(new_sol, self.dm, self.spec)
        if new_score.sort_key < current_score.sort_key:
            return new_sol
        return None
