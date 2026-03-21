"""Topológia vizualizáció: random / grid / cluster deployment összehasonlítása.

Három deployment stratégiát ábrázol egymás mellett egy 3-panel ábrán:
  1. Random uniform deployment
  2. Grid deployment (enyhe jitterrel)
  3. Cluster deployment (K=3 klaszter)

Minden panelen:
  - Csomópontok pozíciói (sink kiemelve)
  - Hatótáv alapú szomszédsági élek
  - Csomópontok száma, él, összefüggőségi metrikák a cím alatt

Kimenet: reports/figures/topology_viz.png

Seed: 42 (reprodukálható)
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
import numpy as np

from wsnsim.utils.topology import (
    Node,
    build_neighbor_graph,
    cluster_deployment,
    connectivity_stats,
    grid_deployment,
    random_deployment,
)

# ── Paraméterek ──────────────────────────────────────────────────────────────
SEED = 42
N_NODES = 20
AREA_M = 100.0
RANGE_M = 30.0        # rádió hatótávolság
SINK_ID = 0

GRID_ROWS, GRID_COLS = 4, 5   # 4×5 = 20 csomópont
GRID_SPACING = 20.0            # m
GRID_JITTER = 4.0              # ±2 m jitter

N_CLUSTERS = 3
CLUSTER_STD = 18.0

FIG_PATH = (
    Path(__file__).parent.parent / "reports" / "figures" / "topology_viz.png"
)


# ── Rajzoló segédfüggvény ────────────────────────────────────────────────────

def _draw_topology(
    ax: plt.Axes,
    nodes: list[Node],
    G: nx.Graph,
    title: str,
    range_m: float,
    *,
    with_cluster_colors: bool = False,
) -> None:
    """Egy deployment topológia rajzolása egy Axes-re."""
    pos = nx.get_node_attributes(G, "pos")
    stats = connectivity_stats(G, sink_id=SINK_ID)

    # Csomópontszínek
    if with_cluster_colors:
        cids = [G.nodes[n].get("cluster_id", 0) or 0 for n in G.nodes]
        palette = plt.cm.Set1.colors  # type: ignore[attr-defined]
        node_colors = [palette[c % len(palette)] for c in cids]
    else:
        node_colors = [
            "#e74c3c" if G.nodes[n]["is_sink"] else "#3498db"
            for n in G.nodes
        ]

    # Sink méret kiemelés
    node_sizes = [
        220 if G.nodes[n]["is_sink"] else 80
        for n in G.nodes
    ]

    nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.25, width=0.8,
                           edge_color="#7f8c8d")
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors,
                           node_size=node_sizes)

    # Sink felirat
    sink_pos = {n: p for n, p in pos.items() if G.nodes[n]["is_sink"]}
    nx.draw_networkx_labels(ax=ax, G=G, pos=sink_pos,
                            labels={n: "S" for n in sink_pos},
                            font_size=6, font_color="white", font_weight="bold")

    # Hatótáv kör a sinkre
    if SINK_ID in pos:
        sx, sy = pos[SINK_ID]
        circle = plt.Circle((sx, sy), range_m, color="#e74c3c",
                             fill=False, linestyle="--", linewidth=0.8, alpha=0.4)
        ax.add_patch(circle)

    # Metrikák a cím alatt
    conn_str = "összefüggő ✓" if stats["is_connected"] else f"{stats['n_components']} komp."
    reach_pct = 100 * stats["sink_reachable_count"] / stats["n_nodes"] if stats["n_nodes"] else 0
    subtitle = (
        f"N={stats['n_nodes']}, él={stats['n_edges']}, "
        f"avgDeg={stats['avg_degree']:.1f}\n"
        f"{conn_str}, sink elér.: {reach_pct:.0f}%"
    )
    ax.set_title(f"{title}\n{subtitle}", fontsize=9, pad=4)
    ax.set_xlim(-5, AREA_M + 5)
    ax.set_ylim(-5, AREA_M + 5)
    ax.set_xlabel("x [m]", fontsize=8)
    ax.set_ylabel("y [m]", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.2)


# ── Fő futtatás ──────────────────────────────────────────────────────────────

def main() -> None:
    rng = np.random.default_rng(SEED)

    # --- Random deployment ---
    nodes_r = random_deployment(N_NODES, area_m=AREA_M, sink_id=SINK_ID, rng=rng)
    G_r = build_neighbor_graph(nodes_r, range_m=RANGE_M)
    stats_r = connectivity_stats(G_r, sink_id=SINK_ID)

    # --- Grid deployment ---
    nodes_g = grid_deployment(GRID_ROWS, GRID_COLS, spacing_m=GRID_SPACING,
                               jitter_m=GRID_JITTER, sink_id=SINK_ID, rng=rng)
    G_g = build_neighbor_graph(nodes_g, range_m=RANGE_M)
    stats_g = connectivity_stats(G_g, sink_id=SINK_ID)

    # --- Cluster deployment ---
    nodes_c = cluster_deployment(N_NODES, n_clusters=N_CLUSTERS, area_m=AREA_M,
                                  cluster_std_m=CLUSTER_STD, sink_id=SINK_ID, rng=rng)
    G_c = build_neighbor_graph(nodes_c, range_m=RANGE_M)
    stats_c = connectivity_stats(G_c, sink_id=SINK_ID)

    # Konzol összefoglaló
    header = f"{'Stratégia':<12}  {'N':>3}  {'Él':>4}  {'avgDeg':>7}  {'Comp':>5}  {'Összef.':>8}  {'Sink%':>6}"
    print(header)
    print("-" * len(header))
    for name, s in [("Random", stats_r), ("Grid", stats_g), ("Cluster", stats_c)]:
        reach_pct = 100 * s["sink_reachable_count"] / s["n_nodes"]
        print(f"{name:<12}  {s['n_nodes']:>3}  {s['n_edges']:>4}  "
              f"{s['avg_degree']:>7.2f}  {s['n_components']:>5}  "
              f"{'igen' if s['is_connected'] else 'nem':>8}  {reach_pct:>5.0f}%")

    # ── Ábra ─────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8))
    fig.suptitle(
        f"WSN Topológia összehasonlítás — hatótáv={RANGE_M} m, seed={SEED}",
        fontsize=11,
    )

    _draw_topology(axes[0], nodes_r, G_r, "Random deployment", RANGE_M)
    _draw_topology(axes[1], nodes_g, G_g, "Grid deployment (jitter=4 m)", RANGE_M)
    _draw_topology(axes[2], nodes_c, G_c, f"Cluster deployment (K={N_CLUSTERS})",
                   RANGE_M, with_cluster_colors=True)

    # Jelmagyarázat
    legend_handles = [
        mpatches.Patch(color="#e74c3c", label="Sink"),
        mpatches.Patch(color="#3498db", label="Szenzor"),
    ]
    fig.legend(handles=legend_handles, loc="lower center", ncol=2,
               fontsize=9, bbox_to_anchor=(0.5, -0.02))

    plt.tight_layout(rect=(0, 0.04, 1, 1))
    FIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_PATH, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nÁbra mentve: {FIG_PATH}")


if __name__ == "__main__":
    main()
