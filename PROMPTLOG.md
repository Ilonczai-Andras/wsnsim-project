# PROMPTLOG — wsnsim projekt

Ez a fájl a projekt fejlesztése során alkalmazott AI-promptokat és a hozzájuk kapcsolódó döntéseket rögzíti.
Minden bejegyzés a kötelező sablont követi.

---

## Sablon

```
### [DÁTUM] — [Rövid cím]

**Cél:**
Mit szerettünk volna elérni ezzel a prompttal?

**Kontextus:**
Mi volt az aktuális állapot, milyen kódbázison / problémán dolgoztunk?

**Prompt:**
Az AI-nak küldött pontos kérés szövege.

**MI válasz összefoglalója:**
Az AI által javasolt megközelítés rövid leírása (nem a teljes output).

**Döntésem:**
Mit fogadtam el, mit módosítottam, mit utasítottam el és miért?

**Validálás:**
Hogyan ellenőriztem az eredményt? (tesztek, manuális futtatás, kódátvizsgálás stb.)
```

---

## Bejegyzések

---

## 2026-03-07 Projekt Incializáció

### 1. Projektstruktúra és fejlesztői környezet kialakítása

**Cél:**
A wsnsim Python csomag alapvető repo-vázának, fejlesztői környezetének és dokumentációjának elkészítése egyetlen, jól specifikált AI-prompttal.

**Kontextus:**
Üres workspace (`d:\wsnsim-project`), csak egy üres `README.md` létezett. Semmilyen kód, konfiguráció vagy mappastruktúra nem volt még jelen.

**Prompt:**

> Egy Python-alapú vezeték nélküli szenzorhálózat szimulátor (wsnsim) fejlesztésébe kezdek.Segíts az alapvető projektstruktúra és a fejlesztői környezet kialakításában az alábbiak szerint:
>
> 1. Repo struktúra: wsnsim/sim/, wsnsim/models/, wsnsim/scenarios/, wsnsim/metrics/, wsnsim/utils/, tests/, experiments/, reports/figures/
> 2. Környezet: requirements.txt — pytest, numpy, matplotlib, networkx
> 3. Konfiguráció: pyproject.toml (telepíthető csomag)
> 4. Alap dokumentáció: README.md sablon "Gyors indítás" és "Modulok" szekciókkal
> 5. Promptlog: PROMPTLOG.md a kötelező sablonnal

**MI válasz összefoglalója:**
Az AI létrehozta a teljes mappastruktúrát `__init__.py` fájlokkal, a `requirements.txt`-t verziózott függőségekkel (numpy≥1.26, networkx≥3.3, matplotlib≥3.8, pytest≥8.1, pytest-cov≥5.0), a `pyproject.toml`-t setuptools build-backenddel és opcionális `[dev]` extra-val, a `README.md`-t magyar nyelvű "Gyors indítás" és "Modulok" szekciókkal, valamint ezt a `PROMPTLOG.md` fájlt.

**Döntésem:**

- Elfogadva: a teljes javasolt struktúra — megfelel a standard Python csomag-konvencióknak (src-layout helyett flat-layout, mivel a projekt korai fázisban van).
- Módosítás: `pytest-cov` hozzáadása a `requirements.txt`-be a lefedettségi mérés miatt (az alap specifikációban nem szerepelt, de szükséges fejlesztői eszköz).
- Elfogadva: `pyproject.toml` a `setup.py` helyett — modernebb, PEP 517/518 kompatibilis megoldás.

**Validálás:**

- [x] `pip install -e .[dev]` lefut hiba nélkül — ✅ 2026-03-07 (javítás: `build-backend` helyesbítve `setuptools.build_meta`-ra)
- [x] `pytest` lefut importhibák nélkül — ✅ 2026-03-07, 2 passed, 100% coverage (`tests/test_smoke.py` hozzáadva)
- [x] `python -c "import wsnsim; print(wsnsim.__version__)"` visszaadja `0.1.0`-t — ✅ 2026-03-07
- [x] Mappastruktúra egyezik a specifikációval (`Get-ChildItem -Recurse`) — ✅ 2026-03-07, mind az 5 alcsomag jelen van

---

### 2. .gitignore létrehozása

**Cél:**
A verziókezelőből kizárandó fájlok és mappák definiálása, hogy a repo tiszta maradjon (cache, venv, build-artifaktok, generált outputok).

