"""时间限制下的最少分组数求解器（含最佳路线优化）"""

from __future__ import annotations

import math
from typing import Optional

from mm_final.routing.mtsp_solver import MTSP_Solver
from mm_final.routing.distance_matrix import DistanceMatrix
from mm_final.routing.scoring import ObjectiveSpec, score_candidate
from mm_final.routing.candidate import CandidateSolution


class MinGroupsSolver:
    def __init__(
        self,
        distance_matrix: DistanceMatrix,
        T_hour: float = 2.0,
        t_hour: float = 1.0,
        speed_km_per_hour: float = 35.0,
        time_limit_hour: float = 24.0,
        max_group_upper: int = 10,
        time_limit_seconds: float = 600.0,
    ):
        self.dm = distance_matrix
        self.T = T_hour
        self.t = t_hour
        self.v = speed_km_per_hour
        self.time_limit_hour = time_limit_hour
        self.max_group_upper = max_group_upper
        self.time_limit_seconds = time_limit_seconds

        self._lower_k = self._estimate_min_k()

    def _estimate_min_k(self) -> int:
        single_km = 672.7
        single_time = single_km / self.v + 18 * self.T + 35 * self.t
        return max(2, math.ceil(single_time / self.time_limit_hour))

    def solve(self) -> Optional[CandidateSolution]:
        print(f"下界 k_min = {self._lower_k}")

        for k in range(self._lower_k, self.max_group_upper + 1):
            print(f"尝试 k = {k} ...")
            spec_strict = ObjectiveSpec(
                T_hour=self.T,
                t_hour=self.t,
                speed_km_per_hour=self.v,
                time_limit_hour=self.time_limit_hour,
                time_limit_penalty_weight=1000.0,
                mode="lexicographic",
            )
            solver = MTSP_Solver(
                self.dm,
                group_count=k,
                objective_spec=spec_strict,
                time_limit_seconds=self.time_limit_seconds,
                iterations=40,
            )
            solution = solver.solve()
            score = score_candidate(solution, self.dm, spec_strict)

            if score.penalty == 0.0:
                print(f"找到可行解，最少分组数为 {k}，现在优化该分组方案...")
                refine_spec = ObjectiveSpec(
                    T_hour=self.T,
                    t_hour=self.t,
                    speed_km_per_hour=self.v,
                    time_limit_hour=self.time_limit_hour,
                    time_limit_penalty_weight=1000.0,
                    mode="weighted",
                    weights={
                        "total_distance_km": 1.0,
                        "max_route_time_hour": 0.5,
                        "time_range_hour": 0.5,
                    }
                )
                refiner = MTSP_Solver(
                    self.dm,
                    group_count=k,
                    objective_spec=refine_spec,
                    time_limit_seconds=self.time_limit_seconds,
                    iterations=80,
                )
                best_solution = refiner.solve()
                return best_solution
            else:
                print(f"k={k} 不可行 (max_time={score.max_route_time_hour:.2f}h, penalty={score.penalty})")

        return None
