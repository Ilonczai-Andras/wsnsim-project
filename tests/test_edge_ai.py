# tests/test_edge_ai.py — 7.11. hét: Edge AI szenzorhálóban

import numpy as np
import pytest

from wsnsim.models.edge_ai import (
    DetectionResult,
    EWMADetector,
    SensorSignalGenerator,
    ZScoreDetector,
    evaluate,
)


# ---------------------------------------------------------------------------
# TestSensorSignalGenerator
# ---------------------------------------------------------------------------

class TestSensorSignalGenerator:
    def test_output_shapes(self):
        gen = SensorSignalGenerator(rng=np.random.default_rng(1))
        values, labels = gen.generate(100)
        assert values.shape == (100,)
        assert labels.shape == (100,)

    def test_labels_binary(self):
        gen = SensorSignalGenerator(rng=np.random.default_rng(2))
        _, labels = gen.generate(500)
        assert set(labels).issubset({0, 1})

    def test_anomaly_rate_binomial(self):
        """seed=0, n=10000 → anomália arány 0.05 ± 0.01 (binomiális ellenőrzés)."""
        gen = SensorSignalGenerator(anomaly_prob=0.05, rng=np.random.default_rng(0))
        _, labels = gen.generate(10_000)
        rate = labels.mean()
        assert abs(rate - 0.05) < 0.01, f"anomália arány: {rate:.4f}"

    def test_anomaly_values_elevated(self):
        """Anomáliapontokon az érték > mean + anomaly_magnitude / 2."""
        gen = SensorSignalGenerator(
            mean=22.0, std=0.01, anomaly_magnitude=5.0, rng=np.random.default_rng(7)
        )
        values, labels = gen.generate(2000)
        anomaly_vals = values[labels == 1]
        if len(anomaly_vals) > 0:
            assert np.all(anomaly_vals > 22.0 + 5.0 / 2)

    def test_reproducibility(self):
        """Azonos seed → azonos sorozat."""
        gen1 = SensorSignalGenerator(rng=np.random.default_rng(42))
        gen2 = SensorSignalGenerator(rng=np.random.default_rng(42))
        v1, l1 = gen1.generate(200)
        v2, l2 = gen2.generate(200)
        np.testing.assert_array_equal(v1, v2)
        np.testing.assert_array_equal(l1, l2)


# ---------------------------------------------------------------------------
# TestZScoreDetector
# ---------------------------------------------------------------------------

class TestZScoreDetector:
    def test_first_sample_no_fire(self):
        """Friss detektor: az első mintán sigma=0, nem tüzel."""
        det = ZScoreDetector(threshold=3.0)
        assert det.update_and_detect(22.0) is False

    def test_fires_on_large_deviation(self):
        """1000 normál minta után 5×std eltérés tüzel."""
        det = ZScoreDetector(threshold=3.0)
        rng = np.random.default_rng(0)
        for _ in range(1000):
            det.update_and_detect(float(rng.normal(0.0, 1.0)))
        # 5 sigma eltérés szignifikánsan > threshold=3
        assert det.update_and_detect(det.mu + 5 * det.sigma) is True

    def test_normal_sample_no_fire(self):
        """Normál tartományú minta nem tüzel betanítás után."""
        det = ZScoreDetector(threshold=3.0)
        rng = np.random.default_rng(1)
        for _ in range(500):
            det.update_and_detect(float(rng.normal(0.0, 1.0)))
        # Pontosan az átlag nem tüzel
        assert det.update_and_detect(det.mu) is False

    def test_reset_clears_state(self):
        """reset() után mu=0, n=0 és az állapot üres."""
        det = ZScoreDetector()
        for v in [1.0, 2.0, 3.0]:
            det.update_and_detect(v)
        det.reset()
        assert det.mu == 0.0
        assert det._n == 0

    def test_welford_mu_three_samples(self):
        """[1, 2, 3] → mu ≈ 2.0 (tol 1e-9)."""
        det = ZScoreDetector(threshold=100.0)
        for v in [1.0, 2.0, 3.0]:
            det.update_and_detect(v)
        assert abs(det.mu - 2.0) < 1e-9


# ---------------------------------------------------------------------------
# TestEWMADetector
# ---------------------------------------------------------------------------

