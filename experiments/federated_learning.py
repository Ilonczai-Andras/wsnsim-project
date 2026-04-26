"""experiments/federated_learning.py — 7.12. hét: FL update-periódus sweep.

Stdout táblázat + reports/figures/federated_learning.png
"""

import pathlib

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from wsnsim.models.fed_learning import (
    FedAvgConfig,
    FedAvgSimulation,
    CommCostModel,
    make_node_datasets,
)

# ---------------------------------------------------------------------------
# Paraméterek
# ---------------------------------------------------------------------------

SEED = 42
N_NODES = 10
N_SAMPLES = 200
N_FEATURES = 4
NOISE_STD = 0.5
ROUNDS = 50
LOCAL_STEPS = 5
LEARNING_RATE = 0.01
MODEL_SIZE_BYTES = 128
SAMPLE_SIZE_BYTES = 16

UPDATE_PERIODS = [1, 2, 5, 10, 25, 50]

OUT_PATH = pathlib.Path(__file__).parent.parent / "reports" / "figures" / "federated_learning.png"

# ---------------------------------------------------------------------------
# Konfig és adatgenerálás
# ---------------------------------------------------------------------------

config = FedAvgConfig(
    n_nodes=N_NODES,
    n_features=N_FEATURES,
    local_steps=LOCAL_STEPS,
    learning_rate=LEARNING_RATE,
    rounds=ROUNDS,
    model_size_bytes=MODEL_SIZE_BYTES,
    sample_size_bytes=SAMPLE_SIZE_BYTES,
)

datasets = make_node_datasets(
    n_nodes=N_NODES,
    n_samples=N_SAMPLES,
    n_features=N_FEATURES,
    noise_std=NOISE_STD,
    rng=np.random.default_rng(SEED),
)

cost_model = CommCostModel(config=config, n_samples=N_SAMPLES)
centralized_bytes = cost_model.centralized_bytes()

# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------

results = {}
for period in UPDATE_PERIODS:
    sim = FedAvgSimulation(config, datasets, np.random.default_rng(SEED))
    results[period] = sim.run(update_period=period)

# ---------------------------------------------------------------------------
# Stdout táblázat
# ---------------------------------------------------------------------------

HEADER = (
    f"{'update_period':>13} {'final_mse':>10} {'comm_fl_B':>10} "
    f"{'comm_central_B':>14} {'comm_reduc%':>11}"
)
SEP = "-" * len(HEADER)
print(SEP)
print(HEADER)
print(SEP)
for period in UPDATE_PERIODS:
    r = results[period]
    print(
        f"{period:>13} {r.final_mse:>10.4f} {r.total_comm_bytes:>10} "
        f"{r.centralized_bytes:>14} {r.comm_reduction_pct:>11.1f}"
    )
print()

# ---------------------------------------------------------------------------
# Ábra — 3 panel
# ---------------------------------------------------------------------------

colors = plt.cm.tab10(np.linspace(0, 0.6, len(UPDATE_PERIODS)))

fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(14, 4.5))

suptitle = (
    f"Federated Learning — update-periódus sweep\n"
    f"seed={SEED}, n_nodes={N_NODES}, n_samples={N_SAMPLES}, "
    f"rounds={ROUNDS}, local_steps={LOCAL_STEPS}"
)
fig.suptitle(suptitle, fontsize=9)

# --- Bal panel: konvergencia görbe ---
ax1.set_xlabel("Kör sorszáma")
ax1.set_ylabel("Globális MSE")
ax1.set_title("Konvergencia")
for i, period in enumerate(UPDATE_PERIODS):
    r = results[period]
    ax1.plot(
        range(1, ROUNDS + 1),
        r.round_mse,
        label=f"period={period}",
        color=colors[i],
        linewidth=1.5,
    )
ax1.legend(fontsize=7)
ax1.grid(True, alpha=0.3)

# --- Közép panel: kommunikáció-spórolás sávdiagram ---
ax2.set_xlabel("Lokális update-periódus")
ax2.set_ylabel("Kommunikáció (byte)")
ax2.set_title("FL vs. Centralizált kommunikáció")

fl_bytes = [results[p].total_comm_bytes for p in UPDATE_PERIODS]
bars = ax2.bar(
    [str(p) for p in UPDATE_PERIODS],
    fl_bytes,
    color="steelblue",
    alpha=0.8,
    label="FL kommunikáció",
)
ax2.axhline(
    centralized_bytes,
    color="darkorange",
    linestyle="--",
    linewidth=1.5,
    label=f"Centralizált ({centralized_bytes} B)",
)
# comm_reduction_pct annotáció a sávok tetején
for bar, period in zip(bars, UPDATE_PERIODS):
    pct = results[period].comm_reduction_pct
    ax2.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() + centralized_bytes * 0.01,
        f"{pct:.0f}%",
        ha="center",
        va="bottom",
        fontsize=7,
    )
ax2.legend(fontsize=7)
ax2.grid(True, alpha=0.3, axis="y")

# --- Jobb panel: kommunikáció vs. konvergencia trade-off ---
ax3.set_xlabel("FL kommunikáció (KB)")
ax3.set_ylabel("Végső MSE")
ax3.set_title("Kommunikáció–konvergencia trade-off")
for i, period in enumerate(UPDATE_PERIODS):
    r = results[period]
    x = r.total_comm_bytes / 1024
    y = r.final_mse
    ax3.scatter(x, y, color=colors[i], s=60, zorder=3)
    ax3.annotate(
        f"p={period}",
        (x, y),
        textcoords="offset points",
        xytext=(5, 3),
        fontsize=7,
        color=colors[i],
    )
ax3.grid(True, alpha=0.3)

plt.tight_layout()
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(OUT_PATH, dpi=150)
plt.close()
print(f"Ábra mentve: {OUT_PATH}")
