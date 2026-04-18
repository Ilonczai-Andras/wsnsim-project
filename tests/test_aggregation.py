"""Unit tesztek a wsnsim.models.aggregation modulhoz.

Teszteli az AggResult dataclass-t, a RawForwarder-t és a TreeAggregator-t,
beleértve a delta-kódolást és az MSE/MAE metrikákat.

Fix tesztopológia minden tesztosztályhoz:
    5-csomópontos lánc: 0=sink, 1→0, 2→1, 3→2, 4→3
    prr=1.0 minden élen (ETX=1.0, determinisztikus routing)
"""

from __future__ import annotations

import numpy as np
import networkx as nx
import pytest

from wsnsim.models.routing import SinkTreeRouter
from wsnsim.models.aggregation import AggResult, RawForwarder, TreeAggregator


# ---------------------------------------------------------------------------
# Közös fixture: 5-csomópontos lánc topológia
# ---------------------------------------------------------------------------

def _make_chain_router() -> SinkTreeRouter:
    """5-csomópontos lánc: 0=sink, 1→0, 2→1, 3→2, 4→3."""
    G = nx.Graph()
    G.add_edge(0, 1, prr=1.0)
    G.add_edge(1, 2, prr=1.0)
    G.add_edge(2, 3, prr=1.0)
    G.add_edge(3, 4, prr=1.0)
    return SinkTreeRouter(G, sink_id=0)


# Osztott router (minden teszt újrainicializálja, ahol fontos)
CHAIN_ROUTER = _make_chain_router()

# Alap readings: eltérő értékek minden csomóponton
READINGS_5 = {0: 20.0, 1: 22.0, 2: 24.0, 3: 26.0, 4: 28.0}

# Egyforma readings a delta-teszteléshez
READINGS_FLAT = {0: 25.0, 1: 25.0, 2: 25.0, 3: 25.0, 4: 25.0}

RNG = np.random.default_rng(0)


# ---------------------------------------------------------------------------
# TestAggResultCreation
# ---------------------------------------------------------------------------

class TestAggResultCreation:
    """AggResult dataclass közvetlen létrehozása és mezőellenőrzés."""

    def test_fields_raw(self) -> None:
        """Minden mező helyesen tárolódik 'raw' stratégiánál."""
        r = AggResult(
            strategy="raw",
            messages_sent=10,
            bytes_sent=200,
            delivered_values=[1.0, 2.0, 3.0],
            ground_truth=[1.0, 2.0, 3.0],
            mse=0.0,
            mae=0.0,
        )
        assert r.strategy == "raw"
        assert r.messages_sent == 10
        assert r.bytes_sent == 200
        assert r.delivered_values == [1.0, 2.0, 3.0]
        assert r.ground_truth == [1.0, 2.0, 3.0]
        assert r.mse == 0.0
        assert r.mae == 0.0

    def test_fields_tree(self) -> None:
        """Minden mező helyesen tárolódik 'tree_avg_delta' stratégiánál."""
        r = AggResult(
            strategy="tree_avg_delta",
            messages_sent=4,
            bytes_sent=80,
            delivered_values=[24.0],
            ground_truth=[20.0, 22.0, 24.0, 26.0, 28.0],
            mse=1.0,
            mae=1.0,
        )
        assert r.strategy == "tree_avg_delta"
        assert r.messages_sent == 4
        assert r.delivered_values == [24.0]
        assert len(r.ground_truth) == 5

    def test_mse_mae_direct(self) -> None:
        """mse és mae közvetlenül beállítható, nem automatikus a dataclass-ban."""
        r = AggResult(
            strategy="raw",
            messages_sent=0,
            bytes_sent=0,
            delivered_values=[],
            ground_truth=[],
            mse=3.14,
            mae=1.77,
        )
        assert r.mse == pytest.approx(3.14)
        assert r.mae == pytest.approx(1.77)


# ---------------------------------------------------------------------------
# TestRawForwarderBasic
# ---------------------------------------------------------------------------

