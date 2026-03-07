"""SimLogger — időbélyeges naplózó a szimulátorhoz.

A naplózó a Python beépített ``logging`` moduljára épül, és minden
bejegyzés elé automatikusan kiírja az aktuális szimulációs időpontot
(µs-ban) a hozzárendelt :class:`~wsnsim.sim.clock.SimClock`-ból.

Használat::

    from wsnsim.sim import SimClock, SimLogger

    clock = SimClock()
    log = SimLogger(clock=clock)
    log.info("Szimuláció elindult")
    # → [sim=0.000µs] Szimuláció elindult
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

from wsnsim.sim.clock import SimClock

# Alapértelmezett formátum — „%(message)s" elegendő, mert a szimulációs
# időt a SimLogger maga illeszti be az üzenet elejére.
_DEFAULT_FORMAT = "%(levelname)-8s %(message)s"


class SimLogger:
    """Szimulációs időbélyeget tartalmazó naplózó.

    Args:
        name:  A Python ``logging`` sub-logger neve (alapértelmezés: ``"wsnsim"``).
        level: A minimális naplózási szint (pl. ``logging.DEBUG``).
               Alapértelmezés: ``logging.DEBUG``.
        clock: Opcionális :class:`~wsnsim.sim.clock.SimClock`.  Ha meg van
               adva, minden üzenet előtt szerepel az aktuális szimulációs idő.
        stream: A kimenet folyama (alapértelmezés: ``sys.stdout``).

    Example:
        >>> import logging
        >>> from wsnsim.sim.clock import SimClock
        >>> from wsnsim.sim.logger import SimLogger
        >>> clock = SimClock(0.0)
        >>> log = SimLogger(clock=clock, level=logging.INFO)
        >>> log.info("hello")   # [sim=0.000µs] hello
    """

    def __init__(
        self,
        name: str = "wsnsim",
        level: int = logging.DEBUG,
        clock: Optional[SimClock] = None,
        stream: object = None,
    ) -> None:
        self._clock: Optional[SimClock] = clock
        self._logger: logging.Logger = logging.getLogger(name)
        self._logger.setLevel(level)

        # Csak akkor adunk handlert, ha még nincs (idempotens hívás)
        if not self._logger.handlers:
            handler = logging.StreamHandler(
                stream=stream if stream is not None else sys.stdout
            )
            handler.setLevel(level)
            formatter = logging.Formatter(_DEFAULT_FORMAT)
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

        # Megakadályozzuk, hogy a root-loggerbe is felbuggyon
        self._logger.propagate = False

    # ---------------------------------------------------------------------------
    # Belső segédmetódus
    # ---------------------------------------------------------------------------

    def _format_message(self, message: str) -> str:
        """Szimulációs időbélyeget illeszt az üzenet elé, ha van óra."""
        if self._clock is not None:
            return f"[sim={self._clock.now:.3f}\u00b5s] {message}"
        return message

    # ---------------------------------------------------------------------------
    # Naplózó metódusok
    # ---------------------------------------------------------------------------

    def debug(self, message: str) -> None:
        """DEBUG szintű naplóbejegyzés.

        Args:
            message: A naplózandó szöveges üzenet.
        """
        self._logger.debug(self._format_message(message))

    def info(self, message: str) -> None:
        """INFO szintű naplóbejegyzés.

        Args:
            message: A naplózandó szöveges üzenet.
        """
        self._logger.info(self._format_message(message))

    def warning(self, message: str) -> None:
        """WARNING szintű naplóbejegyzés.

        Args:
            message: A naplózandó szöveges üzenet.
        """
        self._logger.warning(self._format_message(message))

    def error(self, message: str) -> None:
        """ERROR szintű naplóbejegyzés.

        Args:
            message: A naplózandó szöveges üzenet.
        """
        self._logger.error(self._format_message(message))

    def log(self, level: int, message: str) -> None:
        """Tetszőleges szintű naplóbejegyzés.

        Args:
            level:   A ``logging`` modul szintje (pl. ``logging.INFO``).
            message: A naplózandó szöveges üzenet.
        """
        self._logger.log(level, self._format_message(message))

    # ---------------------------------------------------------------------------
    # Lekérdezők
    # ---------------------------------------------------------------------------

    @property
    def underlying_logger(self) -> logging.Logger:
        """A mögöttes ``logging.Logger`` példány (haladó konfigurációhoz)."""
        return self._logger

    def set_level(self, level: int) -> None:
        """Módosítja a naplózási szintet futás közben.

        Args:
            level: Az új minimális naplózási szint.
        """
        self._logger.setLevel(level)
        for handler in self._logger.handlers:
            handler.setLevel(level)

    def __repr__(self) -> str:
        sim_t = f"{self._clock.now:.3f}µs" if self._clock else "N/A"
        return (
            f"SimLogger(name={self._logger.name!r}, "
            f"level={logging.getLevelName(self._logger.level)}, "
            f"sim_time={sim_t})"
        )
