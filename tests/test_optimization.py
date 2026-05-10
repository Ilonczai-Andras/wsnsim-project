import json
import os
import pytest
from wsnsim.models.optimization import ParameterGrid, ParetoFilter, ConfigDumper

# --- ParameterGrid Tests ---

def test_parameter_grid_empty():
    grid = ParameterGrid({})
    assert len(grid) == 0
    configs = list(grid)
    assert configs == [{}]

def test_parameter_grid_single():
    grid = ParameterGrid({"a": [1, 2]})
    assert len(grid) == 2
    configs = list(grid)
    assert configs == [{"a": 1}, {"a": 2}]

def test_parameter_grid_multiple():
    grid = ParameterGrid({"a": [1, 2], "b": ["x", "y"]})
    assert len(grid) == 4
    configs = list(grid)
    assert configs == [
        {"a": 1, "b": "x"},
        {"a": 1, "b": "y"},
        {"a": 2, "b": "x"},
        {"a": 2, "b": "y"}
    ]

def test_parameter_grid_len():
    grid = ParameterGrid({"a": [1, 2, 3], "b": [4, 5], "c": [6]})
    assert len(grid) == 6

def test_parameter_grid_types():
    grid = ParameterGrid({"i": [1], "f": [2.5], "s": ["test"], "b": [True, False]})
    assert len(grid) == 2
    configs = list(grid)
    assert configs[0] == {"i": 1, "f": 2.5, "s": "test", "b": True}
    assert configs[1] == {"i": 1, "f": 2.5, "s": "test", "b": False}

# --- ParetoFilter _dominates Tests ---

def test_pareto_filter_dominates_max_max():
    pf = ParetoFilter(("max", "max"))
    assert pf._dominates((10.0, 10.0), (5.0, 5.0)) is True
    assert pf._dominates((5.0, 5.0), (10.0, 10.0)) is False
    assert pf._dominates((10.0, 5.0), (5.0, 5.0)) is True

def test_pareto_filter_dominates_min_min():
    pf = ParetoFilter(("min", "min"))
    assert pf._dominates((5.0, 5.0), (10.0, 10.0)) is True
    assert pf._dominates((10.0, 10.0), (5.0, 5.0)) is False
    assert pf._dominates((5.0, 10.0), (10.0, 10.0)) is True

def test_pareto_filter_dominates_max_min():
    pf = ParetoFilter(("max", "min"))
    assert pf._dominates((10.0, 5.0), (5.0, 10.0)) is True
    assert pf._dominates((5.0, 10.0), (10.0, 5.0)) is False
    assert pf._dominates((10.0, 10.0), (5.0, 10.0)) is True

def test_pareto_filter_dominates_min_max():
    pf = ParetoFilter(("min", "max"))
    # (5, 10) should dominate (10, 5) because min wants low (5 < 10) and max wants high (10 > 5)
    assert pf._dominates((5.0, 10.0), (10.0, 5.0)) is True
    assert pf._dominates((10.0, 5.0), (5.0, 10.0)) is False
    assert pf._dominates((5.0, 5.0), (10.0, 5.0)) is True

def test_pareto_filter_no_dominance_tradeoff():
    pf = ParetoFilter(("max", "max"))
    assert pf._dominates((10.0, 5.0), (5.0, 10.0)) is False
    assert pf._dominates((5.0, 10.0), (10.0, 5.0)) is False

def test_pareto_filter_identical_objectives():
    pf = ParetoFilter(("max", "max"))
    assert pf._dominates((10.0, 10.0), (10.0, 10.0)) is False

def test_pareto_filter_length_mismatch():
    pf = ParetoFilter(("max", "max"))
    with pytest.raises(ValueError):
        pf._dominates((10.0,), (10.0, 10.0))

def test_pareto_filter_3d_objectives():
    pf = ParetoFilter(("max", "min", "max"))
    assert pf._dominates((10.0, 2.0, 10.0), (5.0, 5.0, 5.0)) is True
    assert pf._dominates((10.0, 5.0, 5.0), (5.0, 5.0, 5.0)) is True
    assert pf._dominates((10.0, 2.0, 1.0), (5.0, 5.0, 5.0)) is False

# --- ParetoFilter filter Tests ---

def test_pareto_filter_empty_list():
    pf = ParetoFilter(("max", "max"))
    assert pf.filter([]) == []

def test_pareto_filter_single_element():
    pf = ParetoFilter(("max", "max"))
    sol = [("sol1", (10.0, 10.0))]
    assert pf.filter(sol) == sol

def test_pareto_filter_all_identical():
    pf = ParetoFilter(("max", "max"))
    sols = [
        ("sol1", (10.0, 10.0)),
        ("sol2", (10.0, 10.0)),
        ("sol3", (10.0, 10.0)),
    ]
    front = pf.filter(sols)
    assert len(front) == 3
    assert set([s[0] for s in front]) == {"sol1", "sol2", "sol3"}

def test_pareto_filter_strict_chain():
    pf = ParetoFilter(("max", "max"))
    sols = [
        ("worst", (1.0, 1.0)),
        ("mid", (5.0, 5.0)),
        ("best", (10.0, 10.0)),
    ]
    front = pf.filter(sols)
    assert len(front) == 1
    assert front[0][0] == "best"

def test_pareto_filter_true_front():
    pf = ParetoFilter(("max", "min"))
    sols = [
        ("a", (10.0, 5.0)),
        ("b", (5.0, 1.0)),
        ("c", (10.0, 10.0)),
        ("d", (1.0, 20.0)),
        ("e", (20.0, 15.0))
    ]
    front = pf.filter(sols)
    ids = {s[0] for s in front}
    assert ids == {"a", "b", "e"}

def test_pareto_filter_all_non_dominated():
    pf = ParetoFilter(("max", "max"))
    sols = [
        ("a", (10.0, 1.0)),
        ("b", (5.0, 5.0)),
        ("c", (1.0, 10.0)),
    ]
    front = pf.filter(sols)
    assert len(front) == 3

def test_pareto_filter_negative_values():
    pf = ParetoFilter(("max", "min"))
    sols = [
        ("a", (-5.0, -10.0)), # Max obj is -5, min obj is -10
        ("b", (-10.0, -20.0)), # Max is -10 (worse), min is -20 (better) -> tradeoff
        ("c", (-15.0, -5.0)), # Dominated by a
    ]
    front = pf.filter(sols)
    ids = {s[0] for s in front}
    assert ids == {"a", "b"}