**Kontextus:**
Az alapstruktúra és a `pyproject.toml` már létezett, de `.gitignore` nem volt. A `.venv/`, `__pycache__/`, `dist/` stb. könnyen bekerülhettek volna a commitokba.

**Prompt:**

> create a gitignore too

**MI válasz összefoglalója:**
Az AI létrehozott egy `.gitignore` fájlt, amely lefedi: Python cache (`__pycache__/`, `*.pyc`), csomagolási outputokat (`dist/`, `build/`, `*.egg-info/`), virtuális környezeteket (`.venv/`, `venv/`), pytest/coverage outputokat (`.pytest_cache/`, `htmlcov/`), Jupyter checkpointokat, IDE-fájlokat (`.vscode/`, `.idea/`) és projekt-specifikus generált fájlokat (`reports/figures/*.png`, `experiments/*.csv`).

**Döntésem:**
Elfogadva teljes egészében — standard Python projekt `.gitignore` sablon, projekt-specifikus kiegészítésekkel. Nem volt mit módosítani.

**Validálás:**

- [x] `.gitignore` fájl létezik a repo gyökerében — ✅ 2026-03-07
- [x] A `.venv/` mappa szerepel benne — ✅
- [x] `reports/figures/` és `experiments/` generált outputjai ki vannak zárva — ✅

---

### 3. Smoke tesztek hozzáadása

**Cél:**
A `pytest` „no data collected" coverage-figyelmeztetésének megszüntetése és az alapvető import-helyesség gépi ellenőrzése.

**Kontextus:**
`pytest` 0 tesztet gyűjtött össze, a coverage-plugin `CoverageWarning: No data was collected` figyelmeztetést dobott. A `wsnsim/__init__.py` 0%-os lefedettséget mutatott.

**Prompt:**

> _(pytest kimenet beillesztve — 0 items collected, CoverageWarning)_

**MI válasz összefoglalója:**
Az AI létrehozta a `tests/test_smoke.py` fájlt két teszttel: `test_package_version()` ellenőrzi, hogy `wsnsim.__version__ == "0.1.0"`, `test_submodules_importable()` pedig végigiterál mind az 5 almodulun és ellenőrzi, hogy importálhatók.

**Döntésem:**
Elfogadva — minimális, de értékes alaptesztek. Biztosítják, hogy egy csomagtörés (pl. rossz `__init__.py`) azonnal látható legyen CI-ban is.

**Validálás:**

- [x] `pytest` 2 tesztet gyűjt és futtat — ✅ 2026-03-07, `2 passed in 0.09s`
- [x] Coverage-figyelmeztetés eltűnt — ✅
- [x] `wsnsim/__init__.py` lefedettsége 100% — ✅
- [x] `python -c "import wsnsim; print(wsnsim.__version__)"` → `0.1.0` — ✅

---

<!-- Új nap bejegyzései ide kerülnek: ## YYYY-MM-DD, majd ### 1. Cím stb. -->

---

## 2026-03-07 7.1. hét: WSN alapok & szimulátor indítás

### 1. Szimulációs motor alapjai (v0) — SimClock, Event, Scheduler, SimLogger

**Cél:**
A `wsnsim.sim` almodul teljes implementációja: diszkrét eseményű szimulátor alapjai, determinisztikus RNG-kezeléssel és időbélyeges naplózóval.

**Kontextus:**
A `wsnsim/sim/__init__.py` üres vázként létezett. A cél egy heapq-alapú eseménysor, amelyhez szimulációs óra, event-struktúra és logger is tartozik.

**Prompt:**

> Implementáld a szimulátor alapjait (v0): SimClock, heapq-alapú Scheduler, Event dataclass (timestamp, priority, callback, payload), SimLogger időbélyeges naplózóval. Determinizmus: numpy.random.default_rng(seed). Írj legalább 2-3 pytest unit tesztet a tests/test_scheduler.py fájlba (eseményrendezés, tie-breaker prioritás, FIFO, SimClock).

**MI válasz összefoglalója:**Az AI létrehozta a következő modulokat:

- `wsnsim/sim/clock.py` — `SimClock` osztály (`advance()`, `reset()`, monoton időellenőrzéssel)
- `wsnsim/sim/event.py` — `Event` dataclass (`time`, `priority`, `_seq`, `callback`, `payload`; teljes összehasonlító operátorok)
- `wsnsim/sim/scheduler.py` — `Scheduler` osztály (`schedule()`, `step()`, `run()`, `run_until()`; heapq alapú)
- `wsnsim/sim/logger.py` — `SimLogger` osztály (Python `logging`-ra épül, szimulációs időbélyeggel)
- `wsnsim/sim/__init__.py` — re-export `__all__`
- `tests/test_scheduler.py` — 15 unit teszt 5 tesztosztályban

