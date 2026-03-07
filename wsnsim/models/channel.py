"""LogDistanceChannel — log-normal shadowing csatornamodell.

A modell az IEEE 802.15.4 / WSN irodalomban bevett log-distance + log-normal
shadowing formát követi [Seidel & Rappaport, 1992]:

.. math::

    PL(d) = PL_0 + 10 \\cdot n \\cdot \\log_{10}\\!\\left(\\frac{d}{d_0}\\right)
             + X_\\sigma

ahol :math:`X_\\sigma \\sim \\mathcal{N}(0, \\sigma^2)` a shadowing komponens (dB),
:math:`n` a path loss kitevő, :math:`d_0` a referencia-távolság, :math:`PL_0` a
referencia-távolságon mért path loss.

BER-ből PRR levezetés (BPSK-AWGN közelítés):

.. math::

    \\text{BER} = \\frac{1}{2}\\,\\operatorname{erfc}\\!\\left(\\sqrt{\\text{SNR}_{\\text{lin}}}\\right)

.. math::

    \\text{PER} = 1 - (1 - \\text{BER})^{N_{\\text{bits}}}

.. math::

    \\text{PRR} = 1 - \\text{PER}

Hivatkozások:
    [1] Seidel & Rappaport (1992) — 914 MHz path loss and shadowing.
    [2] Dargie & Poellabauer (2010) — WSN rádiós csatorna alapok.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class LogDistanceChannel:
    """Log-distance + log-normal shadowing csatornamodell.

    Alapértelmezett paraméterek tipikus beltéri IEEE 802.15.4 (2.4 GHz)
    környezetre vonatkoznak.

    Args:
        n:           Path loss kitevő (dimenzió nélküli).
                     Szabadtér: 2.0, beltér: 2.5–4.0. Default: 2.7.
        pl0_db:      Path loss a referencia-távolságon (dB). Default: 55.0 dB
                     (1 m, 2.4 GHz, izotróp antenna közelítés).
        d0_m:        Referencia-távolság (m). Default: 1.0 m.
        sigma_db:    Shadowing szórása (dB). 0 = nincs shadowing. Default: 4.0 dB.
        tx_power_dbm: Adó teljesítmény (dBm). Default: 0.0 dBm (CC2420 max).
        noise_floor_dbm: Zajszint (dBm). Default: -95.0 dBm.
        rng:         NumPy véletlenszám-generátor a shadowing zajhoz.
                     Ha None, egy seed nélküli generátor jön létre.

    Example:
        >>> import numpy as np
        >>> ch = LogDistanceChannel(sigma_db=0.0, rng=np.random.default_rng(0))
        >>> ch.path_loss_db(10.0)   # d0=1m → 55 + 10*2.7*log10(10) = 55+27=82 dB
        82.0
        >>> ch.prr(10.0, n_bits=256) > 0.9  # közel a küszöbhöz
        True
    """

    n: float = 2.7
    pl0_db: float = 55.0
    d0_m: float = 1.0
    sigma_db: float = 4.0
    tx_power_dbm: float = 0.0
    noise_floor_dbm: float = -95.0
    rng: Optional[np.random.Generator] = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if self.d0_m <= 0:
            raise ValueError(f"d0_m pozitív kell legyen, kapott: {self.d0_m}")
        if self.n <= 0:
            raise ValueError(f"n pozitív kell legyen, kapott: {self.n}")
        if self.rng is None:
            object.__setattr__(self, "rng", np.random.default_rng())

    # ---------------------------------------------------------------------------
    # Alapmodellek
    # ---------------------------------------------------------------------------

    def path_loss_db(self, d_m: float, shadowing: bool = False) -> float:
        """Kiszámítja a path loss értékét dB-ben az adott távolságra.

        Args:
            d_m:       Távolság méterben (d ≥ d0; ha d < d0, d0-ra klippelődik).
            shadowing: Ha True, log-normal shadowing zajt ad hozzá.

        Returns:
            Path loss [dB].
        """
        d_eff = max(float(d_m), self.d0_m)
        pl = self.pl0_db + 10.0 * self.n * math.log10(d_eff / self.d0_m)
        if shadowing and self.sigma_db > 0.0:
            pl += float(self.rng.normal(0.0, self.sigma_db))  # type: ignore[union-attr]
        return pl

    def rssi_dbm(self, d_m: float, shadowing: bool = False) -> float:
        """Vett jelerősség (RSSI) dBm-ben.

        .. math::  RSSI(d) = P_{tx} - PL(d)

        Args:
            d_m:       Távolság méterben.
            shadowing: Ha True, shadowing zaját hozzáadja.

        Returns:
            RSSI [dBm].
        """
        return self.tx_power_dbm - self.path_loss_db(d_m, shadowing=shadowing)

    def snr_db(self, d_m: float, shadowing: bool = False) -> float:
        """Jel-zaj viszony (SNR) dB-ben.

        .. math::  SNR(d) = RSSI(d) - N_{floor}

        Args:
            d_m:       Távolság méterben.
            shadowing: Ha True, shadowing zaját hozzáadja.

        Returns:
            SNR [dB].
        """
        return self.rssi_dbm(d_m, shadowing=shadowing) - self.noise_floor_dbm

    # ---------------------------------------------------------------------------
    # BER → PER → PRR
    # ---------------------------------------------------------------------------

    def ber(self, d_m: float, shadowing: bool = False) -> float:
        """Bit Error Rate (BPSK-AWGN közelítés).

        .. math::  BER = \\frac{1}{2}\\,\\operatorname{erfc}(\\sqrt{SNR_{lin}})

        Args:
            d_m:       Távolság méterben.
            shadowing: Ha True, shadowing zaját hozzáadja.

        Returns:
            BER ∈ [0, 0.5].
        """
        snr_db_val = self.snr_db(d_m, shadowing=shadowing)
        snr_lin = 10.0 ** (snr_db_val / 10.0)
        # erfc(sqrt(max(0,snr))) — negatív SNR esetén BER → 0.5
        ber_val = 0.5 * math.erfc(math.sqrt(max(0.0, snr_lin)))
        return float(np.clip(ber_val, 0.0, 0.5))

    def per(self, d_m: float, n_bits: int = 256, shadowing: bool = False) -> float:
        """Packet Error Rate.

        .. math::  PER = 1 - (1 - BER)^{N_{bits}}

        Args:
            d_m:       Távolság méterben.
            n_bits:    Csomag mérete bitekben.
            shadowing: Ha True, shadowing zaját hozzáadja.

        Returns:
            PER ∈ [0, 1].
        """
        ber_val = self.ber(d_m, shadowing=shadowing)
        per_val = 1.0 - (1.0 - ber_val) ** n_bits
        return float(np.clip(per_val, 0.0, 1.0))

    def prr(self, d_m: float, n_bits: int = 256, shadowing: bool = False) -> float:
        """Packet Reception Ratio (PRR).

        .. math::  PRR = 1 - PER

        Args:
            d_m:       Távolság méterben.
            n_bits:    Csomag mérete bitekben.
            shadowing: Ha True, shadowing zaját hozzáadja.

        Returns:
            PRR ∈ [0, 1].
        """
        return 1.0 - self.per(d_m, n_bits=n_bits, shadowing=shadowing)

    def prr_mean(
        self,
        d_m: float,
        n_bits: int = 256,
        n_samples: int = 1000,
    ) -> float:
        """Átlagos PRR shadowing esetén Monte-Carlo integrálással.

        Több mintavételezéssel sima görbét ad a kísérletekhez.

        Args:
            d_m:       Távolság méterben.
            n_bits:    Csomag mérete bitekben.
            n_samples: Monte-Carlo minták száma.

        Returns:
            Átlagos PRR ∈ [0, 1].
        """
        return float(
            np.mean([self.prr(d_m, n_bits=n_bits, shadowing=True) for _ in range(n_samples)])
        )

    # ---------------------------------------------------------------------------
    # Link budget összefoglaló
    # ---------------------------------------------------------------------------

    def link_budget(self, d_m: float) -> dict[str, float]:
        """Link budget összefoglaló egy adott távolságra (shadowing nélkül).

        Args:
            d_m: Távolság méterben.

        Returns:
            Szótár a fő link budget értékekkel (dBm / dB egységben).
        """
        pl = self.path_loss_db(d_m, shadowing=False)
        rssi = self.rssi_dbm(d_m, shadowing=False)
        snr = self.snr_db(d_m, shadowing=False)
        return {
            "d_m": d_m,
            "tx_power_dbm": self.tx_power_dbm,
            "path_loss_db": pl,
            "rssi_dbm": rssi,
            "noise_floor_dbm": self.noise_floor_dbm,
            "snr_db": snr,
            "ber": self.ber(d_m),
            "prr_256bit": self.prr(d_m, n_bits=256),
        }

    def __repr__(self) -> str:
        return (
            f"LogDistanceChannel(n={self.n}, pl0={self.pl0_db}dB, "
            f"d0={self.d0_m}m, σ={self.sigma_db}dB, "
            f"Ptx={self.tx_power_dbm}dBm)"
        )
