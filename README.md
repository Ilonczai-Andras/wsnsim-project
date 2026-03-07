# wsnsim — Wireless Sensor Network Simulator

Python-alapú, eseményvezérelt szimulátor vezeték nélküli szenzorhálózatok modellezésére.  
Kutatási és oktatási célra tervezve: energiamodellezés, routing-protokollok és hálózati teljesítménymutatók vizsgálatára.

---

## Gyors indítás

### 1. Klónozás és telepítés

```bash
git clone <repo-url>
cd wsnsim-project

# Virtuális környezet létrehozása
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

# Függőségek telepítése
pip install -r requirements.txt

# Csomag szerkeszthető módban való telepítése
pip install -e .
```

### 2. Tesztek futtatása

```bash
pytest
```

### 3. Első szimuláció futtatása

```bash
python experiments/hello_sim.py
```

Vagy közvetlenül Pythonból:

```python
import numpy as np
from wsnsim.sim import SimClock, Scheduler
from wsnsim.metrics import StatsCollector

clock = SimClock()
stats = StatsCollector(clock)
sched = Scheduler(clock, rng=np.random.default_rng(42))

sched.schedule(100.0, lambda e: stats.record("tx", value=32.0), payload="ping")
sched.schedule(200.0, lambda e: stats.record("rx", value=32.0), payload="pong")
sched.run()

print(stats.table_str())
```

---

## Modulok

| Modul         | Elérési út          | Leírás                                                   |
| ------------- | ------------------- | -------------------------------------------------------- |
| **sim**       | `wsnsim/sim/`       | Szimuláció motor — eseményvezérelt futtatás, időbeosztás |
| **models**    | `wsnsim/models/`    | Csomópont-, energia- és csatorna-modellek                |
| **scenarios** | `wsnsim/scenarios/` | Forgatókönyvek beolvasása és topológia-leírók            |
| **metrics**   | `wsnsim/metrics/`   | Teljesítménymutatók (PDR, energia, késleltetés)          |
| **utils**     | `wsnsim/utils/`     | Logolás, véletlenszám-kezelés, általános segédfüggvények |

### Részletes modul-leírások

#### `wsnsim.sim`

Az eseményvezérelt szimuláció magja. Kezeli az eseménysorokat, az időléptetést és a csomópontok közötti üzenetküldést.

#### `wsnsim.models`

Fizikai és logikai modellek gyűjteménye:

- `NodeModel` — szenzorcsomópont állapota és viselkedése
- `EnergyModel` — akkumulátor- és fogyasztásmodell
- `ChannelModel` — rádiócsatorna, csillapítás, interferencia

#### `wsnsim.scenarios`

YAML/JSON alapú forgatókönyv-leírók betöltése és validálása. Meghatározza a topológiát, a csomópontok paramétereit és a forgalomgenerátort.

#### `wsnsim.metrics`

Futás közbeni és utólagos metrika-gyűjtés:

- Csomagkézbesítési arány (PDR)
- Átlagos energiafogyasztás
- Végponttól-végpontig tartó késleltetés
- Hálózati élettartam

#### `wsnsim.utils`

- Strukturált naplózás (`logging` wrapper)
- Reprodukálható véletlenszám-generálás
- Segédeszközök gráfvizualizációhoz (Matplotlib + NetworkX)

---

## Projekt struktúra

```
wsnsim-project/
├── wsnsim/
│   ├── sim/          # Szimuláció motor
│   ├── models/       # Csomópont- és csatorna-modellek
│   ├── scenarios/    # Forgatókönyvek
│   ├── metrics/      # Teljesítménymutatók
│   └── utils/        # Segédeszközök
├── tests/            # Egység- és integrációs tesztek
├── experiments/      # Kísérleti szkriptek és notebookok
├── reports/
│   └── figures/      # Generált ábrák
├── requirements.txt
├── pyproject.toml
├── PROMPTLOG.md
└── README.md
```

---

## Fejlesztői munkamenet

```bash
# Linting (opcionális, ha ruff telepítve van)
ruff check wsnsim/

# Lefedettségi riport
pytest --cov=wsnsim --cov-report=html
# Megnyitás: htmlcov/index.html
```

---

## Licenc

MIT — részletek a `LICENSE` fájlban.