class TestEWMADetector:
    def test_first_sample_initializes_ewma(self):
        """Első minta után _ewma == value, nem tüzel."""
        det = EWMADetector()
        fired = det.update_and_detect(22.0)
        assert det.ewma == 22.0
        assert fired is False

    def test_small_deviation_no_fire(self):
        """Kis eltérés nem tüzel betanított detektor esetén."""
        det = EWMADetector(alpha=0.1, threshold=3.0)
        rng = np.random.default_rng(9)
        # Warmup: 200 minta — varianciabecslés stabilizálódik
        for _ in range(200):
            det.update_and_detect(float(rng.normal(22.0, 1.0)))
        # 0.1 sigma nagyságrendű eltérés nem tüzel
        assert det.update_and_detect(22.1) is False

    def test_large_spike_fires(self):
        """Nagy spike (mean + 20×std) tüzel betanítás után."""
        det = EWMADetector(alpha=0.1, threshold=3.0)
        rng = np.random.default_rng(5)
        for _ in range(200):
            det.update_and_detect(float(rng.normal(22.0, 1.0)))
        assert det.update_and_detect(22.0 + 20.0) is True

    def test_reset_clears_ewma(self):
        """reset() után _ewma is None."""
        det = EWMADetector()
        det.update_and_detect(10.0)
        det.reset()
        assert det.ewma is None

    def test_alpha_half_two_steps(self):
        """alpha=0.5 esetén kézi EWMA képlettel 2 lépés ellenőrzése."""
        det = EWMADetector(alpha=0.5, threshold=100.0)
        det.update_and_detect(10.0)   # ewma = 10.0
        det.update_and_detect(20.0)   # ewma = 0.5*20 + 0.5*10 = 15.0
        assert abs(det.ewma - 15.0) < 1e-9


# ---------------------------------------------------------------------------
# TestDetectionResult
# ---------------------------------------------------------------------------

class TestDetectionResult:
    def _result(self, tp=10, fp=5, tn=80, fn=5):
        return DetectionResult(tp=tp, fp=fp, tn=tn, fn=fn)

    def test_total(self):
        r = self._result(tp=10, fp=5, tn=80, fn=5)
        assert r.total == 100

    def test_comm_saved_pct(self):
        """comm_saved_pct = (tn + fn) / total * 100."""
        r = self._result(tp=10, fp=5, tn=80, fn=5)
        expected = (80 + 5) / 100 * 100
        assert abs(r.comm_saved_pct - expected) < 1e-9

    def test_precision_recall_f1(self):
        r = self._result(tp=10, fp=5, tn=80, fn=5)
        assert abs(r.precision - 10 / 15) < 1e-9
        assert abs(r.recall - 10 / 15) < 1e-9
        p, rec = r.precision, r.recall
        expected_f1 = 2 * p * rec / (p + rec)
        assert abs(r.f1 - expected_f1) < 1e-9

    def test_precision_no_zerodivision_when_no_positives(self):
        """tp=0, fp=0 → precision=0.0 (ne dobjon ZeroDivisionError)."""
        r = DetectionResult(tp=0, fp=0, tn=90, fn=10)
        assert r.precision == 0.0

    def test_fpr(self):
        """fpr = fp / (fp + tn)."""
        r = self._result(tp=10, fp=5, tn=80, fn=5)
        assert abs(r.fpr - 5 / 85) < 1e-9


# ---------------------------------------------------------------------------
# TestEvaluate
# ---------------------------------------------------------------------------

class TestEvaluate:
    def _known_sequence(self):
        """60 elem: 50 normál (22.0) warmup, majd 2 óriási spike, majd 8 normál."""
        values = np.array([22.0] * 60, dtype=float)
        labels = np.zeros(60, dtype=int)
        # Anomáliák az 50. és 55. pozícióban — Welford már stabil ekkorra
        values[50] = 200.0
        values[55] = 200.0
        labels[50] = 1
        labels[55] = 1
        return values, labels

    def test_zscore_known_sequence(self):
        """ZScoreDetector ismert sorozaton: warmup után óriási spike → TP >= 1."""
        values, labels = self._known_sequence()
        det = ZScoreDetector(threshold=3.0)
        result = evaluate(values, labels, det)
        # Összesen 60 minta, total helyes
        assert result.total == 60
        # Legalább az egyik óriási spike-ot elkapja (TP >= 1)
        assert result.tp >= 1
        # Nincs negatív szám
        assert result.fp >= 0 and result.tn >= 0 and result.fn >= 0

    def test_repeated_evaluate_same_result(self):
        """Két egymást követő evaluate() hívás azonos eredményt ad (reset fut)."""
        values, labels = self._known_sequence()
        det = ZScoreDetector(threshold=3.0)
        r1 = evaluate(values, labels, det)
        r2 = evaluate(values, labels, det)
        assert r1 == r2

    def test_ewma_evaluate_interface(self):
        """EWMADetector is átmegy az evaluate() interfészen (duck typing)."""
        values, labels = self._known_sequence()
        det = EWMADetector(alpha=0.1, threshold=3.0)
        result = evaluate(values, labels, det)
        assert result.total == 60

    def test_all_normal_no_tp_fn(self):
        """Ha nincs anomália a sorozatban, TP=0 és FN=0."""
        values = np.ones(50) * 22.0
        labels = np.zeros(50, dtype=int)
        det = ZScoreDetector(threshold=3.0)
        result = evaluate(values, labels, det)
        assert result.tp == 0
        assert result.fn == 0

    def test_counters_sum_to_total(self):
        """TP + FP + TN + FN == len(values)."""
        values, labels = self._known_sequence()
        det = EWMADetector()
        result = evaluate(values, labels, det)
        assert result.tp + result.fp + result.tn + result.fn == len(values)
