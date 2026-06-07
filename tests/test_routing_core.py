import networkx as nx

from mm_final.network import RoadNetwork
from mm_final.routing import (
    CandidateRoute,
    CandidateSolution,
    DistanceMatrix,
    ObjectiveSpec,
    SolutionPool,
    build_candidate_from_groups,
    candidate_to_route_plan,
    relocate_node,
    reverse_segment,
    score_candidate,
    swap_nodes,
)


def make_network():
    graph = nx.Graph()
    graph.add_edge("O", "A", weight=2.0)
    graph.add_edge("A", "B", weight=3.0)
    graph.add_edge("B", "1", weight=4.0)
    graph.add_edge("O", "1", weight=20.0)
    return RoadNetwork(graph)


def make_matrix():
    return DistanceMatrix.from_network(make_network(), nodes=("A", "B", "1"))


def test_road_network_shortest_path_returns_distance_and_nodes():
    shortest_path = make_network().shortest_path("O", "1")

    assert shortest_path.distance_km == 9.0
    assert shortest_path.node_path == ("O", "A", "B", "1")


def test_distance_matrix_expands_closed_route_without_duplicate_boundaries():
    matrix = make_matrix()

    route_path = matrix.route_path(("A", "1"))

    assert route_path.distance_km == 18.0
    assert route_path.expanded_node_path == ("O", "A", "B", "1", "B", "A", "O")


def test_score_candidate_computes_distance_time_penalty_and_diagnostics():
    matrix = make_matrix()
    solution = CandidateSolution(
        routes=(
            CandidateRoute("R1", ("A", "B")),
            CandidateRoute("R2", ("1",)),
            CandidateRoute("R3", ()),
        ),
        method="manual",
        seed=7,
    )
    objective = ObjectiveSpec(required_visit_nodes=frozenset(("A", "B", "1")))

    score = score_candidate(solution, matrix, objective)

    assert score.total_distance_km == 28.0
    assert score.max_route_distance_km == 18.0
    assert score.min_route_distance_km == 0.0
    assert score.distance_range_km == 18.0
    assert score.penalty == objective.empty_route_penalty
    assert {diagnostic.code for diagnostic in score.diagnostics} == {"empty_route"}


def test_build_candidate_from_groups_keeps_grouping_and_metadata():
    solution = build_candidate_from_groups(
        [("A", "B"), ("1",)],
        lambda group: tuple(reversed(group)),
        method="cluster_first",
        parameters={"k": 2},
        seed=13,
    )

    assert solution.method == "cluster_first"
    assert solution.parameters["k"] == 2
    assert solution.seed == 13
    assert solution.routes[0].required_visit_order == ("B", "A")


def test_objective_spec_can_penalize_fixed_group_count_mismatch():
    matrix = make_matrix()
    solution = CandidateSolution(routes=(CandidateRoute("R1", ("A", "B", "1")),))
    objective = ObjectiveSpec(required_visit_nodes=frozenset(("A", "B", "1")), fixed_group_count=2)

    score = score_candidate(solution, matrix, objective)

    assert score.penalty == objective.group_count_mismatch_penalty
    assert {diagnostic.code for diagnostic in score.diagnostics} == {"group_count_mismatch"}


def test_move_primitives_only_apply_requested_local_change():
    solution = CandidateSolution(
        routes=(
            CandidateRoute("R1", ("A", "B")),
            CandidateRoute("R2", ("1",)),
        )
    )

    reversed_solution = reverse_segment(solution, 0, 0, 1)
    relocated_solution = relocate_node(solution, 0, 1, 1, 0)
    swapped_solution = swap_nodes(solution, 0, 1, 1, 0)

    assert reversed_solution.routes[0].required_visit_order == ("B", "A")
    assert relocated_solution.routes[0].required_visit_order == ("A",)
    assert relocated_solution.routes[1].required_visit_order == ("B", "1")
    assert swapped_solution.routes[0].required_visit_order == ("A", "1")
    assert swapped_solution.routes[1].required_visit_order == ("B",)


def test_candidate_to_route_plan_preserves_contract_nullable_fields_by_default():
    solution = CandidateSolution(routes=(CandidateRoute("R1", ("A", "1")),), method="two_opt", seed=3)

    plan = candidate_to_route_plan(solution, plan_id="candidate-001")

    assert plan.schema_version == "route-plan-v1"
    assert plan.source == "two_opt"
    assert plan.parameters["seed"] == 3
    assert plan.metrics is None
    assert plan.routes[0].depot == "O"
    assert plan.routes[0].expanded_node_path is None
    assert plan.routes[0].distance_km is None
    assert plan.routes[0].metrics is None


def test_candidate_to_route_plan_can_include_expanded_paths_without_metrics():
    matrix = make_matrix()
    solution = CandidateSolution(routes=(CandidateRoute("R1", ("A", "1")),))

    plan = candidate_to_route_plan(
        solution,
        plan_id="candidate-002",
        distance_matrix=matrix,
        include_expanded_paths=True,
    )

    assert plan.routes[0].expanded_node_path == ["O", "A", "B", "1", "B", "A", "O"]
    assert plan.routes[0].distance_km == 18.0
    assert plan.routes[0].metrics is None


def test_solution_pool_keeps_top_n_candidates_by_score_key():
    matrix = make_matrix()
    objective = ObjectiveSpec(required_visit_nodes=frozenset(("A", "B", "1")))
    pool = SolutionPool(max_size=2)
    candidates = [
        CandidateSolution(routes=(CandidateRoute("R1", ("A", "B", "1")),), method="long"),
        CandidateSolution(routes=(CandidateRoute("R1", ("A", "B")),), method="missing"),
        CandidateSolution(routes=(CandidateRoute("R1", ("1",)), CandidateRoute("R2", ("A", "B"))), method="split"),
    ]

    for candidate in candidates:
        pool.add(candidate, score_candidate(candidate, matrix, objective))

    assert len(pool.items) == 2
    assert pool.best.solution.method == "split"
    assert {item.solution.method for item in pool.items} == {"long", "split"}
