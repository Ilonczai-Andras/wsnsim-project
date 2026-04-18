"""Aggregációs stratégiák összehasonlítása: RawForwarder vs TreeAggregator.

Topológia: 5×5 rácsgrid (25 csomópont, spacing=20m, range=25m, sink=0, seed=42).
Readings R1: normáleloszlás μ=25.0 °C, σ=2.0 °C (seed=42).
Readings R2: R1 + perturbáció N(0, σ=1.5 °C) — a delta-kódolás hatásának szimulálása.
Sweep: threshold_delta ∈ [0.0, 0.5, 1.0, 2.0, 3.0, 5.0].

Módszer: minden threshold_delta értékre egy friss TreeAggregator példány fut
két körön (R1, R2). A táblázatban a 2. kör (R2) adatai szerepelnek, ahol
a delta-kódolás a változás mértékétől függően suppress-eli az üzeneteket.
Az RawForwarder egy körre vonatkozó referencia (deterministikus).

Kimenetek:
  - Stdout táblázat (threshold_delta | messages_sent | bytes_sent | mse | mae | comm_saving_%)
  - reports/figures/aggregation_comparison.png (2 panel)
"""

from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt
import numpy as np

# Workspace-gyökér hozzáadása a path-hoz
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from wsnsim.models.aggregation import AggResult, RawForwarder, TreeAggregator
from wsnsim.models.routing import SinkTreeRouter
from wsnsim.utils.topology import build_neighbor_graph, grid_deployment

# ---------------------------------------------------------------------------
# Paraméterek
# ---------------------------------------------------------------------------

SEED = 42
ROWS, COLS = 5, 5
SPACING_M = 20.0
RANGE_M = 25.0
SINK_ID = 0
READINGS_MU = 25.0
READINGS_SIGMA = 2.0
PERTURBATION_SIGMA = 1.5   # R2 = R1 + N(0, PERTURBATION_SIGMA)
THRESHOLD_DELTAS = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0]
PACKET_SIZE_BYTES = 20

FIGURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "reports", "figures", "aggregation_comparison.png"
)


def main() -> None:
    rng = np.random.default_rng(SEED)

    # Topológia felépítése
    nodes = grid_deployment(ROWS, COLS, spacing_m=SPACING_M, sink_id=SINK_ID, rng=rng)
    G = build_neighbor_graph(nodes, range_m=RANGE_M)
    router = SinkTreeRouter(G, sink_id=SINK_ID)

    # Csak a sinkből elérhető csomópontok
    reachable = {
        n: True for n in G.nodes if router.path_to_sink(n)
    }

    # Mérési értékek generálása (μ=25 °C, σ=2 °C)
    readings_rng = np.random.default_rng(SEED)
    readings_r1: dict[int, float] = {
        n: float(readings_rng.normal(READINGS_MU, READINGS_SIGMA))
        for n in reachable
    }
    # R2: R1 + kis perturbáció (a delta-kódolás hatásának szimulálása)
    perturb_rng = np.random.default_rng(SEED + 1)
    readings_r2: dict[int, float] = {
        n: v + float(perturb_rng.normal(0.0, PERTURBATION_SIGMA))
        for n, v in readings_r1.items()
    }

    # RawForwarder referencia futás (R1)
    raw_fwd = RawForwarder(router, packet_size_bytes=PACKET_SIZE_BYTES)
    raw_result = raw_fwd.run(readings_r1, np.random.default_rng(SEED))

    print("=== Aggregáció összehasonlítás: RawForwarder vs TreeAggregator ===")
    print(f"Topológia: {ROWS}×{COLS} rácsgrid, spacing={SPACING_M}m, range={RANGE_M}m")
    print(f"Csomópontok száma: {len(readings_r1)} (elérhető a sinkből), seed={SEED}")
    print(f"Readings R1: N(μ={READINGS_MU}, σ={READINGS_SIGMA}) °C")
    print(f"Readings R2: R1 + N(0, σ={PERTURBATION_SIGMA}) °C  [delta-kódolás 2. köre]")
    print()
    print(f"{'threshold_delta':>16} | {'messages_sent':>13} | {'bytes_sent':>10} | {'mse':>10} | {'mae':>10} | {'comm_saving_%':>14}")
    print("-" * 85)
    print(
        f"{'raw (R1 referencia)':>16} | {raw_result.messages_sent:>13} | "
        f"{raw_result.bytes_sent:>10} | {raw_result.mse:>10.4f} | "
        f"{raw_result.mae:>10.4f} | {'0.00':>14}"
    )
    print("-" * 85)

    # Sweep: TreeAggregator különböző threshold_delta értékekre (R1 → R2 két kör)
    tree_results: list[tuple[float, AggResult]] = []

    for delta in THRESHOLD_DELTAS:
        tree = TreeAggregator(
            router,
            packet_size_bytes=PACKET_SIZE_BYTES,
            threshold_delta=delta,
        )
        # R1 — inicializálja a prev_value-t
        tree.run(readings_r1, np.random.default_rng(SEED))
        # R2 — a delta-kódolás itt lép működésbe
        result = tree.run(readings_r2, np.random.default_rng(SEED + 1))
        tree_results.append((delta, result))

        saving = (
            (1.0 - result.messages_sent / raw_result.messages_sent) * 100.0
            if raw_result.messages_sent > 0
            else 0.0
        )
        print(
            f"{delta:>16.1f} | {result.messages_sent:>13} | "
            f"{result.bytes_sent:>10} | {result.mse:>10.4f} | "
            f"{result.mae:>10.4f} | {saving:>13.2f}%"
        )

    print()

    # ---------------------------------------------------------------------------
    # Ábra: 2 panel
    # ---------------------------------------------------------------------------

    deltas = [d for d, _ in tree_results]
    tree_msgs = [r.messages_sent for _, r in tree_results]
    tree_mses = [r.mse for _, r in tree_results]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(
        f"Aggregáció összehasonlítás — {ROWS}×{COLS} rácsgrid, seed={SEED}",
        fontsize=13,
    )

    # Bal panel: messages_sent vs threshold_delta
    ax1.axhline(
        raw_result.messages_sent,
        color="tab:blue",
        linestyle="--",
        linewidth=1.5,
        label=f"RawForwarder ({raw_result.messages_sent} üzenet)",
    )
    ax1.plot(deltas, tree_msgs, "o-", color="tab:orange", linewidth=2, label="TreeAggregator")
    ax1.set_xlabel("threshold_delta")
    ax1.set_ylabel("messages_sent")
    ax1.set_title("Kommunikációs költség")
    ax1.legend()
    ax1.grid(True, linestyle=":", alpha=0.6)

    # Jobb panel: MSE vs threshold_delta
    ax2.axhline(
        0.0,
        color="tab:blue",
        linestyle="--",
        linewidth=1.5,
        label="RawForwarder (MSE=0.0)",
    )
    ax2.plot(deltas, tree_mses, "s-", color="tab:orange", linewidth=2, label="TreeAggregator")
    ax2.set_xlabel("threshold_delta")
    ax2.set_ylabel("MSE (°C²)")
    ax2.set_title("Aggregációs hiba (MSE)")
    ax2.legend()
    ax2.grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout()
    os.makedirs(os.path.dirname(FIGURE_PATH), exist_ok=True)
    plt.savefig(FIGURE_PATH, dpi=120)
    plt.close()
    print(f"Ábra mentve: {os.path.abspath(FIGURE_PATH)}")


if __name__ == "__main__":
    main()
