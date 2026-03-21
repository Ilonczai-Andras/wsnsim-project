"""Unit tesztek — Routing modellek (FloodRouter, SinkTreeRouter).

Teszt osztályok
---------------
TestRoutedPacket       — RoutedPacket dataclass, hop_count
TestFloodRouterBasic   — alapvető flooding logika
TestFloodRouterTTL     — TTL lejárat és eldobás
TestFloodRouterCache   — seen-cache, duplikátum-szűrés
TestSinkTreeBasic      — sink-fa szülőhozzárendelés, path_to_sink
TestSinkTreeETX        — ETX-alapú szülőválasztás (rövidebb ETX nyeri)
TestSinkTreeIsolated   — nem elérhető csomópont kezelése
"""

from __future__ import annotations

import math

import networkx as nx
import numpy as np
import pytest

from wsnsim.models.routing import FloodRouter, RoutedPacket, SinkTreeRouter, _etx
from wsnsim.utils.topology import build_neighbor_graph, grid_deployment, Node


# ---------------------------------------------------------------------------
# Segédfüggvények
# ---------------------------------------------------------------------------


def linear_graph(n: int, spacing: float = 10.0, range_m: float = 12.0) -> nx.Graph:
    """n csomópont lineárisan (0-1-2-...) range_m hatótávval."""
    nodes = [Node(i, float(i) * spacing, 0.0) for i in range(n)]
    return build_neighbor_graph(nodes, range_m=range_m)


def star_graph(n_leaves: int, r: float = 10.0) -> nx.Graph:
    """Csillag: 0 a sink, 1..n_leaves levelek, r hatótáv."""
    nodes = [Node(0, 0.0, 0.0)]
    for i in range(1, n_leaves + 1):
        nodes.append(Node(i, r * 0.9, 0.0))  # biztosan belül r-en
    return build_neighbor_graph(nodes, range_m=r)


# ---------------------------------------------------------------------------
# RoutedPacket tesztek
# ---------------------------------------------------------------------------


class TestRoutedPacket:
    def test_hop_count_empty_hops(self):
        p = RoutedPacket(packet_id=1, src=0, dst=0)
        assert p.hop_count == 0

    def test_hop_count_direct(self):
        p = RoutedPacket(packet_id=1, src=1, dst=0, hops=[1, 0])
        assert p.hop_count == 1

    def test_hop_count_three_hop(self):
        p = RoutedPacket(packet_id=1, src=3, dst=0, hops=[3, 2, 1, 0])
        assert p.hop_count == 3

    def test_delivered_and_dropped_default_false(self):
        p = RoutedPacket(packet_id=1, src=1, dst=0)
        assert not p.delivered
        assert not p.dropped
        assert p.drop_reason is None


# ---------------------------------------------------------------------------
# FloodRouter alapvető tesztek
# ---------------------------------------------------------------------------


class TestFloodRouterBasic:
    def test_direct_neighbor_delivered(self):
        """Közvetlen szomszéd 1 ugrással eléri a sink-et."""
        G = star_graph(3)
        router = FloodRouter(G, sink_id=0, default_ttl=5)
        delivered = router.inject(packet_id=1, src=1)
        assert len(delivered) == 1
        assert delivered[0].delivered
        assert delivered[0].hop_count == 1

    def test_linear_delivery_two_hops(self):
        """Lineáris gráfon 0-1-2: 2-es csomópont 2 ugrással éri el a sink-et."""
        G = linear_graph(3)
        router = FloodRouter(G, sink_id=0, default_ttl=5)
        delivered = router.inject(packet_id=1, src=2)
        assert len(delivered) == 1
        assert delivered[0].hop_count == 2
        assert delivered[0].hops == [2, 1, 0]

    def test_pdr_all_delivered(self):
        G = star_graph(4)
        router = FloodRouter(G, sink_id=0, default_ttl=5)
        for i in range(1, 5):
            router.inject(packet_id=i, src=i)
        assert router.pdr() == pytest.approx(1.0)

    def test_avg_hop_count(self):
        """Lineáris 5-csomópontos gráfon: avg hop = (1+2+3+4)/4 = 2.5."""
        G = linear_graph(5)
        router = FloodRouter(G, sink_id=0, default_ttl=10)
        for i in range(1, 5):
            router.inject(packet_id=i, src=i)
        assert router.avg_hop_count() == pytest.approx(2.5)

    def test_path_recorded_in_hops(self):
        G = linear_graph(4)
        router = FloodRouter(G, sink_id=0, default_ttl=10)
        delivered = router.inject(packet_id=1, src=3)
        assert delivered[0].hops[0] == 3
        assert delivered[0].hops[-1] == 0


