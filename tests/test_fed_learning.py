# tests/test_fed_learning.py — 7.12. hét: Federated Learning WSN-ben

import math

import numpy as np
import pytest

from wsnsim.models.fed_learning import (
    CommCostModel,
    FedAvgConfig,
    FedAvgResult,
    FedAvgSimulation,
    NodeDataset,
    make_node_datasets,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _small_config(**kwargs) -> FedAvgConfig:
    defaults = dict(
        n_nodes=5,
        n_features=3,
        local_steps=3,
        learning_rate=0.05,
        rounds=10,
        model_size_bytes=64,
        sample_size_bytes=12,
    )
    defaults.update(kwargs)
    return FedAvgConfig(**defaults)


def _small_datasets(config: FedAvgConfig, n_samples: int = 50) -> list[NodeDataset]:
    return make_node_datasets(
        n_nodes=config.n_nodes,
        n_samples=n_samples,
        n_features=config.n_features,
        noise_std=0.1,
        rng=np.random.default_rng(42),
    )


# ---------------------------------------------------------------------------
# TestFedAvgConfig
# ---------------------------------------------------------------------------

class TestFedAvgConfig:
    def test_default_values(self):
        cfg = FedAvgConfig()
        assert cfg.n_nodes == 10
        assert cfg.rounds == 30
        assert cfg.n_features == 4
        assert cfg.local_steps == 5
        assert cfg.learning_rate == 0.01

    def test_frozen_raises_on_assignment(self):
        cfg = FedAvgConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.n_nodes = 99  # type: ignore

    def test_model_size_bytes_positive(self):
        cfg = FedAvgConfig(model_size_bytes=256)
        assert cfg.model_size_bytes > 0

    def test_learning_rate_positive(self):
        cfg = FedAvgConfig(learning_rate=0.001)
        assert cfg.learning_rate > 0

    def test_equality(self):
        cfg1 = FedAvgConfig(n_nodes=5, rounds=20)
        cfg2 = FedAvgConfig(n_nodes=5, rounds=20)
        assert cfg1 == cfg2
        cfg3 = FedAvgConfig(n_nodes=6, rounds=20)
        assert cfg1 != cfg3


# ---------------------------------------------------------------------------
# TestMakeNodeDatasets
# ---------------------------------------------------------------------------

class TestMakeNodeDatasets:
    def test_list_length(self):
        ds = make_node_datasets(7, 30, 3, 0.1, np.random.default_rng(0))
        assert len(ds) == 7

    def test_X_shape(self):
        ds = make_node_datasets(4, 20, 5, 0.1, np.random.default_rng(1))
        for d in ds:
            assert d.X.shape == (20, 5)

    def test_y_shape(self):
        ds = make_node_datasets(4, 20, 5, 0.1, np.random.default_rng(2))
        for d in ds:
            assert d.y.shape == (20,)

    def test_different_nodes_have_different_data(self):
        ds = make_node_datasets(3, 50, 4, 0.1, np.random.default_rng(3))
        # Legalább két node adatpontjai különböznek
        assert not np.allclose(ds[0].X, ds[1].X)

    def test_reproducibility(self):
        ds1 = make_node_datasets(3, 30, 4, 0.1, np.random.default_rng(42))
        ds2 = make_node_datasets(3, 30, 4, 0.1, np.random.default_rng(42))
        for a, b in zip(ds1, ds2):
            np.testing.assert_array_equal(a.X, b.X)
            np.testing.assert_array_equal(a.y, b.y)


# ---------------------------------------------------------------------------
# TestFedAvgSimulationConvergence
# ---------------------------------------------------------------------------

class TestFedAvgSimulationConvergence:
    def _sim(self, **kwargs):
        cfg = _small_config(**kwargs)
        ds = _small_datasets(cfg, n_samples=100)
        return FedAvgSimulation(cfg, ds, np.random.default_rng(42))

    def test_convergence_final_mse_smaller(self):
        """update_period=1: final_mse < round_mse[0]."""
        sim = self._sim(rounds=20, local_steps=5, learning_rate=0.05)
        result = sim.run(update_period=1)
        assert result.final_mse < result.round_mse[0]

    def test_round_mse_length(self):
        """round_mse hossza == rounds."""
        cfg = _small_config(rounds=15)
        ds = _small_datasets(cfg)
        sim = FedAvgSimulation(cfg, ds, np.random.default_rng(0))
        result = sim.run(update_period=1)
        assert len(result.round_mse) == 15

    def test_single_aggregation_comm_bytes(self):
        """update_period=rounds → pontosan 1 aggregálás (a végén)."""
        cfg = _small_config(rounds=10, n_nodes=5, model_size_bytes=64)
        ds = _small_datasets(cfg)
        sim = FedAvgSimulation(cfg, ds, np.random.default_rng(0))
        result = sim.run(update_period=10)
        # 1 aggregálás × 2 irány × 64 byte × 5 node = 640 byte
        expected = 2 * 64 * 5 * 1
        assert result.total_comm_bytes == expected

    def test_all_rounds_aggregation_comm_bytes(self):
        """update_period=1 → minden körben aggregálás."""
        cfg = _small_config(rounds=10, n_nodes=5, model_size_bytes=64)
        ds = _small_datasets(cfg)
        sim = FedAvgSimulation(cfg, ds, np.random.default_rng(0))
        result = sim.run(update_period=1)
        expected = 2 * 64 * 5 * 10
        assert result.total_comm_bytes == expected

    def test_comm_reduction_pct_in_range(self):
        """comm_reduction_pct ∈ [0, 100]."""
        cfg = _small_config(rounds=10, n_nodes=5)
        ds = _small_datasets(cfg, n_samples=50)
        sim = FedAvgSimulation(cfg, ds, np.random.default_rng(0))
        result = sim.run(update_period=1)
        assert 0.0 <= result.comm_reduction_pct <= 100.0


# ---------------------------------------------------------------------------
# TestCommCostModel
# ---------------------------------------------------------------------------

class TestCommCostModel:
    def _model(self, **cfg_kwargs):
        cfg = FedAvgConfig(**cfg_kwargs)
        return CommCostModel(config=cfg, n_samples=200)

    def test_federated_bytes_manual(self):
        """n_nodes=10, model_size_bytes=128, rounds=30, update_period=1 → 2×128×10×30=76800."""
        m = self._model(n_nodes=10, model_size_bytes=128, rounds=30)
        assert m.federated_bytes(update_period=1) == 2 * 128 * 10 * 30

    def test_centralized_bytes_manual(self):
        """n_nodes=10, n_samples=200, sample_size_bytes=16 → 10×200×16=32000."""
        m = CommCostModel(
            config=FedAvgConfig(n_nodes=10, sample_size_bytes=16),
            n_samples=200,
        )
        assert m.centralized_bytes() == 10 * 200 * 16

    def test_fl_cheaper_than_centralized_small_model(self):
        """update_period=rounds (1 aggregálás) FL olcsóbb mint nyers adat küldése."""
        cfg = FedAvgConfig(n_nodes=10, model_size_bytes=64, rounds=30, sample_size_bytes=16)
        m = CommCostModel(config=cfg, n_samples=500)
        assert m.federated_bytes(update_period=30) < m.centralized_bytes()

    def test_comm_reduction_pct_in_range(self):
        m = self._model(n_nodes=5, model_size_bytes=64, rounds=20, sample_size_bytes=16)
        pct = m.comm_reduction_pct(update_period=1)
        assert 0.0 <= pct <= 100.0

    def test_federated_bytes_monotone_with_period(self):
        """Nagyobb update_period → kevesebb aggregálás → kevesebb byte."""
        m = self._model(n_nodes=10, model_size_bytes=128, rounds=30)
        prev = m.federated_bytes(1)
        for period in [2, 5, 10, 15, 30]:
            curr = m.federated_bytes(period)
            assert curr <= prev
            prev = curr


# ---------------------------------------------------------------------------
# TestFedAvgResult
# ---------------------------------------------------------------------------

class TestFedAvgResult:
    def _result(self, **kwargs):
        defaults = dict(
            round_mse=[5.0, 3.0, 2.0, 1.5],
            final_mse=1.5,
            total_comm_bytes=1000,
            centralized_bytes=5000,
            comm_reduction_pct=80.0,
        )
        defaults.update(kwargs)
        return FedAvgResult(**defaults)

    def test_comm_reduction_not_negative(self):
        """comm_reduction_pct soha nem negatív (clip)."""
        r = self._result(comm_reduction_pct=0.0)
        assert r.comm_reduction_pct >= 0.0

    def test_final_mse_equals_last_round(self):
        r = self._result(round_mse=[5.0, 3.0, 1.5], final_mse=1.5)
        assert r.final_mse == r.round_mse[-1]

    def test_total_comm_bytes_positive(self):
        r = self._result(total_comm_bytes=512)
        assert r.total_comm_bytes > 0

    def test_centralized_bytes_positive(self):
        r = self._result(centralized_bytes=8000)
        assert r.centralized_bytes > 0

    def test_frozen_raises_on_modification(self):
        r = self._result()
        with pytest.raises((AttributeError, TypeError)):
            r.final_mse = 0.0  # type: ignore
