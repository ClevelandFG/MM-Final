"""B8c GUI 与 A/B 后端之间的求解 runner 契约。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, Literal, Optional, Protocol

from mm_final.contracts import AuditResult, RoutePlan
from mm_final.evaluation.route_plan_auditor import audit_route_plan
from mm_final.evaluation.route_plan_evaluator import EvaluationParameters
from mm_final.network import REQUIRED_VISIT_NODES, RoadNetwork, load_road_network
from mm_final.routing import DistanceMatrix, ObjectiveSpec, Score, score_candidate
from mm_final.routing.bb_solver import BranchAndBoundTspSolver
from mm_final.routing.candidate import CandidateSolution
from mm_final.routing.export import candidate_to_route_plan
from mm_final.routing.min_groups import MinGroupsSolver
from mm_final.routing.minmax_vrp import MinMaxVRP_Solver
from mm_final.routing.mtsp_solver import MTSP_Solver


ProblemKind = Literal["fixed_groups", "minimum_groups", "unlimited_personnel"]
SolveStatus = Literal["completed", "failed", "cancelled"]
SolveEventKind = Literal["started", "progress", "log", "candidate", "completed", "failed", "cancelled"]
SolveEventSink = Callable[["SolveEvent"], None]


@dataclass(frozen=True)
class SolveParameters:
    """GUI 可收集的求解参数；工程参数作为高级口径保留默认值。"""

    T_hour: float = 2.0
    t_hour: float = 1.0
    speed_km_per_hour: float = 35.0
    time_limit_hour: float = 24.0
    group_count: int = 3
    max_group_upper: int = 8
    time_limit_seconds: float = 600.0
    iterations: int = 50
    required_visit_nodes: frozenset[str] = field(default_factory=lambda: frozenset(REQUIRED_VISIT_NODES))

    def validate(self) -> None:
        if self.T_hour < 0:
            raise ValueError("T_hour must be >= 0.")
        if self.t_hour < 0:
            raise ValueError("t_hour must be >= 0.")
        if self.speed_km_per_hour <= 0:
            raise ValueError("speed_km_per_hour must be > 0.")
        if self.time_limit_hour <= 0:
            raise ValueError("time_limit_hour must be > 0.")
        if self.group_count <= 0:
            raise ValueError("group_count must be > 0.")
        if self.max_group_upper <= 0:
            raise ValueError("max_group_upper must be > 0.")
        if self.time_limit_seconds <= 0:
            raise ValueError("time_limit_seconds must be > 0.")
        if self.iterations <= 0:
            raise ValueError("iterations must be > 0.")

    def to_evaluation_parameters(self) -> EvaluationParameters:
        return EvaluationParameters(
            T_hour=self.T_hour,
            t_hour=self.t_hour,
            speed_km_per_hour=self.speed_km_per_hour,
            time_limit_hour=self.time_limit_hour,
            required_visit_nodes=self.required_visit_nodes,
        )

    def to_route_plan_parameters(self) -> dict[str, object]:
        return {
            "T_hour": self.T_hour,
            "t_hour": self.t_hour,
            "speed_km_per_hour": self.speed_km_per_hour,
            "time_limit_hour": self.time_limit_hour,
            "group_count": self.group_count,
        }


@dataclass(frozen=True)
class SolveJob:
    job_id: str
    problem_kind: ProblemKind
    algorithm_id: str = "default"
    parameters: SolveParameters = field(default_factory=SolveParameters)
    plan_id: Optional[str] = None


@dataclass(frozen=True)
class SolveEvent:
    kind: SolveEventKind
    message: str
    progress: Optional[float] = None
    plan_id: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "message": self.message,
            "progress": self.progress,
            "plan_id": self.plan_id,
        }


class CancelToken:
    """GUI 后台任务使用的协作式取消令牌。"""

    def __init__(self) -> None:
        self._cancel_requested = False

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_requested

    def request_cancel(self) -> None:
        self._cancel_requested = True


@dataclass(frozen=True)
class SolveCandidate:
    plan: RoutePlan
    score: Score
    audit_result: AuditResult
    sort_key: tuple[float, ...]

    @property
    def plan_id(self) -> str:
        return self.plan.plan_id

    @property
    def is_final_valid(self) -> bool:
        audit = self.audit_result
        return audit.schema_valid and audit.coverage_valid and audit.route_valid and audit.metric_valid

    def to_dict(self) -> dict[str, object]:
        metrics = self.audit_result.recomputed_metrics
        return {
            "plan_id": self.plan.plan_id,
            "source": self.plan.source,
            "is_final_valid": self.is_final_valid,
            "sort_key": list(self.sort_key),
            "score": {
                "total_distance_km": self.score.total_distance_km,
                "max_route_distance_km": self.score.max_route_distance_km,
                "distance_range_km": self.score.distance_range_km,
                "total_time_hour": self.score.total_time_hour,
                "max_route_time_hour": self.score.max_route_time_hour,
                "time_range_hour": self.score.time_range_hour,
                "penalty": self.score.penalty,
            },
            "audit_result": {
                "plan_id": self.audit_result.plan_id,
                "schema_valid": self.audit_result.schema_valid,
                "coverage_valid": self.audit_result.coverage_valid,
                "route_valid": self.audit_result.route_valid,
                "metric_valid": self.audit_result.metric_valid,
                "errors": list(self.audit_result.errors),
                "warnings": list(self.audit_result.warnings),
                "recomputed_metrics": None if metrics is None else asdict(metrics),
            },
        }


@dataclass(frozen=True)
class SolveResult:
    job: SolveJob
    status: SolveStatus
    candidates: tuple[SolveCandidate, ...] = ()
    recommended_plan_id: Optional[str] = None
    events: tuple[SolveEvent, ...] = ()
    error: Optional[str] = None

    @property
    def recommended_candidate(self) -> Optional[SolveCandidate]:
        if self.recommended_plan_id is None:
            return None
        return next((item for item in self.candidates if item.plan_id == self.recommended_plan_id), None)

    def to_dict(self) -> dict[str, object]:
        return {
            "job": {
                "job_id": self.job.job_id,
                "problem_kind": self.job.problem_kind,
                "algorithm_id": self.job.algorithm_id,
                "parameters": _parameters_to_dict(self.job.parameters),
                "plan_id": self.job.plan_id,
            },
            "status": self.status,
            "recommended_plan_id": self.recommended_plan_id,
            "candidate_count": len(self.candidates),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "events": [event.to_dict() for event in self.events],
            "error": self.error,
        }


class AlgorithmRunner(Protocol):
    def run(
        self,
        job: SolveJob,
        *,
        road_network: Optional[RoadNetwork] = None,
        event_sink: Optional[SolveEventSink] = None,
        cancel_token: Optional[CancelToken] = None,
    ) -> SolveResult:
        """运行一次求解任务。"""


class DefaultAlgorithmRunner:
    """复用现有 A 线 solver 的默认 GUI runner。"""

    def run(
        self,
        job: SolveJob,
        *,
        road_network: Optional[RoadNetwork] = None,
        event_sink: Optional[SolveEventSink] = None,
        cancel_token: Optional[CancelToken] = None,
    ) -> SolveResult:
        events: list[SolveEvent] = []

        def emit(event: SolveEvent) -> None:
            events.append(event)
            if event_sink is not None:
                event_sink(event)

        token = CancelToken() if cancel_token is None else cancel_token
        emit(SolveEvent("started", f"开始求解 {job.problem_kind}", 0.0))
        try:
            job.parameters.validate()
            if token.is_cancelled:
                return _cancelled(job, events, emit)

            network = _road_network(road_network)
            distance_matrix = DistanceMatrix.from_network(network, nodes=job.parameters.required_visit_nodes)
            solution = self._solve(job, distance_matrix, emit, token)
            if token.is_cancelled:
                return _cancelled(job, events, emit)
            if solution is None:
                raise RuntimeError("Solver did not return a feasible candidate.")

            candidate = _candidate_from_solution(job, solution, network, distance_matrix)
            emit(SolveEvent("candidate", f"生成候选方案 {candidate.plan_id}", 0.9, candidate.plan_id))
            emit(SolveEvent("completed", "求解完成", 1.0, candidate.plan_id))
            return SolveResult(
                job=job,
                status="completed",
                candidates=(candidate,),
                recommended_plan_id=candidate.plan_id,
                events=tuple(events),
            )
        except Exception as exc:
            emit(SolveEvent("failed", f"求解失败：{exc}", plan_id=job.plan_id))
            return SolveResult(job=job, status="failed", events=tuple(events), error=str(exc))

    def _solve(
        self,
        job: SolveJob,
        distance_matrix: DistanceMatrix,
        emit: SolveEventSink,
        token: CancelToken,
    ) -> Optional[CandidateSolution]:
        algorithm_id = _resolve_algorithm_id(job.problem_kind, job.algorithm_id)
        params = job.parameters
        if algorithm_id == "branch_and_bound":
            emit(SolveEvent("progress", "运行单路线分支定界求解器", 0.2))
            return BranchAndBoundTspSolver.from_distance_matrix(distance_matrix).solve()

        if algorithm_id == "mtsp_local_search":
            emit(SolveEvent("progress", f"运行固定 {params.group_count} 组局部搜索", 0.2))
            objective = ObjectiveSpec(
                T_hour=params.T_hour,
                t_hour=params.t_hour,
                speed_km_per_hour=params.speed_km_per_hour,
                time_limit_hour=float("inf"),
                required_visit_nodes=params.required_visit_nodes,
                fixed_group_count=params.group_count,
                mode="weighted",
                weights={
                    "total_distance_km": 1.0,
                    "max_route_distance_km": 0.5,
                    "distance_range_km": 0.5,
                },
            )
            solver = MTSP_Solver(
                distance_matrix,
                group_count=params.group_count,
                objective_spec=objective,
                time_limit_seconds=params.time_limit_seconds,
                iterations=params.iterations,
            )
            return solver.solve()

        if algorithm_id == "min_groups_search":
            emit(SolveEvent("progress", "运行 24 小时最少组数搜索", 0.2))
            solver = MinGroupsSolver(
                distance_matrix,
                T_hour=params.T_hour,
                t_hour=params.t_hour,
                speed_km_per_hour=params.speed_km_per_hour,
                time_limit_hour=params.time_limit_hour,
                max_group_upper=params.max_group_upper,
                time_limit_seconds=params.time_limit_seconds,
            )
            return solver.solve()

        if algorithm_id == "minmax_vrp_search":
            emit(SolveEvent("progress", "运行人员足够时最短完成时间搜索", 0.2))
            solver = MinMaxVRP_Solver(
                distance_matrix,
                T_hour=params.T_hour,
                t_hour=params.t_hour,
                speed_km_per_hour=params.speed_km_per_hour,
                time_limit_seconds=params.time_limit_seconds,
                max_group_upper=params.max_group_upper,
            )
            return solver.solve()

        raise ValueError(f"Unsupported algorithm_id: {algorithm_id}")


def _candidate_from_solution(
    job: SolveJob,
    solution: CandidateSolution,
    road_network: RoadNetwork,
    distance_matrix: DistanceMatrix,
) -> SolveCandidate:
    params = job.parameters
    plan_id = job.plan_id or f"{job.problem_kind}-{solution.method}"
    plan = candidate_to_route_plan(
        solution,
        plan_id=plan_id,
        source=solution.method,
        parameters=params.to_route_plan_parameters(),
        distance_matrix=distance_matrix,
        include_expanded_paths=True,
    )
    objective = ObjectiveSpec(
        T_hour=params.T_hour,
        t_hour=params.t_hour,
        speed_km_per_hour=params.speed_km_per_hour,
        time_limit_hour=params.time_limit_hour,
        required_visit_nodes=params.required_visit_nodes,
        fixed_group_count=params.group_count if job.problem_kind == "fixed_groups" else None,
    )
    score = score_candidate(solution, distance_matrix, objective)
    audit = audit_route_plan(plan, road_network, params.to_evaluation_parameters(), mode="final")
    return SolveCandidate(plan=plan, score=score, audit_result=audit, sort_key=score.sort_key)


def _resolve_algorithm_id(problem_kind: ProblemKind, algorithm_id: str) -> str:
    if algorithm_id != "default":
        return algorithm_id
    defaults = {
        "fixed_groups": "mtsp_local_search",
        "minimum_groups": "min_groups_search",
        "unlimited_personnel": "minmax_vrp_search",
    }
    return defaults[problem_kind]


def _road_network(road_network: Optional[RoadNetwork]) -> RoadNetwork:
    if road_network is not None:
        return road_network
    result = load_road_network()
    if result.network is None:
        error_text = "; ".join(item.to_text() for item in result.errors)
        raise RuntimeError(f"Default road network failed to load: {error_text}")
    return result.network


def _cancelled(
    job: SolveJob,
    events: list[SolveEvent],
    emit: SolveEventSink,
) -> SolveResult:
    emit(SolveEvent("cancelled", "求解已取消"))
    return SolveResult(job=job, status="cancelled", events=tuple(events))


def _parameters_to_dict(params: SolveParameters) -> dict[str, object]:
    data = asdict(params)
    data["required_visit_nodes"] = sorted(params.required_visit_nodes, key=_node_sort_key)
    return data


def _node_sort_key(node: str) -> tuple[int, int, str]:
    if node == "O":
        return (0, 0, node)
    if node.isalpha():
        return (1, 0, node)
    if node.isdigit():
        return (2, int(node), node)
    if node.startswith("U") and node[1:].isdigit():
        return (3, int(node[1:]), node)
    return (4, 0, node)
