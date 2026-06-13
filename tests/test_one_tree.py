"""测试 one_tree 模块的 1-树下界计算和次梯度优化。"""

import pytest
from mm_final.routing.one_tree import OneTreeComputer, SubgradientOptimizer


class TestOneTreeComputer:

    def test_three_node_triangle(self):
        nodes = ["O", "A", "B"]
        dist = [
            [0, 10, 20],
            [10, 0, 10],
            [20, 10, 0]
        ]
        computer = OneTreeComputer(dist, nodes)
        pi = [0.0, 0.0, 0.0]
        result = computer.compute(pi)

        assert result.lower_bound == 40.0
        assert result.is_tour == True
        assert result.node_degrees == [2, 2, 2]

    def test_three_node_optimize_no_change(self):
        nodes = ["O", "A", "B"]
        dist = [
            [0, 10, 20],
            [10, 0, 10],
            [20, 10, 0]
        ]
        computer = OneTreeComputer(dist, nodes)
        optimizer = SubgradientOptimizer(computer, max_iterations=100)
        ub = 40.0
        best_lb, result, pi = optimizer.optimize(ub)

        assert best_lb == 40.0
        assert result.is_tour == True

    def test_four_node_square(self):
        nodes = ["O", "A", "B", "C"]
        dist = [
            [0, 10, 15, 20],
            [10, 0, 5, 15],
            [15, 5, 0, 10],
            [20, 15, 10, 0]
        ]
        computer = OneTreeComputer(dist, nodes)
        result_init = computer.compute([0, 0, 0, 0])
        assert result_init.is_tour == False or result_init.lower_bound < 45.0

        optimizer = SubgradientOptimizer(computer, max_iterations=1000)
        ub = 45.0
        best_lb, result_opt, pi = optimizer.optimize(ub)

        assert best_lb <= 45.0
        assert best_lb >= 44.9
        if result_opt.is_tour:
            assert result_opt.lower_bound == 45.0

    def test_forbidden_and_forced_edges(self):
        nodes = ["O", "A", "B", "C"]
        dist = [
            [0, 10, 15, 20],
            [10, 0, 5, 15],
            [15, 5, 0, 10],
            [20, 15, 10, 0]
        ]
        computer = OneTreeComputer(dist, nodes)

        force = {(0, 1)}
        result_force = computer.compute([0, 0, 0, 0], force_edges=force)
        assert result_force.node_degrees[0] >= 1
        assert result_force.node_degrees[1] >= 1

        forbidden = {(0, 2)}
        result_forbid = computer.compute([0, 0, 0, 0], forbidden_edges=forbidden)
