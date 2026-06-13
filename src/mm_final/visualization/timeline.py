"""路线动画时间轴模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Optional

from mm_final.contracts import RoutePlan
from mm_final.evaluation import EvaluationParameters, EvaluationResult, evaluate_route_plan
from mm_final.network import DEPOT, NodeType, RoadNetwork, classify_node


SegmentKind = Literal["travel", "stop"]
TeamStatus = Literal["not_started", "traveling", "stopping", "finished"]


@dataclass(frozen=True)
class RouteSegment:
    """单队时间轴上的行驶或停留片段。"""

    route_id: str
    kind: SegmentKind
    start_hour: float
    end_hour: float
    source: str
    target: str
    distance_km: float = 0.0

    @property
    def duration_hour(self) -> float:
        return self.end_hour - self.start_hour


@dataclass(frozen=True)
class EdgeProgress:
    """某一时刻某条边已经染色的比例。"""

    route_id: str
    source: str
    target: str
    progress: float


@dataclass(frozen=True)
class TeamState:
    """某一时刻单队的可渲染状态。"""

    route_id: str
    status: TeamStatus
    current_node: Optional[str]
    edge: Optional[tuple[str, str]]
    edge_progress: float
    elapsed_hour: float
    total_time_hour: float


@dataclass(frozen=True)
class RouteAnimationSnapshot:
    """全局动画快照。"""

    time_hour: float
    completion_time_hour: float
    progress_ratio: float
    team_states: tuple[TeamState, ...]
    traversed_edges: tuple[EdgeProgress, ...]


@dataclass(frozen=True)
class RouteAnimationTimeline:
    """基于 B2/B3 复算路径构造的可播放路线时间轴。"""

    plan_id: str
    source: str
    parameters: EvaluationParameters
    segments_by_route_id: Mapping[str, tuple[RouteSegment, ...]]
    route_total_time_hour: Mapping[str, float]
    route_distance_km: Mapping[str, float]
    completion_time_hour: float

    @classmethod
    def from_route_plan(
        cls,
        plan: RoutePlan,
        road_network: RoadNetwork,
        parameters: Optional[EvaluationParameters] = None,
    ) -> "RouteAnimationTimeline":
        """复用 B2 评价口径，从 RoutePlan 构造动画时间轴。"""

        params = EvaluationParameters.from_route_plan(plan) if parameters is None else parameters
        evaluation = evaluate_route_plan(plan, road_network, params)
        if evaluation.plan_metrics is None:
            raise ValueError("Cannot build animation timeline when evaluation has no plan metrics.")

        segments_by_route_id: dict[str, tuple[RouteSegment, ...]] = {}
        route_total_time_hour: dict[str, float] = {}
        route_distance_km: dict[str, float] = {}
        for route in plan.routes:
            segments = _segments_for_route(route.route_id, route.required_visit_order, road_network, params)
            segments_by_route_id[route.route_id] = tuple(segments)
            route_total_time_hour[route.route_id] = segments[-1].end_hour if segments else 0.0
            route_distance_km[route.route_id] = evaluation.route_metrics_by_id[route.route_id].distance_km

        return cls(
            plan_id=plan.plan_id,
            source=plan.source,
            parameters=params,
            segments_by_route_id=segments_by_route_id,
            route_total_time_hour=route_total_time_hour,
            route_distance_km=route_distance_km,
            completion_time_hour=evaluation.plan_metrics.completion_time_hour,
        )

    def state_at(self, time_hour: float) -> RouteAnimationSnapshot:
        """返回任意模型时刻的动画快照。"""

        time_clamped = min(max(float(time_hour), 0.0), self.completion_time_hour)
        team_states: list[TeamState] = []
        traversed_edges: list[EdgeProgress] = []

        for route_id, segments in self.segments_by_route_id.items():
            route_total = self.route_total_time_hour[route_id]
            team_states.append(_team_state_at(route_id, segments, route_total, time_clamped))
            traversed_edges.extend(_edge_progress_at(route_id, segments, time_clamped))

        progress_ratio = 1.0 if self.completion_time_hour <= 0 else time_clamped / self.completion_time_hour
        return RouteAnimationSnapshot(
            time_hour=time_clamped,
            completion_time_hour=self.completion_time_hour,
            progress_ratio=progress_ratio,
            team_states=tuple(team_states),
            traversed_edges=tuple(traversed_edges),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "source": self.source,
            "parameters": {
                "T_hour": self.parameters.T_hour,
                "t_hour": self.parameters.t_hour,
                "speed_km_per_hour": self.parameters.speed_km_per_hour,
                "time_limit_hour": self.parameters.time_limit_hour,
            },
            "completion_time_hour": self.completion_time_hour,
            "route_total_time_hour": dict(self.route_total_time_hour),
            "route_distance_km": dict(self.route_distance_km),
            "segments_by_route_id": {
                route_id: [
                    {
                        "kind": segment.kind,
                        "start_hour": segment.start_hour,
                        "end_hour": segment.end_hour,
                        "source": segment.source,
                        "target": segment.target,
                        "distance_km": segment.distance_km,
                    }
                    for segment in segments
                ]
                for route_id, segments in self.segments_by_route_id.items()
            },
        }


def _segments_for_route(
    route_id: str,
    required_visit_order: list[str],
    road_network: RoadNetwork,
    params: EvaluationParameters,
) -> list[RouteSegment]:
    segments: list[RouteSegment] = []
    current_hour = 0.0
    checkpoints = [DEPOT, *required_visit_order, DEPOT]

    for source, target in zip(checkpoints, checkpoints[1:]):
        path = road_network.shortest_path(source, target).node_path
        for edge_source, edge_target in zip(path, path[1:]):
            distance = road_network.edge_weight_km(edge_source, edge_target)
            duration = distance / params.speed_km_per_hour
            segments.append(
                RouteSegment(
                    route_id=route_id,
                    kind="travel",
                    start_hour=current_hour,
                    end_hour=current_hour + duration,
                    source=edge_source,
                    target=edge_target,
                    distance_km=distance,
                )
            )
            current_hour += duration

        stop_duration = _stop_duration_hour(target, params)
        if stop_duration > 0:
            segments.append(
                RouteSegment(
                    route_id=route_id,
                    kind="stop",
                    start_hour=current_hour,
                    end_hour=current_hour + stop_duration,
                    source=target,
                    target=target,
                )
            )
            current_hour += stop_duration

    return segments


def _stop_duration_hour(node: str, params: EvaluationParameters) -> float:
    node_type = classify_node(node)
    if node_type is NodeType.TOWN:
        return params.T_hour
    if node_type is NodeType.VILLAGE:
        return params.t_hour
    return 0.0


def _team_state_at(
    route_id: str,
    segments: tuple[RouteSegment, ...],
    route_total_time_hour: float,
    time_hour: float,
) -> TeamState:
    if not segments or time_hour <= 0:
        return TeamState(route_id, "not_started", DEPOT, None, 0.0, time_hour, route_total_time_hour)
    if time_hour >= route_total_time_hour:
        return TeamState(route_id, "finished", DEPOT, None, 1.0, route_total_time_hour, route_total_time_hour)

    for segment in segments:
        if segment.start_hour <= time_hour <= segment.end_hour:
            if segment.kind == "stop":
                return TeamState(
                    route_id=route_id,
                    status="stopping",
                    current_node=segment.source,
                    edge=None,
                    edge_progress=1.0,
                    elapsed_hour=time_hour,
                    total_time_hour=route_total_time_hour,
                )
            progress = (
                1.0
                if segment.duration_hour <= 0
                else (time_hour - segment.start_hour) / segment.duration_hour
            )
            return TeamState(
                route_id=route_id,
                status="traveling",
                current_node=None,
                edge=(segment.source, segment.target),
                edge_progress=min(max(progress, 0.0), 1.0),
                elapsed_hour=time_hour,
                total_time_hour=route_total_time_hour,
            )

    return TeamState(route_id, "finished", DEPOT, None, 1.0, route_total_time_hour, route_total_time_hour)


def _edge_progress_at(
    route_id: str,
    segments: tuple[RouteSegment, ...],
    time_hour: float,
) -> list[EdgeProgress]:
    progress: list[EdgeProgress] = []
    for segment in segments:
        if segment.kind != "travel" or time_hour <= segment.start_hour:
            continue
        if time_hour >= segment.end_hour:
            value = 1.0
        else:
            value = (time_hour - segment.start_hour) / segment.duration_hour if segment.duration_hour > 0 else 1.0
        progress.append(EdgeProgress(route_id, segment.source, segment.target, min(max(value, 0.0), 1.0)))
    return progress
