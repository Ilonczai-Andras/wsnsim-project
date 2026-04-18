"""Biztonsági overhead összehasonlítás: NONE vs MAC_ONLY vs MAC_ENCRYPT.

Topológia: 5×5 rácsgrid (25 csomópont, spacing=20m, range=25m, sink=0, seed=42).
Szimuláció: 100 csomag/csomópont, SinkTreeRouter.
Három konfig összehasonlítva: OVERHEAD_NONE, OVERHEAD_MAC_ONLY, OVERHEAD_MAC_ENCRYPT.

Stdout táblázat:
  config | mic_bytes | encrypt_bytes | energy_per_pkt_uJ | latency_us | overhead_pct

Ábra: reports/figures/security_overhead.png (2 panel):
  - Bal: energia/csomag sávdiagram (3 konfig)
  - Jobb: latency overhead sávdiagram
"""

from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from wsnsim.models.energy import EnergyModel
from wsnsim.models.packet import Packet
from wsnsim.models.routing import SinkTreeRouter
from wsnsim.models.security import (
    OVERHEAD_MAC_ENCRYPT,
    OVERHEAD_MAC_ONLY,
    OVERHEAD_NONE,
    SecurityOverheadConfig,
    SecurityOverheadModel,
)
from wsnsim.utils.topology import build_neighbor_graph, grid_deployment

# ---------------------------------------------------------------------------
# Paraméterek
# ---------------------------------------------------------------------------

SEED = 42
ROWS, COLS = 5, 5
SPACING_M = 20.0
RANGE_M = 25.0
SINK_ID = 0
PACKETS_PER_NODE = 100
PACKET_SIZE_BYTES = 32

FIGURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "reports", "figures", "security_overhead.png"
)

CONFIGS: list[tuple[str, SecurityOverheadConfig]] = [
    ("NONE", OVERHEAD_NONE),
    ("MAC_ONLY", OVERHEAD_MAC_ONLY),
    ("MAC_ENCRYPT", OVERHEAD_MAC_ENCRYPT),
]


# ---------------------------------------------------------------------------
# Szimuláció
# ---------------------------------------------------------------------------

def simulate_config(
    config: SecurityOverheadConfig,
    router: SinkTreeRouter,
    nodes_list: list,
    packets_per_node: int,
) -> dict[str, float]:
    """Egy konfig szimulálása: N csomag/csomópont, csak kriptó overhead energia.

    A SecurityOverheadModel.apply() által elszámolt CPU overhead energiát méri —
    ez a biztonsági intézkedés tényleges extra költsége (rádiós TX nélkül).

    Returns
    -------
    dict[str, float]
        Kulcsok: ``energy_per_pkt_j``, ``latency_us``.
    """
    total_energy_j = 0.0
    n_nodes = len(nodes_list)

    for node_id in range(n_nodes):
        em = EnergyModel()
        model = SecurityOverheadModel(config, em)
        t_us = 0.0
        for pkt_id in range(packets_per_node):
            pkt = Packet(
                packet_id=pkt_id,
                src=node_id,
                dst=SINK_ID,
                size_bytes=PACKET_SIZE_BYTES,
                created_at=t_us,
            )
            model.apply(pkt, at_us=t_us)
            t_us += config.cpu_overhead_us + 1000.0  # 1ms küldési ciklus
        total_energy_j += em.consumed_j

    avg_energy_per_pkt_j = total_energy_j / (n_nodes * packets_per_node)

    return {
        "energy_per_pkt_j": avg_energy_per_pkt_j,
        "latency_us": config.cpu_overhead_us,
    }


def main() -> None:
    rng = np.random.default_rng(SEED)
    nodes = grid_deployment(ROWS, COLS, spacing_m=SPACING_M, sink_id=SINK_ID, rng=rng)
    G = build_neighbor_graph(nodes, range_m=RANGE_M)
    router = SinkTreeRouter(G, sink_id=SINK_ID)

    results: list[dict] = []
    for name, config in CONFIGS:
        metrics = simulate_config(config, router, nodes, PACKETS_PER_NODE)
        results.append({"name": name, "config": config, **metrics})
    # --- referencia NONE energia ---
    none_energy = next(r["energy_per_pkt_j"] for r in results if r["name"] == "NONE")

    print("=== Biztonsági overhead összehasonlítás ===")
    print(f"Topológia: {ROWS}×{COLS} rácsgrid, spacing={SPACING_M}m, range={RANGE_M}m, seed={SEED}")
    print(f"Csomag/csomópont: {PACKETS_PER_NODE}, csomagméret: {PACKET_SIZE_BYTES} B")
    print()
    hdr = f"{'konfig':>12} | {'mic_bytes':>9} | {'encrypt_bytes':>13} | {'energia/csomag (µJ)':>20} | {'latencia (µs)':>14} | {'extra energia (µJ)':>19}"
    print(hdr)
    print("-" * len(hdr))

    for r in results:
        cfg: SecurityOverheadConfig = r["config"]
        e_uj = r["energy_per_pkt_j"] * 1e6
        lat = r["latency_us"]
        extra_uj = (r["energy_per_pkt_j"] - none_energy) * 1e6
        print(
            f"{r['name']:>12} | {cfg.mic_bytes:>9} | {cfg.encrypt_bytes:>13} | "
            f"{e_uj:>20.4f} | {lat:>14.1f} | {extra_uj:>+18.4f}"
        )

    # ---------------------------------------------------------------------------
    # Ábra: 2 panel
    # ---------------------------------------------------------------------------

    names = [r["name"] for r in results]
    energies_uj = [r["energy_per_pkt_j"] * 1e6 for r in results]
    latencies = [r["latency_us"] for r in results]
    colors = ["tab:blue", "tab:orange", "tab:red"]
    x = range(len(names))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(
        f"Biztonsági overhead — {ROWS}×{COLS} rács, {PACKETS_PER_NODE} csomag/csomópont, seed={SEED}",
        fontsize=12,
    )

    # Bal: energia/csomag
    bars1 = ax1.bar(x, energies_uj, color=colors, edgecolor="black", linewidth=0.7)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(names)
    ax1.set_ylabel("Energia / csomag (µJ)")
    ax1.set_title("CPU kriptó energia overhead")
    ax1.bar_label(bars1, fmt="%.4f µJ", padding=3, fontsize=9)
    ax1.set_ylim(0, max(energies_uj) * 1.3 if max(energies_uj) > 0 else 1.0)
    ax1.grid(axis="y", linestyle=":", alpha=0.6)

    # Jobb: latency overhead
    bars2 = ax2.bar(x, latencies, color=colors, edgecolor="black", linewidth=0.7)
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(names)
    ax2.set_ylabel("Latencia overhead (µs)")
    ax2.set_title("CPU feldolgozási latencia")
    ax2.bar_label(bars2, fmt="%.0f µs", padding=3, fontsize=9)
    ax2.set_ylim(0, max(latencies) * 1.3 if max(latencies) > 0 else 1.0)
    ax2.grid(axis="y", linestyle=":", alpha=0.6)

    plt.tight_layout()
    os.makedirs(os.path.dirname(FIGURE_PATH), exist_ok=True)
    plt.savefig(FIGURE_PATH, dpi=120)
    plt.close()
    print(f"\nÁbra mentve: {os.path.abspath(FIGURE_PATH)}")


if __name__ == "__main__":
    main()
