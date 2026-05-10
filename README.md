# wsnsim — Wireless Sensor Network Simulator

## Executive Summary
A **wsnsim** egy Python-alapú, diszkrét eseményvezérelt (DES) szimulátor, amely vezeték nélküli szenzorhálózatok (WSN) kutatási és oktatási modellezésére készült. A projekt átfogóan támogatja a teljes hálózati stacket és a szenzorcsomóponti feladatokat: 
- **Fizikai és MAC réteg:** Log-distance csatorna árnyékolással, energiaállapot-gép (IDLE/TX/RX/SLEEP), ALOHA és CSMA/BEB protokollok.
- **Hálózat és Megbízhatóság:** Statikus Sink-fa és árasztásos útválasztás, integrált Stop-and-Wait ARQ mechanizmus a garantált adatátvitelért.
- **Adatkezelés:** In-network adataggregáció (delta-kódolás), Edge AI alapú anomália-detekció (Z-Score, EWMA) és elosztott gépi tanulás (Federated Learning FedAvg-al).
Célja egy tiszta, reprodukálható (seedelt) platform biztosítása, amely egy dedikált optimalizációs modullal lehetővé teszi a hálózati tervezési tér (design space) feltérképezését és a Pareto-optimális architektúrák kiválasztását.

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

### 2. Tesztelés

A projekt kiterjedt unit teszthálózattal rendelkezik (több mint 300 teszt), amely biztosítja a modellek stabilitását. A tesztek a `pytest` framework segítségével futtathatók, a teljes tesztcsomag így indítható:

```bash
pytest tests/ -v
```

### 3. Végső Esettanulmány (Projekt Bemutató)

A projekt fő futtatási parancsa a végső esettanulmány (Smart Agriculture szcenárió), amely bemutatja a wsnsim moduláris képességeit, a MAC és ARQ rétegek optimalizálását egy 50 csomópontos topológiában:

```bash
python experiments/case_study.py
```
Ez a parancs generál egy összegző riportot a konzolra, feltérképezi a Pareto-frontot, és elmenti a kapcsolódó ábrát a `reports/figures/case_study_pareto.png` útvonalra. További specifikus szimulációkat (pl. Federated Learning, Edge AI) az `experiments/` mappa alatt találsz.

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
