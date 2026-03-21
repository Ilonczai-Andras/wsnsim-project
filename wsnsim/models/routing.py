"""Routing modellek: Flooding és Sink-fa (BFS/ETX-alapú).

Két routing stratégia érhető el:

* **FloodRouter** — Pure flooding TTL-lel és seen-cache-szel a végtelen
  hurkok elkerülésére. Minden csomópont, amely először lát egy csomagot,
  továbbküldi az összes szomszédjának (TTL-csökkentéssel). A seen-cache
  biztosítja, hogy ugyanazt a csomagot ne küldjük el kétszer.

* **SinkTreeRouter** — Statikus sink-fa BFS alapon, ETX-szerű szülő-
  választással. Az ETX (Expected Transmissions) metrika a PRR reciproka
  (ETX = 1/PRR), és az egyes csomópontok ahhoz a szomszédjukhoz irányítják
  a forgalmat, amelyen keresztül minimális az összesített ETX a sinkig.
  Az útvonal felépítése egyszeri, statikus (nincs dinamikus újraszámolás —
  ez dokumentált korlát).

Fontos modellezési döntések
---------------------------
* A tényleges rádiós adás (fizika réteg) **nem** része ennek a modulnak —
  azt a ``LogDistanceChannel`` és a MAC réteg kezeli. Ez a modul csak a
  routing logikát (következő ugrás, hop-count, útvonal) modellezi.
* Az energia-fogyasztás számítása a ``EnergyModel``-el elvégezhető, de az
  integráció a kísérleti scriptekben történik.
* Egyszerűsítés: a sink-fa statikus; link-hiba esetén nincs újraszámolás
  (a generált útvonal a gráf-topológiát tükrözi).

Példa::

    import numpy as np
    import networkx as nx
    from wsnsim.utils.topology import grid_deployment, build_neighbor_graph
    from wsnsim.models.routing import SinkTreeRouter, FloodRouter

    nodes = grid_deployment(3, 3, spacing_m=20.0, rng=np.random.default_rng(0))
    G = build_neighbor_graph(nodes, range_m=25.0)
    router = SinkTreeRouter(G, sink_id=0)
    path = router.path_to_sink(8)   # pl. [8, 5, 2, 1, 0]
    print(path)
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import networkx as nx


# ---------------------------------------------------------------------------
# RoutedPacket — routing szintű csomag-leíró
# ---------------------------------------------------------------------------


@dataclass
class RoutedPacket:
    """Egy routing szintű csomag állapota és statisztikái.

    A ``Packet`` dataclass fizikai-szintű metaadatokat tárol; a
    ``RoutedPacket`` ezzel szemben a routing réteget érintő információkat
    rögzíti (hop-count, útvonal, TTL, eldobás oka).

    Attributes
    ----------
    packet_id:    Egyedi azonosító (megegyezhet a Packet.packet_id-val).
    src:          Forrás csomópont azonosítója.
    dst:          Cél csomópont azonosítója (sink).
    ttl:          Hátralévő ugrások száma (flooding esetén csökken).
    hops:         Megtett ugrások listája (forrástól a célig).
    delivered:    Igaz, ha a csomag elérte a sink-et.
    dropped:      Igaz, ha a csomag eldobásra került (TTL=0 vagy nincs út).
    drop_reason:  Az eldobás oka szövegesen (None = nem dobták el).
    """

    packet_id: int
    src: int
    dst: int
    ttl: int = 16
    hops: list[int] = field(default_factory=list)
    delivered: bool = False
    dropped: bool = False
    drop_reason: Optional[str] = None

    @property
    def hop_count(self) -> int:
        """Megtett ugrások száma (a hops lista hossza mínusz 1)."""
        return max(0, len(self.hops) - 1)

    @property
    def energy_per_hop_factor(self) -> float:
        """Hop-count, amit az energia/bit számításban multiplierként használunk."""
        return float(self.hop_count)


# ---------------------------------------------------------------------------
# FloodRouter — flooding TTL-lel és seen-cache-szel
# ---------------------------------------------------------------------------


class FloodRouter:
    """Pure flooding routing TTL-lel és seen-cache-szel.

    Minden csomópont, amely elsőként kap egy adott ``packet_id``-jű
    csomagot, azt továbbküldi az összes szomszédjának (TTL-csökkentéssel).
    Ha a TTL eléri a nullát, vagy a csomópont már látta a csomagot,
    a csomag eldobásra kerül.

    A seen-cache ``(node_id, packet_id)`` párokat tárol.

    Parameters
    ----------
    G:
        Szomszédsági gráf (``build_neighbor_graph`` kimenete).
    sink_id:
        A sink csomópont azonosítója.
    default_ttl:
        Alapértelmezett TTL értéke, ha a hívó nem ad meg külömbözőt.
    """

    def __init__(self, G: nx.Graph, sink_id: int = 0, default_ttl: int = 16) -> None:
        self._G = G
        self._sink_id = sink_id
        self._default_ttl = default_ttl
        self._seen: set[tuple[int, int]] = set()  # (node_id, packet_id)

        self._delivered: list[RoutedPacket] = []
        self._dropped: list[RoutedPacket] = []

    # ------------------------------------------------------------------
    # Publikus interfész
    # ------------------------------------------------------------------

    @property
    def sink_id(self) -> int:
        return self._sink_id

    @property
    def delivered_packets(self) -> list[RoutedPacket]:
        """Sikeresen kézbesített csomagok listája."""
        return list(self._delivered)

    @property
    def dropped_packets(self) -> list[RoutedPacket]:
        """Eldobott csomagok listája."""
        return list(self._dropped)

    def reset(self) -> None:
        """Visszaállítja a seen-cache-t és a statisztikákat."""
        self._seen.clear()
        self._delivered.clear()
        self._dropped.clear()

    def inject(
        self,
        packet_id: int,
        src: int,
        ttl: Optional[int] = None,
    ) -> list[RoutedPacket]:
        """Egy csomag injektálása a ``src`` csomópontból flooding-gal.

        Szélességi keresés szerű terjedés: minden csomópont, amely
        elsőként látja a csomagot, továbbküldi szomszédjainak.

        Parameters
        ----------
        packet_id:
            Az injektált csomag egyedi azonosítója.
        src:
            Forrás csomópont azonosítója.
        ttl:
            TTL értéke. Ha ``None``, a ``default_ttl`` kerül felhasználásra.

        Returns
        -------
        list[RoutedPacket]
            Azon ``RoutedPacket`` példányok listája, amelyek a sinkbe értek
            (általában 0 vagy 1 darab flooding esetén).
        """
        if ttl is None:
            ttl = self._default_ttl

        # Sor: (aktuális csomópont, aktuális TTL, eddigi útvonal)
        queue: deque[tuple[int, int, list[int]]] = deque()
        queue.append((src, ttl, [src]))
        self._seen.add((src, packet_id))

        delivered_this_round: list[RoutedPacket] = []

        while queue:
            node, remaining_ttl, path = queue.popleft()

            # Elértük a sink-et?
            if node == self._sink_id:
                pkt = RoutedPacket(
                    packet_id=packet_id,
                    src=src,
                    dst=self._sink_id,
                    ttl=remaining_ttl,
                    hops=list(path),
                    delivered=True,
                )
                self._delivered.append(pkt)
                delivered_this_round.append(pkt)
                continue  # Nem terjesztjük tovább a sink-ből

            # TTL ellenőrzés
            if remaining_ttl <= 0:
                pkt = RoutedPacket(
                    packet_id=packet_id,
                    src=src,
                    dst=self._sink_id,
                    ttl=0,
                    hops=list(path),
                    dropped=True,
                    drop_reason="TTL=0",
                )
                self._dropped.append(pkt)
                continue

            # Továbbküldés szomszédoknak
            for neighbor in self._G.neighbors(node):
                if (neighbor, packet_id) not in self._seen:
                    self._seen.add((neighbor, packet_id))
                    queue.append((neighbor, remaining_ttl - 1, path + [neighbor]))

        return delivered_this_round

    def pdr(self) -> float:
        """Packet Delivery Ratio: kézbesített / (kézbesített + eldobott)."""
        total = len(self._delivered) + len(self._dropped)
        return len(self._delivered) / total if total > 0 else 0.0

    def avg_hop_count(self) -> float:
        """Átlagos hop-count a kézbesített csomagokra."""
        if not self._delivered:
            return 0.0
        return sum(p.hop_count for p in self._delivered) / len(self._delivered)


# ---------------------------------------------------------------------------
# SinkTreeRouter — statikus BFS sink-fa ETX-alapú szülőválasztással
# ---------------------------------------------------------------------------


def _etx(prr: float) -> float:
    """ETX metrika: várható adások száma sikeres átvitelhez (1/PRR).

    Ha PRR == 0, végtelen (float('inf')) értéket ad vissza.
    """
    return 1.0 / prr if prr > 0.0 else float("inf")


class SinkTreeRouter:
    """Statikus sink-fa routing BFS/ETX alapon.

    A fa felépítése egyszeri, a konstruktorban történik. Minden csomópont
    szülőjét az ETX-súlyozott legrövidebb út határozza meg a sink felé.
    Ha a gráf éle tartalmaz ``prr`` attribútumot, azt használja; egyébként
    a ``distance`` attribútumból becsül (közelebb → jobb PRR, heuristikusan
    prr = exp(-distance / scale)).

    A fa statikus — link-hiba esetén nincs újraszámolás. Ez dokumentált
    korlát; a következő heti ARQ modul kezeli a link-szintű megbízhatóságot.

    Parameters
    ----------
    G:
        Szomszédsági gráf.
    sink_id:
        A sink csomópont azonosítója.
    prr_scale_m:
        Ha az élen nincs ``prr`` attribútum, ezzel a skálával becsüljük:
        ``prr = exp(-distance / prr_scale_m)``.
    """

    def __init__(
        self,
        G: nx.Graph,
        sink_id: int = 0,
        prr_scale_m: float = 30.0,
    ) -> None:
        self._G = G
        self._sink_id = sink_id
        self._prr_scale_m = prr_scale_m

        # ETX-súlyozott Dijkstra a sink felé
        self._parent: dict[int, Optional[int]] = {}
        self._etx_to_sink: dict[int, float] = {}
        self._build_tree()

    # ------------------------------------------------------------------
    # Privát: fa építés
    # ------------------------------------------------------------------

    def _edge_etx(self, u: int, v: int) -> float:
        """Egy él ETX értéke."""
        edge_data = self._G.edges[u, v]
        if "prr" in edge_data:
            return _etx(edge_data["prr"])
        dist = edge_data.get("distance", 1.0)
        import math
        prr = math.exp(-dist / self._prr_scale_m)
        return _etx(prr)

    def _build_tree(self) -> None:
        """Dijkstra ETX-súlyokkal; a sink a forrás (fordított irány)."""
        inf = float("inf")
        dist: dict[int, float] = {n: inf for n in self._G.nodes}
        dist[self._sink_id] = 0.0
        self._parent = {n: None for n in self._G.nodes}
        visited: set[int] = set()

        # Egyszerű prioritásos sor (kis gráfokra elegendő)
        import heapq
        pq: list[tuple[float, int]] = [(0.0, self._sink_id)]

        while pq:
            d, u = heapq.heappop(pq)
            if u in visited:
                continue
            visited.add(u)

            for v in self._G.neighbors(u):
                if v in visited:
                    continue
                edge_cost = self._edge_etx(u, v)
                new_d = d + edge_cost
                if new_d < dist[v]:
                    dist[v] = new_d
                    self._parent[v] = u
                    heapq.heappush(pq, (new_d, v))

        self._etx_to_sink = dist

    # ------------------------------------------------------------------
    # Publikus interfész
    # ------------------------------------------------------------------

    @property
    def sink_id(self) -> int:
        return self._sink_id

    def parent_of(self, node_id: int) -> Optional[int]:
        """A csomópont szülője a sink-fában (None = sink vagy nem elérhető)."""
        return self._parent.get(node_id)

    def etx_to_sink(self, node_id: int) -> float:
        """Összesített ETX a csomóponttól a sinkig."""
        return self._etx_to_sink.get(node_id, float("inf"))

    def path_to_sink(self, node_id: int) -> list[int]:
        """Az optimális útvonal ``node_id``-től a sinkig.

        Returns
        -------
        list[int]
            Az útvonal csomópontjainak listája (``node_id``-vel kezdve,
            ``sink_id``-vel zárva). Ha a csomópont nem érhető el, üres
            lista kerül visszaadásra.
        """
        if self._etx_to_sink.get(node_id, float("inf")) == float("inf"):
            return []
        path = [node_id]
        current = node_id
        visited_in_path: set[int] = {current}
        while current != self._sink_id:
            p = self._parent.get(current)
            if p is None or p in visited_in_path:
                return []  # Kör vagy zsákutca — nem fordulhat elő korrekt gráfon
            path.append(p)
            visited_in_path.add(p)
            current = p
        return path

    def route(self, packet_id: int, src: int) -> RoutedPacket:
        """Egy csomag irányítása a sinkbe az előre számolt fa alapján.

        Parameters
        ----------
        packet_id:
            A csomag azonosítója.
        src:
            A forrás csomópont.

        Returns
        -------
        RoutedPacket
            A routing eredménye (delivered vagy dropped).
        """
        path = self.path_to_sink(src)
        if not path:
            return RoutedPacket(
                packet_id=packet_id,
                src=src,
                dst=self._sink_id,
                hops=[src],
                dropped=True,
                drop_reason="no_route",
            )
        return RoutedPacket(
            packet_id=packet_id,
            src=src,
            dst=self._sink_id,
            hops=path,
            delivered=True,
        )

    def all_reachable(self) -> list[int]:
        """Azon csomópontok listája, amelyek elérik a sink-et."""
        return [
            n for n, d in self._etx_to_sink.items()
            if d < float("inf") and n != self._sink_id
        ]

    def tree_edges(self) -> list[tuple[int, int]]:
        """A sink-fa élei (gyermek, szülő) párként."""
        return [
            (n, p)
            for n, p in self._parent.items()
            if p is not None and n != self._sink_id
        ]
