"""Topológia generátor és szomszédsági gráf — WSN deployment modellek.

Három deployment stratégia érhető el:

* **random_deployment** — csomópontok egyenletesen véletlenszerű eloszlással
  egy [0, area_m] × [0, area_m] területen.
* **grid_deployment** — szabályos rácselrendezés, amelybe opcionálisan pozíció-
  jitter adható.
* **cluster_deployment** — K klaszter-középpont körül Gauss-eloszlású szórással
  helyezi el a csomópontokat.

Mindhárom stratégia ``list[Node]`` értéket ad vissza, ahol a ``Node`` dataclass
tartalmazza a csomópont azonosítóját, koordinátáit és sink-jelzőjét.

A ``build_neighbor_graph()`` függvény hatótáv alapján NetworkX ``Graph``-ot épít,
amelyen az összes szokásos gráfalgoritmus (BFS, összefüggőség, stb.) futtatható.

A ``connectivity_stats()`` segédfüggvény legfontosabb metrikákat számol:
komponensszám, sink elérhetőség, átlagos fokszám, összefüggőség.

Példa::

    from wsnsim.utils.topology import random_deployment, build_neighbor_graph
    import numpy as np

    nodes = random_deployment(n=20, area_m=100.0, rng=np.random.default_rng(42))
    G = build_neighbor_graph(nodes, range_m=30.0)
    stats = connectivity_stats(G, sink_id=0)
    print(stats)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import networkx as nx
import numpy as np
from numpy.random import Generator


# ---------------------------------------------------------------------------
# Node dataclass
# ---------------------------------------------------------------------------


@dataclass
class Node:
    """Egy szenzorcsomópont helyzete és azonosítója.

    Parameters
    ----------
    node_id:
        Egyedi egész azonosító.
    x, y:
        Pozíció méterben a deployment területen.
    is_sink:
        Ha ``True``, ez a csomópont a sink (adatgyűjtő állomás).
    cluster_id:
        Opcionális klaszter-azonosító (cluster deployment esetén).
    """

    node_id: int
    x: float
    y: float
    is_sink: bool = False
    cluster_id: Optional[int] = field(default=None, compare=False)

    def distance_to(self, other: "Node") -> float:
        """Euklideszi távolság méterben."""
        return math.hypot(self.x - other.x, self.y - other.y)

    def __repr__(self) -> str:
        sink = " [SINK]" if self.is_sink else ""
        return f"Node(id={self.node_id}, x={self.x:.1f}, y={self.y:.1f}{sink})"


# ---------------------------------------------------------------------------
# Deployment stratégiák
# ---------------------------------------------------------------------------


def random_deployment(
    n: int,
    area_m: float = 100.0,
    *,
    sink_id: int = 0,
    rng: Generator,
) -> list[Node]:
    """Véletlenszerű egyenletes eloszlású deployment.

    Parameters
    ----------
    n:
        Csomópontok száma (beleértve a sink-et).
    area_m:
        Terület oldalhossza méterben (négyzet: [0, area_m]²).
    sink_id:
        Melyik csomópontot jelöljük sink-ként (node_id == sink_id).
    rng:
        Determinisztikus véletlenszám-generátor.

    Returns
    -------
    list[Node]
        n darab Node, a sink_id-jú ``is_sink=True``.
    """
    xs = rng.uniform(0.0, area_m, size=n)
    ys = rng.uniform(0.0, area_m, size=n)
    return [
        Node(node_id=i, x=float(xs[i]), y=float(ys[i]), is_sink=(i == sink_id))
        for i in range(n)
    ]


def grid_deployment(
    rows: int,
    cols: int,
    spacing_m: float = 20.0,
    *,
    jitter_m: float = 0.0,
    sink_id: int = 0,
    rng: Generator,
) -> list[Node]:
    """Szabályos rács-elrendezés, opcionális pozíció-jitterrel.

    A csomópontok bal felső saroktól sorban kerülnek sorszámozásra
    (sor-major sorrend). Az origó a (0, 0) pont.

    Parameters
    ----------
    rows, cols:
        Rács sorainak és oszlopainak száma.
    spacing_m:
        Szomszédos csomópontok távolsága méterben.
    jitter_m:
        Maximális véletlen pozíció-eltérés (±jitter_m/2 uniform). 0 = nincs.
    sink_id:
        Melyik csomópont a sink.
    rng:
        Determinisztikus véletlenszám-generátor (akkor is átadandó, ha jitter=0).

    Returns
    -------
    list[Node]
        rows × cols darab Node.
    """
    nodes = []
    n = rows * cols
    jx = rng.uniform(-jitter_m / 2, jitter_m / 2, size=n) if jitter_m > 0 else np.zeros(n)
    jy = rng.uniform(-jitter_m / 2, jitter_m / 2, size=n) if jitter_m > 0 else np.zeros(n)
    for i in range(rows):
        for j in range(cols):
            idx = i * cols + j
            x = j * spacing_m + float(jx[idx])
            y = i * spacing_m + float(jy[idx])
            nodes.append(Node(node_id=idx, x=x, y=y, is_sink=(idx == sink_id)))
    return nodes


def cluster_deployment(
    n: int,
    n_clusters: int = 3,
    area_m: float = 100.0,
    cluster_std_m: float = 15.0,
    *,
    sink_id: int = 0,
    rng: Generator,
) -> list[Node]:
    """Klaszteres deployment: csomópontok Gauss-eloszlással klaszter-középpontok körül.

    A klaszter-középpontok véletlenszerűen kerülnek az [0, area_m]² területre.
    Minden csomóponthoz véletlenszerűen választódik egy klaszter, majd
    N(0, cluster_std_m) pozíció-szórással helyeződik el, a határokat levágva.

    Parameters
    ----------
    n:
        Csomópontok száma összesen.
    n_clusters:
        Klaszterek száma.
    area_m:
        Terület oldalhossza méterben.
    cluster_std_m:
        A pozíció-eloszlás szórása méterben.
    sink_id:
        Melyik csomópont a sink.
    rng:
        Determinisztikus véletlenszám-generátor.

    Returns
    -------
    list[Node]
        n darab Node, ``cluster_id`` mezővel feltöltve.
    """
    # Klaszter-középpontok
    centers_x = rng.uniform(cluster_std_m, area_m - cluster_std_m, size=n_clusters)
    centers_y = rng.uniform(cluster_std_m, area_m - cluster_std_m, size=n_clusters)

    # Csomópontok klaszter-hozzárendelése
    assignments = rng.integers(0, n_clusters, size=n)

    nodes = []
    for i in range(n):
        cid = int(assignments[i])
        x = float(np.clip(rng.normal(centers_x[cid], cluster_std_m), 0.0, area_m))
        y = float(np.clip(rng.normal(centers_y[cid], cluster_std_m), 0.0, area_m))
        nodes.append(Node(node_id=i, x=x, y=y, is_sink=(i == sink_id), cluster_id=cid))
    return nodes


# ---------------------------------------------------------------------------
# Szomszédsági gráf
# ---------------------------------------------------------------------------


def build_neighbor_graph(
    nodes: list[Node],
    range_m: float,
    *,
    weight_attr: str = "distance",
) -> nx.Graph:
    """Hatótáv alapú szomszédsági gráf építése.

    Két csomópont között él kerül a gráfba, ha euklideszi távolságuk
    ≤ *range_m*. Az él ``distance`` attribútuma a tényleges távolságot,
    a ``weight`` attribútuma annak reciprokát tárolja (útkeresésekhez).

    Parameters
    ----------
    nodes:
        A csomópontok listája.
    range_m:
        Rádió hatótávolsága méterben.
    weight_attr:
        Az él-attribútum neve, amelybe a távolság kerül. Default: ``"distance"``.

    Returns
    -------
    nx.Graph
        Csomópontok ``node_id``-vel, ``pos``, ``is_sink``, ``cluster_id``
        node-attribútumokkal; élek ``distance`` és ``weight`` attribútumokkal.
    """
    G: nx.Graph = nx.Graph()

    for node in nodes:
        G.add_node(
            node.node_id,
            pos=(node.x, node.y),
            is_sink=node.is_sink,
            cluster_id=node.cluster_id,
        )

    for i, u in enumerate(nodes):
        for v in nodes[i + 1 :]:
            d = u.distance_to(v)
            if d <= range_m:
                G.add_edge(
                    u.node_id,
                    v.node_id,
                    **{weight_attr: d, "weight": 1.0 / d if d > 0 else float("inf")},
                )

    return G


# ---------------------------------------------------------------------------
# Connectivity metrikák
# ---------------------------------------------------------------------------


def connectivity_stats(G: nx.Graph, sink_id: int = 0) -> dict:
    """Összefüggőségi metrikák számítása a gráfra.

    Parameters
    ----------
    G:
        A szomszédsági gráf (``build_neighbor_graph`` kimenete).
    sink_id:
        A sink csomópont azonosítója.

    Returns
    -------
    dict
        Kulcsok:
        ``n_nodes``, ``n_edges``, ``n_components``, ``is_connected``,
        ``sink_reachable_count`` (hány csomópontból érhető el a sink),
        ``avg_degree``, ``max_degree``, ``min_degree``.
    """
    n = G.number_of_nodes()
    components = list(nx.connected_components(G))
    n_components = len(components)
    is_connected = n_components == 1

    # Hány csomópontból érhető el a sink?
    if sink_id in G:
        sink_component = next(
            (c for c in components if sink_id in c), set()
        )
        sink_reachable = len(sink_component)
    else:
        sink_reachable = 0

    degrees = [d for _, d in G.degree()]
    avg_deg = float(np.mean(degrees)) if degrees else 0.0
    max_deg = max(degrees) if degrees else 0
    min_deg = min(degrees) if degrees else 0

    return {
        "n_nodes": n,
        "n_edges": G.number_of_edges(),
        "n_components": n_components,
        "is_connected": is_connected,
        "sink_reachable_count": sink_reachable,
        "avg_degree": avg_deg,
        "max_degree": max_deg,
        "min_degree": min_deg,
    }
