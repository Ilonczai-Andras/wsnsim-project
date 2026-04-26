"""experiments/edge_ai_comm_saving.py — 7.11. hét: Edge AI comm-saving sweep.

Stdout táblázat + reports/figures/edge_ai_comm_saving.png
"""

import pathlib

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from wsnsim.models.edge_ai import (
    SensorSignalGenerator,
    ZScoreDetector,
    EWMADetector,
    evaluate,
)

# ---------------------------------------------------------------------------
# Paraméterek
# ---------------------------------------------------------------------------

SEED = 42
N_STEPS = 2000
MEAN = 22.0
STD = 1.0
ANOMALY_MAGNITUDE = 6.0
ANOMALY_PROB = 0.05

ZSCORE_THRESHOLDS = np.linspace(1.0, 5.0, 20)
EWMA_THRESHOLDS = np.linspace(0.5, 4.0, 20)
EWMA_ALPHA = 0.1

OUT_PATH = pathlib.Path(__file__).parent.parent / "reports" / "figures" / "edge_ai_comm_saving.png"

# ---------------------------------------------------------------------------
# Adatgenerálás
# ---------------------------------------------------------------------------

gen = SensorSignalGenerator(
    mean=MEAN,
    std=STD,
    anomaly_magnitude=ANOMALY_MAGNITUDE,
    anomaly_prob=ANOMALY_PROB,
    rng=np.random.default_rng(SEED),
)
values, labels = gen.generate(N_STEPS)

n_anomaly = int(labels.sum())
n_normal = N_STEPS - n_anomaly
print(f"Generált sorozat: n={N_STEPS}, anomáliák={n_anomaly} ({n_anomaly/N_STEPS*100:.1f}%), normál={n_normal}")
print()

# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------

def run_sweep(detector_factory, thresholds, label):
    results = []
    for thr in thresholds:
        det = detector_factory(thr)
        r = evaluate(values, labels, det)
        results.append((thr, r))
    return results


zscore_results = run_sweep(lambda t: ZScoreDetector(threshold=t), ZSCORE_THRESHOLDS, "ZScore")
ewma_results = run_sweep(lambda t: EWMADetector(alpha=EWMA_ALPHA, threshold=t), EWMA_THRESHOLDS, "EWMA")

# ---------------------------------------------------------------------------
# Stdout táblázat
# ---------------------------------------------------------------------------

HEADER = f"{'Detektor':<10} {'Küszöb':>7} {'TP':>5} {'FP':>5} {'FN':>5} {'Recall%':>8} {'FPR%':>7} {'CommSaved%':>11}"
SEP = "-" * len(HEADER)


def print_table(results, name):
    print(SEP)
    print(HEADER)
    print(SEP)
    for thr, r in results:
        print(
            f"{name:<10} {thr:>7.3f} {r.tp:>5} {r.fp:>5} {r.fn:>5}"
            f" {r.recall*100:>8.1f} {r.fpr*100:>7.1f} {r.comm_saved_pct:>11.1f}"
        )
    print()


print_table(zscore_results, "ZScore")
print_table(ewma_results, "EWMA")

# ---------------------------------------------------------------------------
# Annotálandó pontok (3 küszöb egyenletesen)
# ---------------------------------------------------------------------------

def annotation_indices(n, count=3):
    return [int(round((n - 1) * i / (count - 1))) for i in range(count)]


# ---------------------------------------------------------------------------
# Ábra — 2 panel
# ---------------------------------------------------------------------------

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

suptitle = (
    f"Edge AI kommunikáció-spórolás sweep\n"
    f"seed={SEED}, n={N_STEPS}, anomaly_prob={ANOMALY_PROB}, anomaly_magnitude={ANOMALY_MAGNITUDE}"
)
fig.suptitle(suptitle, fontsize=10)

# --- Bal panel: comm_saved% vs. FPR% (ROC-szerű) ---
ax1.set_xlabel("Hamis pozitív arány (FPR %)")
ax1.set_ylabel("Kommunikáció-megtakarítás (%)")
ax1.set_title("Comm-saving vs. FPR")

for results, name, color, thresholds in [
    (zscore_results, "ZScore", "steelblue", ZSCORE_THRESHOLDS),
    (ewma_results, "EWMA (α=0.1)", "darkorange", EWMA_THRESHOLDS),
]:
    fprs = [r.fpr * 100 for _, r in results]
    saves = [r.comm_saved_pct for _, r in results]
    ax1.plot(fprs, saves, "o-", color=color, label=name, markersize=3)

    # 3 annotált pont
    ann_idx = annotation_indices(len(results))
    for idx in ann_idx:
        thr, r = results[idx]
        ax1.annotate(
            f"{thr:.1f}",
            (r.fpr * 100, r.comm_saved_pct),
            textcoords="offset points",
            xytext=(4, 4),
            fontsize=7,
            color=color,
        )

ax1.legend()
ax1.grid(True, alpha=0.3)

# --- Jobb panel: Recall% vs. comm_saved% ---
ax2.set_xlabel("Visszahívás (Recall %)")
ax2.set_ylabel("Kommunikáció-megtakarítás (%)")
ax2.set_title("Recall vs. Comm-saving")

for results, name, color in [
    (zscore_results, "ZScore", "steelblue"),
    (ewma_results, "EWMA (α=0.1)", "darkorange"),
]:
    recalls = [r.recall * 100 for _, r in results]
    saves = [r.comm_saved_pct for _, r in results]
    ax2.plot(recalls, saves, "o-", color=color, label=name, markersize=3)

ax2.legend()
ax2.grid(True, alpha=0.3)

plt.tight_layout()
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(OUT_PATH, dpi=150)
plt.close()
print(f"Ábra mentve: {OUT_PATH}")
