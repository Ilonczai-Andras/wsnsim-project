# wsnsim.models.fed_learning — Federated Learning WSN-ben (7.12. hét)
# FedAvg algoritmus szimulációja, kommunikációs költségmodell.
# Nincs sklearn/torch/tensorflow — kizárólag numpy.

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


# ---------------------------------------------------------------------------
# FedAvgConfig
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FedAvgConfig:
    """Federated averaging konfigurációs paraméterek."""

    n_nodes: int = 10
    n_features: int = 4
    local_steps: int = 5
    learning_rate: float = 0.01
    rounds: int = 30
    model_size_bytes: int = 128   # modellsúlyok fix byte-mérete
    sample_size_bytes: int = 16   # egy minta ≈ n_features × 4 byte (float32)


# ---------------------------------------------------------------------------
# NodeDataset
# ---------------------------------------------------------------------------

@dataclass
class NodeDataset:
    """Egy szenzorcsomópont lokális adathalmazának konténere."""

    node_id: int
    X: np.ndarray   # shape [n_samples, n_features]
    y: np.ndarray   # shape [n_samples]


def make_node_datasets(
    n_nodes: int,
    n_samples: int,
    n_features: int,
    noise_std: float,
    rng: np.random.Generator,
) -> list[NodeDataset]:
    """Szintetikus IID lineáris regressziós adatot generál csomópontonként.

    Minden node ugyanazt a `true_w` súlyvektort kapja, de különböző X, y mintákat.
    """
    true_w = rng.standard_normal(n_features)
    datasets: list[NodeDataset] = []
    for node_id in range(n_nodes):
        X = rng.standard_normal((n_samples, n_features))
        noise = rng.normal(0.0, noise_std, n_samples)
        y = X @ true_w + noise
        datasets.append(NodeDataset(node_id=node_id, X=X, y=y))
    return datasets


# ---------------------------------------------------------------------------
# FedAvgResult
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FedAvgResult:
    """Egy FedAvg futtatás eredménye."""

    round_mse: list[float]
    final_mse: float
    total_comm_bytes: int
    centralized_bytes: int
    comm_reduction_pct: float   # clipelt 0–100


# ---------------------------------------------------------------------------
# FedAvgSimulation
# ---------------------------------------------------------------------------

class FedAvgSimulation:
    """FedAvg szimulációs motor.

    Parameters
    ----------
    config   : FedAvgConfig
    datasets : list[NodeDataset] — hossza config.n_nodes
    rng      : np.random.Generator — reprodukálhatósághoz
    """

    def __init__(
        self,
        config: FedAvgConfig,
        datasets: list[NodeDataset],
        rng: np.random.Generator,
    ) -> None:
        self.config = config
        self.datasets = datasets
        self.rng = rng
        # Globális súlyvektor nullákkal inicializálva
        self._global_w = np.zeros(config.n_features)

    # ------------------------------------------------------------------
    # Publikus

    def run(self, update_period: int = 1) -> FedAvgResult:
        """Lefuttatja a FedAvg szimulációt.

        Parameters
        ----------
        update_period : int
            Minden update_period-odik körben történik aggregálás.
        """
        cfg = self.config
        # Friss lokális súlyok (másolat per node)
        local_weights = [np.zeros(cfg.n_features) for _ in self.datasets]
        global_w = np.zeros(cfg.n_features)

        round_mse: list[float] = []
        total_comm = 0
        n_samples_list = [ds.y.shape[0] for ds in self.datasets]

        for r in range(cfg.rounds):
            # Lokális update minden csomóponton
            for i, ds in enumerate(self.datasets):
                local_weights[i] = self._local_update(global_w.copy(), ds)

            # Aggregálás update_period-onként (0-indexelt: r+1 a "hányadik kör")
            if (r + 1) % update_period == 0 or (r + 1) == cfg.rounds:
                global_w = np.average(
                    local_weights, axis=0, weights=n_samples_list
                )
                # Upload + download: minden node küld és kap
                total_comm += 2 * cfg.model_size_bytes * cfg.n_nodes

            # MSE mérés a frissített globális súlyokkal
            round_mse.append(self._global_mse(global_w))

        # Centralizált baseline: összes nyers adat egyszer
        n_samples = self.datasets[0].y.shape[0]
        centralized = cfg.n_nodes * n_samples * cfg.sample_size_bytes

        reduction = (1.0 - total_comm / centralized) * 100.0
        reduction = float(np.clip(reduction, 0.0, 100.0))

        return FedAvgResult(
            round_mse=round_mse,
            final_mse=round_mse[-1],
            total_comm_bytes=total_comm,
            centralized_bytes=centralized,
            comm_reduction_pct=reduction,
        )

    # ------------------------------------------------------------------
    # Privát

    def _local_update(self, w: np.ndarray, dataset: NodeDataset) -> np.ndarray:
        """local_steps lépés SGD (MSE loss) a csomópont lokális adatán."""
        lr = self.config.learning_rate
        X, y = dataset.X, dataset.y
        n = y.shape[0]
        for _ in range(self.config.local_steps):
            grad = (2.0 / n) * X.T @ (X @ w - y)
            w = w - lr * grad
        return w

    def _global_mse(self, w: np.ndarray) -> float:
        """MSE az összes csomópont adatán a globális súlyvektorral."""
        total_sq = 0.0
        total_n = 0
        for ds in self.datasets:
            residuals = ds.X @ w - ds.y
            total_sq += float(np.sum(residuals ** 2))
            total_n += ds.y.shape[0]
        return total_sq / total_n if total_n > 0 else 0.0


# ---------------------------------------------------------------------------
# CommCostModel
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CommCostModel:
    """Analitikus kommunikációs költségmodell FL vs. centralizált tanítás."""

    config: FedAvgConfig
    n_samples: int

    def federated_bytes(self, update_period: int) -> int:
        """FL kommunikáció: 2 × model_size_bytes × n_nodes × aggregálások száma."""
        n_aggregations = math.ceil(self.config.rounds / update_period)
        return (
            2
            * self.config.model_size_bytes
            * self.config.n_nodes
            * n_aggregations
        )

    def centralized_bytes(self) -> int:
        """Centralizált baseline: összes nyers adat egyszer elküldve."""
        return self.config.n_nodes * self.n_samples * self.config.sample_size_bytes

    def comm_reduction_pct(self, update_period: int) -> float:
        """Kommunikáció-megtakarítás %-ban (clipelt 0–100)."""
        fl = self.federated_bytes(update_period)
        cent = self.centralized_bytes()
        if cent == 0:
            return 0.0
        reduction = (1.0 - fl / cent) * 100.0
        return float(np.clip(reduction, 0.0, 100.0))
