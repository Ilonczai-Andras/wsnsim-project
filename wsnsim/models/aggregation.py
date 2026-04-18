"""Adataggregáció és tömörítés modellek.

Két stratégia érhető el:

* **RawForwarder** — Nyers adat továbbítás: minden csomópont az eredeti mérési
  értékét hop-by-hop elküldi a sinkig (path_to_sink() útvonalon). Nincs
  aggregáció, nincs tömörítés. Kommunikációs költség: N csomag × hop_count ugr.

* **TreeAggregator** — Fa menti AVG aggregáció delta-kódolással: levéltől a sink
  felé haladva minden közbenső csomópont átlagolja a gyerekektől kapott értékeket
  a saját mérésével. Delta-kódolás: csak akkor küld, ha az aggregált érték
  változása meghaladja a ``threshold_delta`` küszöböt. Kommunikációs megtakarítás:
  legfeljebb N-1 üzenet (fa élei mentén), nem N × hop.

Példa::

    import numpy as np
    import networkx as nx
    from wsnsim.models.routing import SinkTreeRouter
    from wsnsim.models.aggregation import RawForwarder, TreeAggregator

    G = nx.Graph()
    G.add_edge(0, 1, prr=1.0)
    G.add_edge(1, 2, prr=1.0)
    router = SinkTreeRouter(G, sink_id=0)
    rng = np.random.default_rng(42)

    raw = RawForwarder(router)
    result = raw.run({0: 22.0, 1: 24.0, 2: 26.0}, rng)
    print(result.messages_sent, result.mse)

    tree = TreeAggregator(router, threshold_delta=1.0)
    r1 = tree.run({0: 22.0, 1: 24.0, 2: 26.0}, rng)
    r2 = tree.run({0: 22.0, 1: 24.0, 2: 26.0}, rng)  # 0 messages (delta suppressed)
    print(r1.messages_sent, r2.messages_sent)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from wsnsim.models.routing import SinkTreeRouter


# ---------------------------------------------------------------------------
# AggResult — aggregációs futás eredménye
# ---------------------------------------------------------------------------


@dataclass
class AggResult:
    """Egy aggregációs futás eredménye.

    Attributes
    ----------
    strategy:
        A stratégia neve: ``"raw"`` vagy ``"tree_avg_delta"``.
    messages_sent:
        Az összes elküldött üzenet száma (kommunikációs cost).
    bytes_sent:
        Az összes elküldött bájtok száma.
    delivered_values:
        A sinknél megérkezett (aggregált) értékek listája.
    ground_truth:
        Az összes csomópont eredeti mérése.
    mse:
        Mean Squared Error: az aggregált becslés vs. a ground_truth átlagának
        négyzetgyöke. ``(mean(delivered) - mean(ground_truth))²``.
    mae:
        Mean Absolute Error: ``|mean(delivered) - mean(ground_truth)|``.
    """

    strategy: str
    messages_sent: int
    bytes_sent: int
    delivered_values: list[float]
    ground_truth: list[float]
    mse: float
    mae: float


# ---------------------------------------------------------------------------
# RawForwarder — nyers adat hop-by-hop továbbítás
# ---------------------------------------------------------------------------


class RawForwarder:
    """Nyers adat továbbítási stratégia.

    Minden csomópont az eredeti mérési értékét hop-by-hop elküldi a sinkig
    a ``SinkTreeRouter.path_to_sink()`` által meghatározott útvonalon.
    Nincs in-network aggregáció. Kommunikációs költség: ∑ hop_count(i) az
    összes i csomópontra.

    Parameters
    ----------
    router:
        A topológia sink-fa routere.
    packet_size_bytes:
        Egy csomag mérete bájtban (alapértelmezett: 20).
    """

    def __init__(
        self,
        router: SinkTreeRouter,
        packet_size_bytes: int = 20,
    ) -> None:
        self._router = router
        self._packet_size_bytes = packet_size_bytes

    def run(
        self,
        readings: dict[int, float],
        rng: np.random.Generator,
    ) -> AggResult:
        """Egy aggregációs kör szimulálása nyers továbbítással.

        Minden csomóponthoz kövesse a ``path_to_sink()`` utat; minden ugrásnál
        ``messages_sent`` +1, a csomópontok eredeti értékei kerülnek a
        ``delivered_values`` listába.

        Parameters
        ----------
        readings:
            ``{node_id: measured_value}`` leképezés.
        rng:
            Véletlenszám-generátor (interfész-kompatibilitásból; nem használt).

        Returns
        -------
        AggResult
            Az aggregációs kör eredménye (``mse``, ``mae`` automatikusan számítva).
        """
        messages_sent = 0
        delivered_values: list[float] = []
        ground_truth: list[float] = list(readings.values())

        for node_id, value in readings.items():
            path = self._router.path_to_sink(node_id)
            hop_count = max(0, len(path) - 1)
            messages_sent += hop_count
            delivered_values.append(value)

        bytes_sent = messages_sent * self._packet_size_bytes

        gt_mean = sum(ground_truth) / len(ground_truth) if ground_truth else 0.0
        dv_mean = sum(delivered_values) / len(delivered_values) if delivered_values else 0.0
        mse = (dv_mean - gt_mean) ** 2
        mae = abs(dv_mean - gt_mean)

        return AggResult(
            strategy="raw",
            messages_sent=messages_sent,
            bytes_sent=bytes_sent,
            delivered_values=delivered_values,
            ground_truth=ground_truth,
            mse=mse,
            mae=mae,
        )


# ---------------------------------------------------------------------------
# TreeAggregator — fa menti AVG + delta-kódolás
# ---------------------------------------------------------------------------


class TreeAggregator:
    """Fa menti AVG aggregáció delta-kódolással.

    Levél-csomópontoktól a sink felé haladva post-order bejárással minden
    közbenső csomópont átlagolja a gyerekeitől kapott aggregált értékeket
    a saját mérésével. Delta-kódolás: csak akkor küld, ha az aggregált
    érték változása meghaladja a ``threshold_delta`` küszöböt az előző
    elküldött értékhez képest. Az első hívásban (``prev_value`` üres)
    minden csomópont küld.

    A ``prev_value`` dict a ``TreeAggregator`` példányon belül perzisztens,
    így egymást követő ``run()`` hívások között megőrzi az előző állapotot.

    Parameters
    ----------
    router:
        A topológia sink-fa routere.
    packet_size_bytes:
        Egy csomag mérete bájtban (alapértelmezett: 20).
    threshold_delta:
        Delta-kódolás küszöbértéke. Ha 0.0 (alapértelmezett), mindig küld.
        Ha > 0, csak akkor küld, ha ``|új_érték - előző_érték| >= threshold_delta``.
    """

    def __init__(
        self,
        router: SinkTreeRouter,
        packet_size_bytes: int = 20,
        threshold_delta: float = 0.0,
    ) -> None:
        self._router = router
        self._packet_size_bytes = packet_size_bytes
        self._threshold_delta = threshold_delta
        self._prev_value: dict[int, float] = {}

    def run(
        self,
        readings: dict[int, float],
        rng: np.random.Generator,
    ) -> AggResult:
        """Egy aggregációs kör szimulálása fa-aggregációval és delta-kódolással.

        Post-order bejárással (levelektől a sink felé) minden csomópont
        összegyűjti a gyerekeitől kapott aggregált értékeket, átlagolja a
        saját mérésével, majd delta-kódolással dönt a küldésről.

        Parameters
        ----------
        readings:
            ``{node_id: measured_value}`` leképezés.
        rng:
            Véletlenszám-generátor (interfész-kompatibilitásból; nem használt).

        Returns
        -------
        AggResult
            Az aggregációs kör eredménye (``mse``, ``mae`` automatikusan számítva).
        """
        nodes = list(readings.keys())
        sink = self._router.sink_id

        # Gyermek-leképezés felépítése
        children: dict[int, list[int]] = {n: [] for n in nodes}
        for n in nodes:
            p = self._router.parent_of(n)
            if p is not None and p in readings:
                children[p].append(n)

        # Post-order iteratív DFS (levelektől a sink felé)
        order: list[int] = []
        visited: set[int] = set()
        start = sink if sink in nodes else (nodes[0] if nodes else None)

        if start is not None:
            stack: list[tuple[int, bool]] = [(start, False)]
            while stack:
                node, processed = stack.pop()
                if processed:
                    order.append(node)
                    continue
                if node in visited:
                    continue
                visited.add(node)
                stack.append((node, True))
                for child in reversed(children.get(node, [])):
                    if child not in visited:
                        stack.append((child, False))

        # Csomópontok feldolgozása post-order sorrendben
        agg_value: dict[int, float] = {}
        messages_sent = 0
        bytes_sent = 0
        delivered_values: list[float] = []

        for node in order:
            # Saját mérés + gyerekektől kapott aggregált értékek
            vals: list[float] = [readings[node]]
            for child in children.get(node, []):
                if child in agg_value:
                    vals.append(agg_value[child])
            avg = sum(vals) / len(vals)

            if node == sink:
                # A sink a végeredményt tárolja, nem küld senkinek
                delivered_values.append(avg)
            else:
                prev = self._prev_value.get(node)
                if prev is None or abs(avg - prev) >= self._threshold_delta:
                    self._prev_value[node] = avg
                    agg_value[node] = avg
                    messages_sent += 1
                    bytes_sent += self._packet_size_bytes

        ground_truth = list(readings.values())
        gt_mean = sum(ground_truth) / len(ground_truth) if ground_truth else 0.0
        dv_mean = sum(delivered_values) / len(delivered_values) if delivered_values else 0.0
        mse = (dv_mean - gt_mean) ** 2
        mae = abs(dv_mean - gt_mean)

        return AggResult(
            strategy="tree_avg_delta",
            messages_sent=messages_sent,
            bytes_sent=bytes_sent,
            delivered_values=delivered_values,
            ground_truth=ground_truth,
            mse=mse,
            mae=mae,
        )
