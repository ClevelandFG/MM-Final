"""GUI 求解任务共享入口。"""

from mm_final.solving.runner import (
    AlgorithmRunner,
    CancelToken,
    DefaultAlgorithmRunner,
    ProblemKind,
    SolveCandidate,
    SolveEvent,
    SolveJob,
    SolveParameters,
    SolveResult,
    SolveStatus,
)

__all__ = [
    "AlgorithmRunner",
    "CancelToken",
    "DefaultAlgorithmRunner",
    "ProblemKind",
    "SolveCandidate",
    "SolveEvent",
    "SolveJob",
    "SolveParameters",
    "SolveResult",
    "SolveStatus",
]