**Döntésem:**

- Elfogadva: `Event` dataclassban kézi `__lt__`/`__le__`/stb. implementáció a `@dataclass(order=True)` helyett — pontosabb kontroll a `(time, priority, _seq)` hármas felett.
- Elfogadva: `Scheduler` nem örököl `threading.Lock`-ot — egyszálú szimulátorhoz felesleges.
- Elfogadva: `SimLogger` önálló `propagate=False` beállítása — elkerüli a root-logger duplikált kimenetét.
- Javítva: a tesztben a `match="visszalép"` regex nem illeszkedett a `"léphet vissza"` üzenetre → `match="vissza"`-ra módosítva.

**Validálás:**

- [x] `pytest tests/ -v --tb=short` — **17 passed**, 0 failed ✅ 2026-03-07
- [x] Esemény-időrend (`TestEventOrdering`): 3 teszt ✅
- [x] Tie-breaker prioritás (`TestPriorityTieBreaker`): 3 teszt (negatív priority, FIFO) ✅
- [x] SimClock viselkedés (`TestSimClock`): 5 teszt (ValueError visszalépésre, negatív init) ✅
- [x] `run_until()` határfeltételek (`TestRunUntil`): 2 teszt ✅
- [x] Determinizmus (`TestDeterminism`): 2 teszt (azonos seed = azonos kimenet) ✅
- [x] Coverage: `sim/__init__.py` 100%, `scheduler.py` 90% ✅

---

### 2. DoD-hianyok potlasa - StatsCollector, hello_sim, README javitas

**Cel:**
A 7.1. heti DoD harom hianyzo elemenenek implementalasa: futtathatao "hello simulation" pelda,
alapszintu statisztika-gyujto modul es a README valos API-ra valo frissitese.

**Kontextus:**
Az elozo MI-interakcio (4. bejegyzes) kesz szimulatormotor hozott letre, de a DoD-ellenorzes harom
hianyossagot tart fel: (1) a `wsnsim.metrics` ures volt, (2) a `README.md` nem leteszo osztalyokra
hivatkozott, (3) nem volt futtathatao kiserlet kimenettel.

**Prompt:**

> A dokumentum DoD-ellenorzese alapjan hianzik: (1) StatsCollector a metrics modulba,
> (2) futtathatao hello_sim.py kiserlet oszlopdiagrammal, (3) README javitasa a valos API-ra.
> Implementald mindharmat, majd frissitsd a PROMPTLOG-ot.

**MI valasz osszefoglaloja:**

- `wsnsim/metrics/collector.py` - `StatsCollector` osztaly: `record()`, `count()`, `total()`,
  `mean()`, `minimum()`, `maximum()`, `summary()`, `table_str()` metodusokkal; `Record` dataclass.
- `wsnsim/metrics/__init__.py` - re-export `StatsCollector`.
- `experiments/hello_sim.py` - 5 csomopontos periodikus TX szimulacio: exponencialis kuldesi
  koz, seed=42, 10 ms szimulalt ido; stdout tablazat + `reports/figures/hello_sim_events.png`.
- `README.md` - "Elso szimulacio" szekcioja javitva valos importokra.

**Dontesemet:**

- Elfogadva: `StatsCollector` nem orokli a `Scheduler`-t - egyszeru, fuggetlen adatosztaly.
- Elfogadva: `Record` dataclass a nyers rekordokhoz - konny bővíthetőség (tag mezo).
- Elfogadva: `hello_sim.py` exponencialis koz-eloszlast hasznal (realisztikus WSN forgalommodell).
- Elfogadva: minden csomopont leagaztatott RNG-t kap (master_rng.integers -> default_rng).

**Validalas:**

- [x] `pytest tests/ -v --tb=short` - **17 passed**, 0 failed ✅ 2026-03-07
- [x] `python experiments/hello_sim.py` - 35 esemeny, tablazat stdout-ra, abra mentve ✅
- [x] `reports/figures/hello_sim_events.png` generalodik (150 dpi, 2 panel) ✅
- [x] Reprodukalhatosag: ketszeri futatas azonos tablazatot ad (seed=42) ✅
- [x] `wsnsim.metrics` importalhato, `StatsCollector` elerheto ✅