class TestRawForwarderBasic:
    """RawForwarder alapvető működés: hop-count, delivered_values, bytes."""

    def test_messages_sent_chain(self) -> None:
        """5-csomópontos láncon messages_sent = 4+3+2+1+0 = 10."""
        fwd = RawForwarder(CHAIN_ROUTER)
        result = fwd.run(READINGS_5, RNG)
        assert result.messages_sent == 10

    def test_delivered_values_length(self) -> None:
        """delivered_values hossza = a readings csomópontjainak száma."""
        fwd = RawForwarder(CHAIN_ROUTER)
        result = fwd.run(READINGS_5, RNG)
        assert len(result.delivered_values) == len(READINGS_5)

    def test_delivered_values_content(self) -> None:
        """delivered_values tartalmazza az összes eredeti mérési értéket."""
        fwd = RawForwarder(CHAIN_ROUTER)
        result = fwd.run(READINGS_5, RNG)
        assert sorted(result.delivered_values) == pytest.approx(
            sorted(READINGS_5.values())
        )

    def test_bytes_sent(self) -> None:
        """bytes_sent = messages_sent × packet_size_bytes."""
        fwd = RawForwarder(CHAIN_ROUTER, packet_size_bytes=20)
        result = fwd.run(READINGS_5, RNG)
        assert result.bytes_sent == result.messages_sent * 20


# ---------------------------------------------------------------------------
# TestRawForwarderReproducibility
# ---------------------------------------------------------------------------

class TestRawForwarderReproducibility:
    """RawForwarder determinizmus: azonos seed → azonos eredmény."""

    def test_same_seed_same_result(self) -> None:
        """Azonos readings → azonos messages_sent és delivered_values."""
        fwd1 = RawForwarder(CHAIN_ROUTER)
        fwd2 = RawForwarder(CHAIN_ROUTER)
        r1 = fwd1.run(READINGS_5, np.random.default_rng(1))
        r2 = fwd2.run(READINGS_5, np.random.default_rng(1))
        assert r1.messages_sent == r2.messages_sent
        assert r1.delivered_values == r2.delivered_values

    def test_different_rng_same_result(self) -> None:
        """RawForwarder nem használja az rng-t → különböző seed → azonos eredmény."""
        fwd = RawForwarder(CHAIN_ROUTER)
        r1 = fwd.run(READINGS_5, np.random.default_rng(99))
        r2 = fwd.run(READINGS_5, np.random.default_rng(0))
        assert r1.messages_sent == r2.messages_sent
        assert r1.delivered_values == r2.delivered_values


# ---------------------------------------------------------------------------
# TestTreeAggregatorBasic
# ---------------------------------------------------------------------------

class TestTreeAggregatorBasic:
    """TreeAggregator alapvető működés: aggregáció, delivered_values, bytes."""

    def test_messages_sent_n_minus_1(self) -> None:
        """5-csomópontos láncon messages_sent = N-1 = 4 (threshold_delta=0.0)."""
        tree = TreeAggregator(_make_chain_router(), threshold_delta=0.0)
        result = tree.run(READINGS_5, RNG)
        assert result.messages_sent == 4

    def test_delivered_values_length_is_one(self) -> None:
        """Fa-aggregációnál a sink egyetlen aggregált értéket kap."""
        tree = TreeAggregator(_make_chain_router(), threshold_delta=0.0)
        result = tree.run(READINGS_5, RNG)
        assert len(result.delivered_values) == 1

    def test_delivered_value_is_float(self) -> None:
        """A sink által kapott aggregált érték lebegőpontos szám."""
        tree = TreeAggregator(_make_chain_router(), threshold_delta=0.0)
        result = tree.run(READINGS_5, RNG)
        assert isinstance(result.delivered_values[0], float)

    def test_messages_less_than_raw(self) -> None:
        """TreeAggregator messages_sent < RawForwarder messages_sent."""
        fwd = RawForwarder(CHAIN_ROUTER)
        tree = TreeAggregator(_make_chain_router(), threshold_delta=0.0)
        raw_result = fwd.run(READINGS_5, RNG)
        tree_result = tree.run(READINGS_5, RNG)
        assert tree_result.messages_sent < raw_result.messages_sent

    def test_bytes_sent(self) -> None:
        """bytes_sent = messages_sent × packet_size_bytes."""
        tree = TreeAggregator(_make_chain_router(), packet_size_bytes=20, threshold_delta=0.0)
        result = tree.run(READINGS_5, RNG)
        assert result.bytes_sent == result.messages_sent * 20


# ---------------------------------------------------------------------------
# TestTreeAggregatorDeltaCoding
# ---------------------------------------------------------------------------

