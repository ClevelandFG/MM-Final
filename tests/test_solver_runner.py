import networkx as nx

from mm_final.network import RoadNetwork
from mm_final.solving import CancelToken, DefaultAlgorithmRunner, SolveJob, SolveParameters


def make_small_network():
    graph = nx.Graph()
    graph.add_edge("O", "A", weight=2.0)
    graph.add_edge("A", "B", weight=3.0)
    graph.add_edge("B", "1", weight=4.0)
    graph.add_edge("O", "1", weight=12.0)
    return RoadNetwork(graph)


def test_default_runner_solves_fixed_group_job_and_returns_audited_candidate():
    runner = DefaultAlgorithmRunner()
    events = []
    job = SolveJob(
        job_id="gui-smoke",
        problem_kind="fixed_groups",
        parameters=SolveParameters(
            group_count=2,
            time_limit_seconds=5.0,
            iterations=2,
            required_visit_nodes=frozenset(("A", "B", "1")),
        ),
        plan_id="gui-smoke-plan",
    )

    result = runner.run(job, road_network=make_small_network(), event_sink=events.append)

    assert result.status == "completed"
    assert result.recommended_plan_id == "gui-smoke-plan"
    assert result.recommended_candidate is not None
    assert result.recommended_candidate.is_final_valid
    assert result.recommended_candidate.audit_result.recomputed_metrics is not None
    assert result.recommended_candidate.audit_result.recomputed_metrics.group_count == 2
    assert {event.kind for event in events} >= {"started", "progress", "candidate", "completed"}


def test_default_runner_honors_cancel_token_before_solving():
    token = CancelToken()
    token.request_cancel()
    job = SolveJob(job_id="cancelled", problem_kind="fixed_groups")

    result = DefaultAlgorithmRunner().run(job, road_network=make_small_network(), cancel_token=token)

    assert result.status == "cancelled"
    assert result.candidates == ()
    assert result.events[-1].kind == "cancelled"
