"""局部搜索可复用的基础 move primitive。"""

from __future__ import annotations

from mm_final.routing.candidate import CandidateRoute, CandidateSolution


def reverse_segment(
    solution: CandidateSolution,
    route_index: int,
    start_index: int,
    end_index: int,
) -> CandidateSolution:
    route = solution.routes[route_index]
    order = list(route.required_visit_order)
    _require_index(start_index, len(order), "start_index")
    _require_index(end_index, len(order), "end_index")
    if start_index > end_index:
        raise ValueError("start_index must be <= end_index.")

    order[start_index : end_index + 1] = reversed(order[start_index : end_index + 1])
    return _replace_route(solution, route_index, tuple(order))


def relocate_node(
    solution: CandidateSolution,
    from_route_index: int,
    node_index: int,
    to_route_index: int,
    insert_index: int,
) -> CandidateSolution:
    routes = [list(route.required_visit_order) for route in solution.routes]
    _require_index(from_route_index, len(routes), "from_route_index")
    _require_index(to_route_index, len(routes), "to_route_index")
    _require_index(node_index, len(routes[from_route_index]), "node_index")
    if insert_index < 0 or insert_index > len(routes[to_route_index]):
        raise ValueError("insert_index is out of range.")

    node = routes[from_route_index].pop(node_index)
    if from_route_index == to_route_index and insert_index > node_index:
        insert_index -= 1
    routes[to_route_index].insert(insert_index, node)

    return _replace_all_routes(solution, routes)


def swap_nodes(
    solution: CandidateSolution,
    left_route_index: int,
    left_node_index: int,
    right_route_index: int,
    right_node_index: int,
) -> CandidateSolution:
    routes = [list(route.required_visit_order) for route in solution.routes]
    _require_index(left_route_index, len(routes), "left_route_index")
    _require_index(right_route_index, len(routes), "right_route_index")
    _require_index(left_node_index, len(routes[left_route_index]), "left_node_index")
    _require_index(right_node_index, len(routes[right_route_index]), "right_node_index")

    routes[left_route_index][left_node_index], routes[right_route_index][right_node_index] = (
        routes[right_route_index][right_node_index],
        routes[left_route_index][left_node_index],
    )
    return _replace_all_routes(solution, routes)


def _replace_route(solution: CandidateSolution, route_index: int, visit_order: tuple[str, ...]) -> CandidateSolution:
    routes = list(solution.routes)
    old_route = routes[route_index]
    routes[route_index] = CandidateRoute(route_id=old_route.route_id, required_visit_order=visit_order)
    return CandidateSolution(
        routes=tuple(routes),
        method=solution.method,
        parameters=solution.parameters,
        seed=solution.seed,
        runtime_seconds=solution.runtime_seconds,
    )


def _replace_all_routes(solution: CandidateSolution, route_orders: list[list[str]]) -> CandidateSolution:
    routes = tuple(
        CandidateRoute(route_id=old_route.route_id, required_visit_order=tuple(route_order))
        for old_route, route_order in zip(solution.routes, route_orders)
    )
    return CandidateSolution(
        routes=routes,
        method=solution.method,
        parameters=solution.parameters,
        seed=solution.seed,
        runtime_seconds=solution.runtime_seconds,
    )


def _require_index(index: int, length: int, label: str) -> None:
    if index < 0 or index >= length:
        raise ValueError(f"{label} is out of range.")