class TestTreeAggregatorDeltaCoding:
    """Delta-kódolás: 2. futásban 0 üzenet azonos readings esetén."""

    def test_delta_first_run_sends_all(self) -> None:
        """1. futásban (prev=None) minden csomópont küld → messages_sent = 4."""
        tree = TreeAggregator(_make_chain_router(), threshold_delta=1.0)
        r1 = tree.run(READINGS_FLAT, RNG)
        assert r1.messages_sent == 4  # N-1 = 4, minden csomópont küld

    def test_delta_second_run_zero_messages(self) -> None:
        """2. futásban azonos (flat) readings → 0 üzenet (delta suppressed)."""
        tree = TreeAggregator(_make_chain_router(), threshold_delta=1.0)
        tree.run(READINGS_FLAT, RNG)               # 1. futás
        r2 = tree.run(READINGS_FLAT, RNG)           # 2. futás
        assert r2.messages_sent == 0

    def test_delta_zero_always_sends(self) -> None:
        """threshold_delta=0.0 esetén a 2. futásban is minden csomópont küld."""
        tree = TreeAggregator(_make_chain_router(), threshold_delta=0.0)
        tree.run(READINGS_FLAT, RNG)               # 1. futás
        r2 = tree.run(READINGS_FLAT, RNG)           # 2. futás
        assert r2.messages_sent == 4

    def test_delta_reduces_messages_across_runs(self) -> None:
        """threshold_delta=1.0: 2. futás messages_sent < 1. futás messages_sent."""
        tree = TreeAggregator(_make_chain_router(), threshold_delta=1.0)
        r1 = tree.run(READINGS_FLAT, RNG)
        r2 = tree.run(READINGS_FLAT, RNG)
        assert r2.messages_sent < r1.messages_sent

    def test_delta_strategy_label(self) -> None:
        """A stratégia neve 'tree_avg_delta'."""
        tree = TreeAggregator(_make_chain_router(), threshold_delta=1.0)
        result = tree.run(READINGS_5, RNG)
        assert result.strategy == "tree_avg_delta"


# ---------------------------------------------------------------------------
# TestAggComparisonMSE
# ---------------------------------------------------------------------------

class TestAggComparisonMSE:
    """MSE/MAE összehasonlítás RawForwarder vs TreeAggregator."""

    def test_raw_mse_zero(self) -> None:
        """RawForwarder.mse == 0.0: delivered_values == ground_truth (nincs aggregációs hiba)."""
        fwd = RawForwarder(CHAIN_ROUTER)
        result = fwd.run(READINGS_5, RNG)
        assert result.mse == pytest.approx(0.0, abs=1e-12)

    def test_raw_mae_zero(self) -> None:
        """RawForwarder.mae == 0.0: mean(delivered) == mean(ground_truth)."""
        fwd = RawForwarder(CHAIN_ROUTER)
        result = fwd.run(READINGS_5, RNG)
        assert result.mae == pytest.approx(0.0, abs=1e-12)

    def test_tree_mse_nonnegative(self) -> None:
        """TreeAggregator.mse >= 0.0 (nem negatív)."""
        tree = TreeAggregator(_make_chain_router(), threshold_delta=0.0)
        result = tree.run(READINGS_5, RNG)
        assert result.mse >= 0.0

    def test_tree_messages_less_than_raw(self) -> None:
        """TreeAggregator messages_sent < RawForwarder messages_sent (láncon)."""
        fwd = RawForwarder(CHAIN_ROUTER)
        tree = TreeAggregator(_make_chain_router(), threshold_delta=0.0)
        raw_r = fwd.run(READINGS_5, RNG)
        tree_r = tree.run(READINGS_5, RNG)
        assert tree_r.messages_sent < raw_r.messages_sent

    def test_raw_strategy_label(self) -> None:
        """RawForwarder.strategy == 'raw'."""
        fwd = RawForwarder(CHAIN_ROUTER)
        result = fwd.run(READINGS_5, RNG)
        assert result.strategy == "raw"

    def test_tree_strategy_label(self) -> None:
        """TreeAggregator.strategy == 'tree_avg_delta'."""
        tree = TreeAggregator(_make_chain_router(), threshold_delta=0.0)
        result = tree.run(READINGS_5, RNG)
        assert result.strategy == "tree_avg_delta"
