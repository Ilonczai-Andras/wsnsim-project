"""Unit tesztek — Topológia generátor és szomszédsági gráf.

Teszt osztályok
---------------
TestNode               — Node dataclass, distance_to()
TestRandomDeployment   — random_deployment() pozíció és seed
TestGridDeployment     — grid_deployment() pozíció, jitter
TestClusterDeployment  — cluster_deployment() klaszter-hozzárendelés
TestNeighborGraph      — build_neighbor_graph() él- és csomópontlogika
TestConnectivity       — connectivity_stats() metrikák
TestDeterminism        — azonos seed → azonos eredmény
"""

from __future__ import annotations

import math

import numpy as np
import networkx as nx
import pytest

from wsnsim.utils.topology import (
    Node,
    build_neighbor_graph,
    cluster_deployment,
    connectivity_stats,
    grid_deployment,
    random_deployment,
)


# ---------------------------------------------------------------------------
# Node tesztek
# ---------------------------------------------------------------------------


class TestNode:
    def test_distance_to_same_node_is_zero(self):
        n = Node(0, 10.0, 20.0)
        assert n.distance_to(n) == pytest.approx(0.0)

    def test_distance_to_known_value(self):
        a = Node(0, 0.0, 0.0)
        b = Node(1, 3.0, 4.0)
        assert a.distance_to(b) == pytest.approx(5.0)

    def test_distance_symmetric(self):
        a = Node(0, 1.0, 2.0)
        b = Node(1, 4.0, 6.0)
        assert a.distance_to(b) == pytest.approx(b.distance_to(a))

    def test_sink_flag_default_false(self):
        n = Node(0, 0.0, 0.0)
        assert not n.is_sink

    def test_sink_flag_set(self):
        n = Node(0, 0.0, 0.0, is_sink=True)
        assert n.is_sink

    def test_cluster_id_default_none(self):
        n = Node(0, 5.0, 5.0)
        assert n.cluster_id is None


# ---------------------------------------------------------------------------
# Random deployment tesztek
# ---------------------------------------------------------------------------


class TestRandomDeployment:
    def test_returns_correct_count(self):
        nodes = random_deployment(20, area_m=100.0, rng=np.random.default_rng(1))
        assert len(nodes) == 20

    def test_node_ids_sequential(self):
        nodes = random_deployment(10, area_m=50.0, rng=np.random.default_rng(1))
        assert [n.node_id for n in nodes] == list(range(10))

    def test_positions_within_area(self):
        nodes = random_deployment(50, area_m=100.0, rng=np.random.default_rng(2))
        for n in nodes:
            assert 0.0 <= n.x <= 100.0
            assert 0.0 <= n.y <= 100.0

    def test_sink_correctly_marked(self):
        nodes = random_deployment(10, area_m=100.0, sink_id=3,
                                  rng=np.random.default_rng(1))
        sinks = [n for n in nodes if n.is_sink]
        assert len(sinks) == 1
        assert sinks[0].node_id == 3

    def test_same_seed_same_positions(self):
        a = random_deployment(15, area_m=100.0, rng=np.random.default_rng(42))
        b = random_deployment(15, area_m=100.0, rng=np.random.default_rng(42))
        assert all(u.x == v.x and u.y == v.y for u, v in zip(a, b))

    def test_different_seeds_different_positions(self):
        a = random_deployment(15, area_m=100.0, rng=np.random.default_rng(1))
        b = random_deployment(15, area_m=100.0, rng=np.random.default_rng(2))
        assert any(u.x != v.x or u.y != v.y for u, v in zip(a, b))


# ---------------------------------------------------------------------------
# Grid deployment tesztek
# ---------------------------------------------------------------------------


class TestGridDeployment:
    def test_returns_rows_times_cols(self):
        nodes = grid_deployment(3, 4, spacing_m=10.0, rng=np.random.default_rng(0))
        assert len(nodes) == 12

    def test_first_node_at_origin(self):
        nodes = grid_deployment(2, 2, spacing_m=10.0, jitter_m=0.0,
                                rng=np.random.default_rng(0))
        assert nodes[0].x == pytest.approx(0.0)
        assert nodes[0].y == pytest.approx(0.0)

    def test_spacing_correct(self):
        nodes = grid_deployment(2, 3, spacing_m=15.0, jitter_m=0.0,
                                rng=np.random.default_rng(0))
        # (0,0), (15,0), (30,0), (0,15), (15,15), (30,15)
        assert nodes[1].x == pytest.approx(15.0)
        assert nodes[3].y == pytest.approx(15.0)

    def test_jitter_moves_positions(self):
        no_jitter = grid_deployment(3, 3, spacing_m=10.0, jitter_m=0.0,
                                    rng=np.random.default_rng(5))
        with_jitter = grid_deployment(3, 3, spacing_m=10.0, jitter_m=5.0,
                                      rng=np.random.default_rng(5))
        assert any(abs(a.x - b.x) > 0 or abs(a.y - b.y) > 0
                   for a, b in zip(no_jitter, with_jitter))

    def test_sink_correctly_marked(self):
        nodes = grid_deployment(3, 3, spacing_m=10.0, sink_id=4,
                                rng=np.random.default_rng(0))
        sinks = [n for n in nodes if n.is_sink]
        assert len(sinks) == 1
        assert sinks[0].node_id == 4


# ---------------------------------------------------------------------------
# Cluster deployment tesztek
# ---------------------------------------------------------------------------


