# wsnsim.models.edge_ai — Edge AI szenzorhálóban (7.11. hét)
# Szimulált szenzorjel-generátor és anomália-detektorok.
# Nincs sklearn — kizárólag numpy.

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


# ---------------------------------------------------------------------------
# SensorSignalGenerator
# ---------------------------------------------------------------------------

@dataclass
class SensorSignalGenerator:
    """Szimulált szenzorjel-generátor normál + spike anomáliákkal."""

    mean: float = 22.0
    std: float = 1.0
    anomaly_magnitude: float = 5.0
    anomaly_prob: float = 0.05
    rng: np.random.Generator = field(
        default_factory=lambda: np.random.default_rng(0)
    )

    def generate(self, n_steps: int) -> tuple[np.ndarray, np.ndarray]:
        """Generál n_steps mintát.

        Returns
        -------
        values : shape (n_steps,) float64
        labels : shape (n_steps,) int — 1 ha anomália, 0 ha normál
        """
        # Anomália döntés: Bernoulli(anomaly_prob)
        is_anomaly = self.rng.random(n_steps) < self.anomaly_prob
        labels = is_anomaly.astype(int)

        # Alap normál zaj
        values = self.rng.normal(self.mean, self.std, n_steps)

        # Anomális pozíciókra additív spike
        values[is_anomaly] += self.anomaly_magnitude

        return values, labels


# ---------------------------------------------------------------------------
# ZScoreDetector — online Welford-módszer
# ---------------------------------------------------------------------------

@dataclass
class ZScoreDetector:
    """Online Z-score detektor Welford futó átlag/szórás módszerrel."""

    threshold: float = 3.0

    # Belső állapot — nem részei a publikus interfésznek
    _mu: float = field(default=0.0, init=False, repr=False)
    _sigma: float = field(default=1.0, init=False, repr=False)
    _n: int = field(default=0, init=False, repr=False)
    _m2: float = field(default=0.0, init=False, repr=False)  # Welford M2

    @property
    def mu(self) -> float:
        """Futó átlag."""
        return self._mu

    @property
    def sigma(self) -> float:
        """Futó szórás (populációs, sqrt(M2/n))."""
        return self._sigma

    def update_and_detect(self, value: float) -> bool:
        """Frissíti a statisztikát, majd visszaadja, hogy anomália-e.

        Az első mintánál sigma=0, így nem tüzel (nincs referencia).
        """
        self._n += 1
        delta = value - self._mu
        self._mu += delta / self._n
        delta2 = value - self._mu
        self._m2 += delta * delta2

        if self._n < 2:
            self._sigma = 0.0
            return False

        self._sigma = (self._m2 / self._n) ** 0.5
        z = abs(value - self._mu) / max(self._sigma, 1e-9)
        return z > self.threshold

    def reset(self) -> None:
        """Belső állapot nullázása."""
        self._mu = 0.0
        self._sigma = 1.0
        self._n = 0
        self._m2 = 0.0


# ---------------------------------------------------------------------------
# EWMADetector
# ---------------------------------------------------------------------------

@dataclass
class EWMADetector:
    """Exponenciálisan súlyozott mozgóátlag (EWMA) alapú anomália-detektor."""

    alpha: float = 0.1
    threshold: float = 3.0

    _ewma: float | None = field(default=None, init=False, repr=False)
    _variance: float = field(default=1.0, init=False, repr=False)  # online EWMA szórás^2

    @property
    def ewma(self) -> float | None:
        """Aktuális EWMA érték (None ha még nem volt minta)."""
        return self._ewma

    def update_and_detect(self, value: float) -> bool:
        """EWMA frissítés és anomália-detektálás.

        Első mintánál inicializálja az EWMA-t, False-t ad vissza.
        """
        if self._ewma is None:
            self._ewma = float(value)
            self._variance = 0.0
            return False

        diff = value - self._ewma
        # Online EWMA szórás^2 frissítés
        self._variance = (1 - self.alpha) * (self._variance + self.alpha * diff ** 2)
        std_estimate = self._variance ** 0.5

        # EWMA frissítés
        self._ewma = self.alpha * value + (1 - self.alpha) * self._ewma

        return abs(diff) > self.threshold * max(std_estimate, 1e-9)

    def reset(self) -> None:
        """Belső állapot nullázása."""
        self._ewma = None
        self._variance = 1.0


# ---------------------------------------------------------------------------
# DetectionResult
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DetectionResult:
    """Detektálás eredménye: TP/FP/TN/FN számlálók és metrikák."""

    tp: int
    fp: int
    tn: int
    fn: int

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.tn + self.fn

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        denom = p + r
        return 2 * p * r / denom if denom > 0 else 0.0

    @property
    def fpr(self) -> float:
        """False positive rate = FP / (FP + TN)."""
        denom = self.fp + self.tn
        return self.fp / denom if denom > 0 else 0.0

    @property
    def comm_saved_pct(self) -> float:
        """Kommunikáció-megtakarítás %-ban.

        Küldés csak akkor történik, ha a detektor tüzel (TP vagy FP).
        TN + FN esetén a csomag elnyomva — nem megy el.
        """
        if self.total == 0:
            return 0.0
        return (self.tn + self.fn) / self.total * 100.0


# ---------------------------------------------------------------------------
# evaluate — segédfüggvény
# ---------------------------------------------------------------------------

def evaluate(
    values: np.ndarray,
    labels: np.ndarray,
    detector,
) -> DetectionResult:
    """Kiértékeli a detektort egy ismert sorozaton.

    Meghívja a detektor reset()-jét előtte, majd végigmegy a sorozaton
    update_and_detect()-tel és összeszámolja a TP/FP/TN/FN értékeket.

    Parameters
    ----------
    values  : 1D float array
    labels  : 1D int array, 1 = valódi anomália, 0 = normál
    detector: ZScoreDetector vagy EWMADetector (duck typing)
    """
    detector.reset()
    tp = fp = tn = fn = 0
    for v, lbl in zip(values, labels):
        fired = detector.update_and_detect(float(v))
        is_anomaly = int(lbl) == 1
        if fired and is_anomaly:
            tp += 1
        elif fired and not is_anomaly:
            fp += 1
        elif not fired and not is_anomaly:
            tn += 1
        else:
            fn += 1
    return DetectionResult(tp=tp, fp=fp, tn=tn, fn=fn)