# ---------------------------------------------------------------------------
# FloodRouter TTL tesztek
# ---------------------------------------------------------------------------


class TestFloodRouterTTL:
    def test_ttl_zero_drops_immediately(self):
        """TTL=0 esetén a csomag azonnal eldobódik (nem éri el senkihez)."""
        G = linear_graph(3)
        router = FloodRouter(G, sink_id=0, default_ttl=0)
        delivered = router.inject(packet_id=1, src=2, ttl=0)
        assert len(delivered) == 0
        assert len(router.dropped_packets) > 0

    def test_ttl_too_small_drops(self):
        """TTL=1 elég a közvetlen szomszédhoz, de nem 2 ugráshoz."""
        G = linear_graph(3)  # 2→1→0, 2 ugrás kell
        router = FloodRouter(G, sink_id=0, default_ttl=1)
        delivered = router.inject(packet_id=1, src=2, ttl=1)
        assert len(delivered) == 0

    def test_ttl_exact_reaches_sink(self):
        """Pontosan elegendő TTL esetén a csomag megérkezik."""
        G = linear_graph(3)  # 2→1→0, TTL=2 pontosan elég
        router = FloodRouter(G, sink_id=0, default_ttl=2)
        delivered = router.inject(packet_id=1, src=2, ttl=2)
        assert len(delivered) == 1

    def test_drop_reason_ttl(self):
        G = linear_graph(3)
        router = FloodRouter(G, sink_id=0)
        router.inject(packet_id=1, src=2, ttl=1)
        drops = router.dropped_packets
        assert any(d.drop_reason == "TTL=0" for d in drops)


# ---------------------------------------------------------------------------
# FloodRouter seen-cache tesztek
# ---------------------------------------------------------------------------


class TestFloodRouterCache:
    def test_same_packet_not_reinjected(self):
        """Ugyanazt a packet_id-t megismételve a seen-cache blokkolja."""
        G = star_graph(2)
        router = FloodRouter(G, sink_id=0, default_ttl=5)
        d1 = router.inject(packet_id=42, src=1)
        d2 = router.inject(packet_id=42, src=2)  # cache-ban van már node 0
        # A másodszori inject nem ad új kézbesítést ugyanazon packet_id-ra
        assert len(d2) == 0

    def test_different_packet_ids_both_delivered(self):
        """Különböző packet_id-k egymástól függetlenül terjednek."""
        G = star_graph(2)
        router = FloodRouter(G, sink_id=0, default_ttl=5)
        d1 = router.inject(packet_id=1, src=1)
        d2 = router.inject(packet_id=2, src=2)
        assert len(d1) == 1
        assert len(d2) == 1

    def test_reset_clears_cache(self):
        """Reset után ugyanaz a packet_id újra kézbesíthető."""
        G = star_graph(1)
        router = FloodRouter(G, sink_id=0, default_ttl=5)
        router.inject(packet_id=99, src=1)
        router.reset()
        delivered = router.inject(packet_id=99, src=1)
        assert len(delivered) == 1


# ---------------------------------------------------------------------------
# SinkTreeRouter alapvető tesztek
# ---------------------------------------------------------------------------