class TestClusterDeployment:
    def test_returns_correct_count(self):
        nodes = cluster_deployment(20, n_clusters=3, area_m=100.0,
                                   rng=np.random.default_rng(0))
        assert len(nodes) == 20

    def test_cluster_ids_in_range(self):
        nodes = cluster_deployment(30, n_clusters=4, area_m=100.0,
                                   rng=np.random.default_rng(1))
        for n in nodes:
            assert n.cluster_id is not None
            assert 0 <= n.cluster_id < 4

    def test_positions_within_area(self):
        nodes = cluster_deployment(40, n_clusters=3, area_m=100.0,
                                   rng=np.random.default_rng(2))
        for n in nodes:
            assert 0.0 <= n.x <= 100.0
            assert 0.0 <= n.y <= 100.0

    def test_same_seed_reproducible(self):
        a = cluster_deployment(20, n_clusters=3, rng=np.random.default_rng(99))
        b = cluster_deployment(20, n_clusters=3, rng=np.random.default_rng(99))
        assert all(u.x == v.x and u.y == v.y for u, v in zip(a, b))

    def test_sink_marked(self):
        nodes = cluster_deployment(10, n_clusters=2, sink_id=0,
                                   rng=np.random.default_rng(0))
        assert nodes[0].is_sink
        assert sum(1 for n in nodes if n.is_sink) == 1


# ---------------------------------------------------------------------------
# Szomszédsági gráf tesztek
# ---------------------------------------------------------------------------


class TestNeighborGraph:
    def _two_nodes(self, dist: float) -> list[Node]:
        return [Node(0, 0.0, 0.0), Node(1, dist, 0.0)]

    def test_close_nodes_connected(self):
        G = build_neighbor_graph(self._two_nodes(10.0), range_m=15.0)
        assert G.has_edge(0, 1)

    def test_far_nodes_not_connected(self):
        G = build_neighbor_graph(self._two_nodes(20.0), range_m=15.0)
        assert not G.has_edge(0, 1)

    def test_edge_at_exact_range(self):
        G = build_neighbor_graph(self._two_nodes(15.0), range_m=15.0)
        assert G.has_edge(0, 1)

    def test_edge_distance_attribute(self):
        G = build_neighbor_graph(self._two_nodes(10.0), range_m=20.0)
        assert G[0][1]["distance"] == pytest.approx(10.0)

    def test_node_count_correct(self):
        nodes = random_deployment(10, area_m=100.0, rng=np.random.default_rng(0))
        G = build_neighbor_graph(nodes, range_m=50.0)
        assert G.number_of_nodes() == 10

    def test_node_attributes_set(self):
        nodes = [Node(0, 5.0, 5.0, is_sink=True), Node(1, 10.0, 10.0)]
        G = build_neighbor_graph(nodes, range_m=20.0)
        assert G.nodes[0]["is_sink"] is True
        assert G.nodes[0]["pos"] == (5.0, 5.0)

    def test_no_self_loops(self):
        nodes = random_deployment(10, area_m=100.0, rng=np.random.default_rng(0))
        G = build_neighbor_graph(nodes, range_m=200.0)
        assert nx.number_of_selfloops(G) == 0

    def test_graph_is_undirected(self):
        nodes = self._two_nodes(5.0)
        G = build_neighbor_graph(nodes, range_m=10.0)
        assert isinstance(G, nx.Graph)
        assert not isinstance(G, nx.DiGraph)


# ---------------------------------------------------------------------------
# Connectivity metrika tesztek
# ---------------------------------------------------------------------------


class TestConnectivity:
    def test_fully_connected_single_component(self):
        # 4 csomópont kis területen, nagy hatótáv → összefüggő
        nodes = grid_deployment(2, 2, spacing_m=10.0, rng=np.random.default_rng(0))
        G = build_neighbor_graph(nodes, range_m=20.0)
        stats = connectivity_stats(G, sink_id=0)
        assert stats["is_connected"] is True
        assert stats["n_components"] == 1

    def test_isolated_node_two_components(self):
        # 1 izolált csomópont → 2 komponens
        nodes = [Node(0, 0.0, 0.0), Node(1, 5.0, 0.0), Node(2, 500.0, 500.0)]
        G = build_neighbor_graph(nodes, range_m=10.0)
        stats = connectivity_stats(G, sink_id=0)
        assert stats["n_components"] == 2
        assert stats["is_connected"] is False

    def test_sink_reachable_count(self):
        # Két összekötött csomópont (sink + 1), egy izolált
        nodes = [Node(0, 0.0, 0.0, is_sink=True), Node(1, 5.0, 0.0),
                 Node(2, 500.0, 500.0)]
        G = build_neighbor_graph(nodes, range_m=10.0)
        stats = connectivity_stats(G, sink_id=0)
        assert stats["sink_reachable_count"] == 2  # csak 0 és 1

    def test_avg_degree_fully_connected(self):
        # 3 csomópont, mind összekötve → átlagos fokszám = 2
        nodes = [Node(0, 0.0, 0.0), Node(1, 5.0, 0.0), Node(2, 2.5, 5.0)]
        G = build_neighbor_graph(nodes, range_m=10.0)
        stats = connectivity_stats(G, sink_id=0)
        assert stats["avg_degree"] == pytest.approx(2.0)

    def test_empty_graph_safe(self):
        G = nx.Graph()
        stats = connectivity_stats(G, sink_id=0)
        assert stats["n_nodes"] == 0
        assert stats["sink_reachable_count"] == 0

    def test_n_nodes_and_edges(self):
        nodes = grid_deployment(2, 3, spacing_m=10.0, rng=np.random.default_rng(0))
        G = build_neighbor_graph(nodes, range_m=12.0)
        stats = connectivity_stats(G)
        assert stats["n_nodes"] == 6
        assert stats["n_edges"] == G.number_of_edges()
