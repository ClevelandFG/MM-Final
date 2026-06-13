"""不限组数的 min-max VRP 求解器（最小化最晚完工时间）"""

from __future__ import annotations

import math
from typing import Optional

from mm_final.routing.mtsp_solver import MTSP_Solver
from mm_final.routing.distance_matrix import DistanceMatrix
from mm_final.routing.scoring import ObjectiveSpec, score_candidate
from mm_final.routing.candidate import CandidateSolution


class MinMaxVRP_Solver:
    def __init__(
        self,
        distance_matrix: DistanceMatrix,
        T_hour: float = 2.0,
        t_hour: float = 1.0,
        speed_km_per_hour: float = 35.0,
        time_limit_seconds: float = 600.0,
        max_group_upper: int = 10,
    ):
        self.dm = distance_matrix
        self.T = T_hour
        self.t = t_hour
        self.v = speed_km_per_hour
        self.time_limit = time_limit_seconds
        self.max_group_upper = max_group_upper

        self._lower_bound_time = self._compute_lower_bound()

    def _compute_lower_bound(self) -> float:
        max_single = 0.0
        depot = self.dm.nodes[0]
        for node in self.dm.nodes[1:]:
            dist = self.dm.distance_km(depot, node)
            time = 2 * dist / self.v
            from mm_final.network import classify_node, NodeType
            node_type = classify_node(node)
            stop = self.T if node_type == NodeType.TOWN else self.t
            total = time + stop
            if total > max_single:
                max_single = total
        return max_single

    def solve(self) -> CandidateSolution:
        best_solution = None
        best_max_time = float('inf')

        for k in range(2, self.max_group_upper + 1):
            spec = ObjectiveSpec(
                T_hour=self.T,
                t_hour=self.t,
                speed_km_per_hour=self.v,
                time_limit_hour=float('inf'),
                mode="weighted",
                weights={"max_route_time_hour": 1.0},
            )

            solver = MTSP_Solver(
                self.dm,
                group_count=k,
                objective_spec=spec,
                time_limit_seconds=self.time_limit,
                iterations=30,
            )
            solution = solver.solve()
            score = score_candidate(solution, self.dm, spec)

            if score.penalty == 0.0 and score.max_route_time_hour < best_max_time:
                best_max_time = score.max_route_time_hour
                best_solution = solution

            if best_max_time <= self._lower_bound_time + 1e-6:
                break

        return best_solution
