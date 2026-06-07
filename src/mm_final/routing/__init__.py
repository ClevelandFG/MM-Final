"""A/B 两线共享的路线候选解评分底座。"""

from mm_final.routing.candidate import CandidateRoute, CandidateSolution, build_candidate_from_groups
from mm_final.routing.distance_matrix import DistanceMatrix, RoutePath
from mm_final.routing.export import candidate_to_route_plan
from mm_final.routing.moves import relocate_node, reverse_segment, swap_nodes
from mm_final.routing.pool import ScoredCandidate, SolutionPool
from mm_final.routing.scoring import ObjectiveSpec, Score, ScoreDiagnostic, score_candidate

__all__ = [
    "CandidateRoute",
    "CandidateSolution",
    "DistanceMatrix",
    "ObjectiveSpec",
    "RoutePath",
    "Score",
    "ScoreDiagnostic",
    "ScoredCandidate",
    "SolutionPool",
    "build_candidate_from_groups",
    "candidate_to_route_plan",
    "relocate_node",
    "reverse_segment",
    "score_candidate",
    "swap_nodes",
]
