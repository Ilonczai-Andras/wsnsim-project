"""7.6. hét — Routing összehasonlítás: Flooding vs Sink-fa.

Rácsтопológián (5×5=25 csomópont, sink=0) minden csomópont 1-1
csomagot küld. Összehasonlítjuk:
  – FloodRouter  (pure flooding, TTL=8)
  – SinkTreeRouter (ETX-alapú sink-fa)

Mért mutatók:
  PDR, átlagos hop-count, „energia per bit" faktor (normalizált hop-count).

Kimenet: reports/figures/routing_comparison.png (2×2 panel)
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from wsnsim.utils.topology import grid_deployment, build_neighbor_graph
from wsnsim.models.routing import FloodRouter, SinkTreeRouter

# ---------------------------------------------------------------------------
# Topológia
# ---------------------------------------------------------------------------

ROWS, COLS = 5, 5
SPACING_M = 20.0
RANGE_M = 28.0   # ~1.4× spacing → átlagosan 3–4 szomszéd rácscsomópontonként
SINK_ID = 0
TTL_FLOOD = 10
RNG_SEED = 42

rng = np.random.default_rng(RNG_SEED)
nodes = grid_deployment(ROWS, COLS, spacing_m=SPACING_M, rng=rng)
G = build_neighbor_graph(nodes, range_m=RANGE_M)

n_nodes = G.number_of_nodes()
sources = [nid for nid in G.nodes if nid != SINK_ID]

print(f"Gráf: {n_nodes} csomópont, {G.number_of_edges()} él, sink={SINK_ID}")
print(f"Forrás csomópontok száma: {len(sources)}")

# ---------------------------------------------------------------------------
# Flooding
# ---------------------------------------------------------------------------

flood = FloodRouter(G, sink_id=SINK_ID, default_ttl=TTL_FLOOD)
for pid, src in enumerate(sources, start=1):
    flood.inject(packet_id=pid, src=src)

flood_pdr = flood.pdr()
flood_avg_hops = flood.avg_hop_count()
flood_delivered = flood.delivered_packets

# Per-csomópontos hop-count táblázat
flood_hops_by_node: dict[int, float] = {}
for pkt in flood_delivered:
    flood_hops_by_node[pkt.src] = pkt.hop_count

# ---------------------------------------------------------------------------
# Sink-fa (SinkTreeRouter)
# ---------------------------------------------------------------------------

tree_router = SinkTreeRouter(G, sink_id=SINK_ID)
tree_pkts = [tree_router.route(packet_id=pid, src=src)
             for pid, src in enumerate(sources, start=1)]

tree_delivered = [p for p in tree_pkts if p.delivered]
tree_dropped = [p for p in tree_pkts if p.dropped]

tree_pdr = len(tree_delivered) / len(sources) if sources else 0.0
tree_avg_hops = (sum(p.hop_count for p in tree_delivered) / len(tree_delivered)
                 if tree_delivered else 0.0)

# Per-csomópontos hop-count
tree_hops_by_node: dict[int, float] = {}
for pkt in tree_delivered:
    tree_hops_by_node[pkt.src] = pkt.hop_count

# ETX-to-sink heatmap adatok
etx_by_node = {nid: tree_router.etx_to_sink(nid) for nid in G.nodes}

# ---------------------------------------------------------------------------
# Összefoglaló kiírás
# ---------------------------------------------------------------------------

print("\n=== Routing összehasonlítás ===")
print(f"{'Mutató':<28} {'Flooding':>12} {'Sink-fa':>12}")
print("-" * 54)
print(f"{'PDR':<28} {flood_pdr:>12.3f} {tree_pdr:>12.3f}")
print(f"{'Átlag hop-count':<28} {flood_avg_hops:>12.2f} {tree_avg_hops:>12.2f}")
print(f"{'Kézbesített csomagok':<28} {len(flood_delivered):>12} {len(tree_delivered):>12}")
print(f"{'Eldobott csomagok':<28} {len(flood.dropped_packets):>12} {len(tree_dropped):>12}")

# ---------------------------------------------------------------------------
# Ábra
# ---------------------------------------------------------------------------

fig, axes = plt.subplots(2, 2, figsize=(12, 10))
fig.suptitle("Routing összehasonlítás: Flooding vs Sink-fa (5×5 rács, 25 csomópont)",
             fontsize=13)

# ---- 1. panel: PDR összehasonlítás sávdiagram ----
ax = axes[0, 0]
methods = ["Flooding\n(TTL=10)", "Sink-fa\n(ETX)"]
pdrs = [flood_pdr, tree_pdr]
bars = ax.bar(methods, pdrs, color=["#4C72B0", "#DD8452"], edgecolor="black", width=0.4)
ax.set_ylim(0, 1.1)
ax.set_ylabel("PDR")
ax.set_title("Csomagkézbesítési arány (PDR)")
for bar, val in zip(bars, pdrs):
    ax.text(bar.get_x() + bar.get_width() / 2, val + 0.03,
            f"{val:.3f}", ha="center", va="bottom", fontsize=10)
ax.axhline(1.0, color="gray", linestyle="--", linewidth=0.8, label="Ideális (PDR=1)")
ax.legend(fontsize=8)

# ---- 2. panel: Átlagos hop-count összehasonlítás ----
ax = axes[0, 1]
hop_vals = [flood_avg_hops, tree_avg_hops]
bars2 = ax.bar(methods, hop_vals, color=["#4C72B0", "#DD8452"], edgecolor="black", width=0.4)
ax.set_ylabel("Átlagos hop-count")
ax.set_title("Átlagos hop-count (forrástól sinkig)")
for bar, val in zip(bars2, hop_vals):
    ax.text(bar.get_x() + bar.get_width() / 2, val + 0.05,
            f"{val:.2f}", ha="center", va="bottom", fontsize=10)

# ---- 3. panel: Hop-count eloszlás (hisztogram) ----
ax = axes[1, 0]
flood_hop_vals = [v for v in flood_hops_by_node.values()]
tree_hop_vals = [v for v in tree_hops_by_node.values()]
max_hops = max(max(flood_hop_vals, default=0), max(tree_hop_vals, default=0))
bins = range(0, int(max_hops) + 3)
ax.hist(flood_hop_vals, bins=bins, alpha=0.6, label="Flooding", color="#4C72B0",
        edgecolor="black", align="left")
ax.hist(tree_hop_vals, bins=bins, alpha=0.6, label="Sink-fa", color="#DD8452",
        edgecolor="black", align="left")
ax.set_xlabel("Hop-count")
ax.set_ylabel("Csomópontok száma")
ax.set_title("Hop-count eloszlás")
ax.legend()
ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))

# ---- 4. panel: ETX-alapú sink-fa hálózati topológia ----
ax = axes[1, 1]

# Csomópontok pozíciói
pos = {node.node_id: (node.x, node.y) for node in nodes}

# Fa élek
tree_edge_list = tree_router.tree_edges()

# ETX értékek normalizált hőtérképhez
etx_values = np.array([etx_by_node.get(nid, 0.0)
                        for nid in sorted(G.nodes)])
finite_etx = etx_values[np.isfinite(etx_values)]
vmax = float(np.max(finite_etx)) if len(finite_etx) > 0 else 1.0

# Nem-fa élek halványan
non_tree_edges = [(u, v) for u, v in G.edges()
                  if (u, v) not in tree_edge_list and (v, u) not in tree_edge_list]
nx_import = __import__("networkx")
nx_import.draw_networkx_edges(G, pos, edgelist=non_tree_edges, ax=ax,
                               alpha=0.15, edge_color="gray")

# Fa élek kiemelve
nx_import.draw_networkx_edges(G, pos, edgelist=tree_edge_list, ax=ax,
                               width=2.0, edge_color="#DD8452", alpha=0.8,
                               arrows=True, arrowstyle="-|>",
                               arrowsize=10, connectionstyle="arc3,rad=0.05")

# Csomópontok ETX-alapú színezéssel
node_colors = [etx_by_node.get(nid, 0.0) for nid in sorted(G.nodes)]
nc = nx_import.draw_networkx_nodes(G, pos, ax=ax, node_size=250,
                                    node_color=node_colors,
                                    cmap=plt.cm.YlOrRd, vmin=0, vmax=vmax)
nx_import.draw_networkx_labels(G, pos, ax=ax, font_size=7)

plt.colorbar(nc, ax=ax, label="ETX a sinkig")
ax.set_title(f"Sink-fa topológia (ETX-súlyozás)\nPiros fa-élek, sink={SINK_ID}")
ax.axis("off")

plt.tight_layout()
out_path = Path(__file__).parent.parent / "reports" / "figures" / "routing_comparison.png"
out_path.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"\nÁbra mentve: {out_path}")
plt.close()
