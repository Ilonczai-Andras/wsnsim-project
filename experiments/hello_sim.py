"""hello_sim.py — wsnsim v0 „Hello Simulation" demonstráció.

5 szenzorcsomópont periodikusan küld adatcsomagokat egy sink felé.
Az ütemezési közök véletlenszerűek, de seed=42-vel reprodukálhatók.

Futtatás::

    python experiments/hello_sim.py

Kimenet:
    - Szövegeses statisztika-táblázat (stdout)
    - reports/figures/hello_sim_events.png (oszlopdiagram)
"""

from __future__ import annotations

import sys
from pathlib import Path

# --- projekt gyökerét a Python-path-ba adjuk (ha közvetlen script) -----------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
# -----------------------------------------------------------------------------

import numpy as np
import matplotlib.pyplot as plt

from wsnsim.sim import SimClock, Scheduler, SimLogger
from wsnsim.metrics import StatsCollector

# ---------------------------------------------------------------------------
# Konfiguráció
# ---------------------------------------------------------------------------

SEED: int = 42
N_NODES: int = 5
SIM_DURATION_US: float = 10_000.0   # 10 ms szimulált idő µs-ban
PACKET_SIZE_BYTES: int = 32          # egy csomag mérete bájtban
TX_INTERVAL_MEAN_US: float = 1_500.0 # átlagos küldési közök µs-ban

FIGURES_DIR = _PROJECT_ROOT / "reports" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Szimulált csomópontok
# ---------------------------------------------------------------------------

def make_node_sender(
    node_id: int,
    sched: Scheduler,
    stats: StatsCollector,
    log: SimLogger,
    rng: np.random.Generator,
) -> None:
    """Rekurzívan ütemezi az adott csomópont következő adásait.

    A következő küldési köz exponenciális eloszlású, átlaga *TX_INTERVAL_MEAN_US*.
    Az ütemezés leáll, ha a következő időpont túllépné *SIM_DURATION_US*-t.

    Args:
        node_id: A csomópont sorszáma (0..N_NODES-1).
        sched:   Az aktív Scheduler példány.
        stats:   A statisztika-gyűjtő.
        log:     A szimulációs logger.
        rng:     Az adott csomópont véletlenszám-generátora.
    """
    def _send(event):  # type: ignore[no-untyped-def]
        current_time = sched.clock.now
        log.debug(f"Node {node_id:02d} TX @ {current_time:.1f}µs  ({PACKET_SIZE_BYTES}B)")
        stats.record(f"node_{node_id:02d}_tx", value=float(PACKET_SIZE_BYTES))
        stats.record("tx_total", value=float(PACKET_SIZE_BYTES))

        # következő küldés ütemezése
        interval = rng.exponential(TX_INTERVAL_MEAN_US)
        next_time = current_time + interval
        if next_time <= SIM_DURATION_US:
            sched.schedule(next_time, _send, payload=node_id)

    # Az első küldés időpontja véletlen
    first_tx = rng.exponential(TX_INTERVAL_MEAN_US)
    if first_tx <= SIM_DURATION_US:
        sched.schedule(first_tx, _send, payload=node_id)


# ---------------------------------------------------------------------------
# Főprogram
# ---------------------------------------------------------------------------

def run_simulation() -> StatsCollector:
    """Lefuttatja a teljes szimulációt és visszaadja a statisztikákat.

    Returns:
        A kitöltött :class:`~wsnsim.metrics.StatsCollector` példány.
    """
    master_rng = np.random.default_rng(SEED)
    clock = SimClock()
    sched = Scheduler(clock, rng=master_rng)
    stats = StatsCollector(clock)
    log = SimLogger(name="hello_sim", clock=clock)

    log.info(f"Szimuláció indul | N={N_NODES}, dur={SIM_DURATION_US}µs, seed={SEED}")

    for node_id in range(N_NODES):
        # Minden csomópont saját, leágaztatott RNG-t kap
        node_rng = np.random.default_rng(master_rng.integers(0, 2**32))
        make_node_sender(node_id, sched, stats, log, node_rng)

    processed = sched.run()
    stats.mark_end()

    log.info(f"Szimuláció kész | feldolgozott események: {processed}")
    return stats


def print_report(stats: StatsCollector) -> None:
    """Kiírja a szöveges statisztika-táblázatot a stdout-ra."""
    print("\n=== wsnsim v0 — Hello Simulation ===")
    print(f"Konfiguráció: seed={SEED}, N={N_NODES}, dur={SIM_DURATION_US:.0f}µs")
    print()
    print(stats.table_str())


def save_figure(stats: StatsCollector) -> Path:
    """Oszlopdiagramot rajzol az egyes csomópontok csomagszámáról.

    A diagram el lesz mentve: ``reports/figures/hello_sim_events.png``.

    Args:
        stats: A kitöltött statisztika-gyűjtő.

    Returns:
        A generált PNG-fájl abszolút elérési útja.
    """
    node_labels = [f"node_{i:02d}" for i in range(N_NODES)]
    tx_counts = [stats.count(f"{lbl}_tx") for lbl in node_labels]
    tx_bytes  = [stats.total(f"{lbl}_tx") for lbl in node_labels]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    fig.suptitle(
        f"wsnsim v0 — Hello Simulation\n"
        f"seed={SEED}, N={N_NODES}, dur={SIM_DURATION_US:.0f} µs",
        fontsize=11,
    )

    # --- bal panel: csomagszám ---
    axes[0].bar(node_labels, tx_counts, color="steelblue", edgecolor="white")
    axes[0].set_title("Elküldött csomagok száma csomópontonként")
    axes[0].set_xlabel("Csomópont")
    axes[0].set_ylabel("Csomagok (db)")
    axes[0].set_ylim(0, max(tx_counts) * 1.25 if tx_counts else 1)
    for bar, val in zip(axes[0].patches, tx_counts):
        axes[0].text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.1,
            str(val),
            ha="center",
            va="bottom",
            fontsize=9,
        )

    # --- jobb panel: átvitt bájtok ---
    axes[1].bar(node_labels, tx_bytes, color="darkorange", edgecolor="white")
    axes[1].set_title("Átvitt adatmennyiség csomópontonként")
    axes[1].set_xlabel("Csomópont")
    axes[1].set_ylabel("Bájtok (B)")
    axes[1].set_ylim(0, max(tx_bytes) * 1.25 if tx_bytes else 1)
    for bar, val in zip(axes[1].patches, tx_bytes):
        axes[1].text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            f"{val:.0f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    plt.tight_layout()
    out_path = FIGURES_DIR / "hello_sim_events.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def main() -> None:
    """Belépési pont: szimuláció → riport → ábra → mentés."""
    stats = run_simulation()
    print_report(stats)
    out = save_figure(stats)
    print(f"\nÁbra mentve: {out}")


if __name__ == "__main__":
    main()