class TestSinkTreeBasic:
    def test_direct_neighbor_parent_is_sink(self):
        """Közvetlen szomszéd szülője maga a sink."""
        G = star_graph(3)
        router = SinkTreeRouter(G, sink_id=0)
        assert router.parent_of(1) == 0
        assert router.parent_of(2) == 0

    def test_path_to_sink_direct(self):
        G = star_graph(1)
        router = SinkTreeRouter(G, sink_id=0)
        assert router.path_to_sink(1) == [1, 0]

    def test_path_to_sink_linear(self):
        """Lineáris gráfon a legrövidebb út [n, n-1, ..., 0]."""
        G = linear_graph(4)
        router = SinkTreeRouter(G, sink_id=0)
        path = router.path_to_sink(3)
        assert path[0] == 3
        assert path[-1] == 0
        assert len(path) == 4  # 3→2→1→0

    def test_route_returns_delivered(self):
        G = star_graph(3)
        router = SinkTreeRouter(G, sink_id=0)
        pkt = router.route(packet_id=1, src=2)
        assert pkt.delivered
        assert not pkt.dropped

    def test_sink_path_to_itself_single_node(self):
        G = nx.Graph()
        G.add_node(0)
        router = SinkTreeRouter(G, sink_id=0)
        assert router.path_to_sink(0) == [0]

    def test_all_reachable_linear(self):
        G = linear_graph(5)
        router = SinkTreeRouter(G, sink_id=0)
        reachable = router.all_reachable()
        assert set(reachable) == {1, 2, 3, 4}

    def test_tree_edges_count(self):
        """Sink-fának n-1 éle van összefüggő gráfon."""
        G = linear_graph(5)
        router = SinkTreeRouter(G, sink_id=0)
        edges = router.tree_edges()
        assert len(edges) == 4  # 5 csomópont → 4 él


# ---------------------------------------------------------------------------
# SinkTreeRouter ETX tesztek
# ---------------------------------------------------------------------------


class TestSinkTreeETX:
    def test_etx_formula(self):
        assert _etx(1.0) == pytest.approx(1.0)
        assert _etx(0.5) == pytest.approx(2.0)
        assert _etx(0.0) == float("inf")

    def test_higher_prr_edge_preferred(self):
        """Ha két szomszéd közül egyiknek magasabb PRR-je van, azt választja."""
        # 0=sink, 1 és 2 egyaránt szomszéd, 3 csak 1-en és 2-n keresztül érhető el
        # 1→0: prr=0.9, 2→0: prr=0.5 → 3-nak az 1-es szülő a jobb
        G = nx.Graph()
        G.add_node(0); G.add_node(1); G.add_node(2); G.add_node(3)
        G.add_edge(1, 0, distance=5.0, prr=0.9)
        G.add_edge(2, 0, distance=5.0, prr=0.5)
        G.add_edge(3, 1, distance=5.0, prr=0.95)
        G.add_edge(3, 2, distance=5.0, prr=0.95)
        router = SinkTreeRouter(G, sink_id=0)
        # 3 szülője 1 legyen (alacsonyabb össz-ETX)
        assert router.parent_of(3) == 1

    def test_etx_to_sink_two_hops(self):
        """Két ugrásos lint ETX = etx(link1) + etx(link2)."""
        G = nx.Graph()
        G.add_node(0); G.add_node(1); G.add_node(2)
        G.add_edge(0, 1, distance=1.0, prr=0.8)  # etx = 1.25
        G.add_edge(1, 2, distance=1.0, prr=0.5)  # etx = 2.0
        router = SinkTreeRouter(G, sink_id=0)
        expected = 1.25 + 2.0
        assert router.etx_to_sink(2) == pytest.approx(expected, rel=1e-6)


# ---------------------------------------------------------------------------
# SinkTreeRouter izolált csomópont tesztek
# ---------------------------------------------------------------------------


class TestSinkTreeIsolated:
    def test_isolated_node_no_path(self):
        """Izolált csomópontnak nincs útja a sinkhez."""
        G = nx.Graph()
        G.add_node(0)
        G.add_node(1)  # nincs él
        router = SinkTreeRouter(G, sink_id=0)
        assert router.path_to_sink(1) == []

    def test_isolated_node_route_dropped(self):
        G = nx.Graph()
        G.add_node(0); G.add_node(1)
        router = SinkTreeRouter(G, sink_id=0)
        pkt = router.route(packet_id=1, src=1)
        assert pkt.dropped
        assert pkt.drop_reason == "no_route"

    def test_isolated_not_in_reachable(self):
        G = nx.Graph()
        G.add_node(0); G.add_node(1); G.add_node(2)
        G.add_edge(1, 0, distance=5.0)
        # 2 izolált
        router = SinkTreeRouter(G, sink_id=0)
        assert 2 not in router.all_reachable()
        assert 1 in router.all_reachable()
