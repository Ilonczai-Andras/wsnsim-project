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

- [X] `pip install -e .[dev]` lefut hiba nélkül — ✅ 2026-03-07 (javítás: `build-backend` helyesbítve `setuptools.build_meta`-ra)
- [X] `pytest` lefut importhibák nélkül — ✅ 2026-03-07, 2 passed, 100% coverage (`tests/test_smoke.py` hozzáadva)
- [X] `python -c "import wsnsim; print(wsnsim.__version__)"` visszaadja `0.1.0`-t — ✅ 2026-03-07
- [X] Mappastruktúra egyezik a specifikációval (`Get-ChildItem -Recurse`) — ✅ 2026-03-07, mind az 5 alcsomag jelen van

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

- [X] `.gitignore` fájl létezik a repo gyökerében — ✅ 2026-03-07
- [X] A `.venv/` mappa szerepel benne — ✅
- [X] `reports/figures/` és `experiments/` generált outputjai ki vannak zárva — ✅

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

- [X] `pytest` 2 tesztet gyűjt és futtat — ✅ 2026-03-07, `2 passed in 0.09s`
- [X] Coverage-figyelmeztetés eltűnt — ✅
- [X] `wsnsim/__init__.py` lefedettsége 100% — ✅
- [X] `python -c "import wsnsim; print(wsnsim.__version__)"` → `0.1.0` — ✅

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

- [X] `pytest tests/ -v --tb=short` — **17 passed**, 0 failed ✅ 2026-03-07
- [X] Esemény-időrend (`TestEventOrdering`): 3 teszt ✅
- [X] Tie-breaker prioritás (`TestPriorityTieBreaker`): 3 teszt (negatív priority, FIFO) ✅
- [X] SimClock viselkedés (`TestSimClock`): 5 teszt (ValueError visszalépésre, negatív init) ✅
- [X] `run_until()` határfeltételek (`TestRunUntil`): 2 teszt ✅
- [X] Determinizmus (`TestDeterminism`): 2 teszt (azonos seed = azonos kimenet) ✅
- [X] Coverage: `sim/__init__.py` 100%, `scheduler.py` 90% ✅

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

- [X] `pytest tests/ -v --tb=short` - **17 passed**, 0 failed ✅ 2026-03-07
- [X] `python experiments/hello_sim.py` - 35 esemeny, tablazat stdout-ra, abra mentve ✅
- [X] `reports/figures/hello_sim_events.png` generalodik (150 dpi, 2 panel) ✅
- [X] Reprodukalhatosag: ketszeri futatas azonos tablazatot ad (seed=42) ✅
- [X] `wsnsim.metrics` importalhato, `StatsCollector` elerheto ✅

---

## 2026-03-07 7.2. hét: Radios csatorna modellek

### 1. LogDistanceChannel, Packet, prr_curve

**Cel:**
A wsnsim.models csatornamodul implementalasa: log-distance + log-normal shadowing modell,
BER->PER->PRR lanc, Packet dataclass, PRR(d) kisérleti abra.

**Kontextus:**
A 7.1. heti motor (sim modul) kész; a 7.2. het a fizikai csatornaretelget adja hozza.
wsnsim/models/**init**.py ures vazként létezett.

**Prompt:**

> Implementald a 7.2. heti feladatot: LogDistanceChannel (log-distance + log-normal shadowing,
> BER->PER->PRR BPSK-AWGN kozelitessel), Packet dataclass, tests/test_channel.py (monotonitas,
> referencia-pont, kezi szamitas 2 ponton, seed reprodukalhatosag), experiments/prr_curve.py
> (PRR(d) gorbe 3 sigma ertekre, link budget tablazat stdoutra, abra mentese).

**MI valasz osszefoglaloja:**

- `wsnsim/models/channel.py` — `LogDistanceChannel` dataclass:
  `path_loss_db()`, `rssi_dbm()`, `snr_db()`, `ber()`, `per()`, `prr()`,
  `prr_mean()` (Monte-Carlo), `link_budget()`.
- `wsnsim/models/packet.py` — `Packet` dataclass: `size_bits`, `delivered`,
  `latency_us` property-k; `lost` flag felulirja a `delivered`-et.
- `wsnsim/models/__init__.py` — re-export.
- `tests/test_channel.py` — 18 unit teszt: path loss ref-pont, monotonitas,
  kezi szamitas (10 m, 50 m), RSSI, PRR tartomany, shadowing seed-eleg.
- `experiments/prr_curve.py` — PRR(d) gorbe sigma={0,3,6} dB; link budget
  tablazat kezi validalassal; `reports/figures/prr_curve.png`.

**Dontesemet:**

- Elfogadva: BPSK-AWGN BER=0.5\*erfc(sqrt(SNR_lin)) — WSN irodalomban bevett
  egyszerusites (o(erfc) numerikusan stabil, scipy nelkul is).
- Elfogadva: d < d0 kliппeles d0-ra (nem ad negatív path loss-t kozeli esetben).
- Elfogadva: prr_mean() Monte-Carlo (500 minta) az atlagos PRR simaabrakhoz —
  a deterministikus sigma=0 ag megtartva gyors tesztekre.
- Elfogadva: Packet.lost flag felulirja delivered-et — realisztikusabb
  csatorna-integracio keszitese elo.

**Validalas:**

- [X] `pytest tests/ -v --tb=short` — **35 passed**, 0 failed ✅ 2026-03-07
- [X] Kezi szamitas: PL(10 m) = 82.00 dB, PL(50 m) = 100.87 dB ✅ (stdout tablazat)
- [X] `python experiments/prr_curve.py` — link budget tablazat + abra ✅
- [X] `reports/figures/prr_curve.png` generalodik (3 sigma gorbe) ✅
- [X] Shadowing reprodukalhatosag: azonos seed = azonos PRR-sorozat ✅
- [X] `wsnsim.models` importalhato, `LogDistanceChannel` es `Packet` elerheto ✅

---

## 2026-03-07 7.3. hét: Energia és üzemidő

### 1. EnergyModel, allapotgep, duty-cycle kiserlet

**Cel:**
Az energia modul implementalasa: EnergyState enum (TX/RX/IDLE/SLEEP), EnergyModel allapotgep
fogyasztas-intergralasal, negatív energia guard, uezemido-becsles, duty-cycle kiserlet abraval.

**Kontextus:**
A 7.2. heti csatornamodul kesz. A 7.3. het az energiareteget adja hozza, amely a kesobb
implementalando MAC es routing modulok szamara biztositja a fogyasztaskovetést.

**Prompt:**

> Implementald a 7.3. heti feladatot: EnergyState enum (TX/RX/IDLE/SLEEP), EnergyModel
> allapotgep (transition, flush, remedaining_j soha nem negativ, lifetime_estimate_s),
> tests/test_energy.py (integracio kezi szamitassal, duty-cycle trend, eletartam-formula),
> experiments/duty_cycle_lifetime.py (duty-cycle vs eletartam abra + stdout tablazat).

**MI valasz osszefoglaloja:**

- `wsnsim/models/energy.py` — `EnergyState` enum + `EnergyModel` dataclass:
  `transition()`, `flush()`, `consumed_j`, `remaining_j`, `is_depleted`,
  `soc_percent`, `average_power_w()`, `lifetime_estimate_s()`, `summary()`.
  CC2420-alapu DEFAULT_POWER_MW: TX=52.2 mW, RX=56.4 mW, IDLE=3 mW, SLEEP=0.003 mW.
- `wsnsim/models/__init__.py` — re-export `EnergyModel`, `EnergyState`.
- `tests/test_energy.py` — 16 unit teszt: kezi energiaintegracio (1 s TX = 0.0522 J),
  negativ energia guard, duty-cycle monotonicas, eletartam keplet, idovisszalep-tiltalom, flush.
- `experiments/duty_cycle_lifetime.py` — analitikus DC vs P es DC vs elettartam gorbe;
  stdout tablazat kezi validalassal; `reports/figures/duty_cycle_lifetime.png`.

**Dontesemet:**

- Elfogadva: energia integracio µs → s konverzio (delta_us × 1e-6) — konzisztens a szimulatorral.
- Elfogadva: negatív energia klippeles (nem RuntimeError) — folytonos szimulacio utan is fut a kod,
  az is_depleted flag jelzi az allapotot.
- Elfogadva: duty-cycle kiserletben analitikus szamitas (nem Monte-Carlo) — gyors, determinisztikus.
- Elfogadva: lifetime_estimate_s(avg_power_w=None) az eddigi merésből becsul —
  kulsőleg is megadhato explicit ertekkel (kiserletekhez).

**Validalas:**

- [X] `pytest tests/ -v --tb=short` — **51 passed**, 0 failed ✅ 2026-03-07
- [X] Kezi ellenorzés: 1 s TX → consumed_j = 0.0522 J ✅
- [X] Kezi ellenorzés: DC=1% → P = 0.01×54.3 + 0.99×0.003 = 0.5460 mW ✅
- [X] `python experiments/duty_cycle_lifetime.py` — tablazat + abra ✅
- [X] `reports/figures/duty_cycle_lifetime.png` (2 panel: avg P + eletartam log skala) ✅
- [X] `wsnsim.models` importalhato, `EnergyModel` es `EnergyState` elerheto ✅

### 2026-03-14 — 7.4. hét: MAC protokollok

### Aloha + CSMA/BEB

**Cél:**
A MAC réteg v1 implementálása: Pure ALOHA és CSMA bináris exponenciális backoff-fal, osztott közeg modellel, ütközés-detekcióval és összehasonlító kísérlettel.

**Kontextus:**
A 7.1–7.3. hetek (DES motor, csatornamodell, energiamodell) már elkészültek, 51/51 teszt zöld. A `wsnsim/models/` csomagban `channel.py`, `energy.py` és `packet.py` volt jelen. A spec (WSN_Gyakorlati_Utmutato_wsnsim_v1_1.txt, 7.4. hét szekció) ALOHA + CSMA backoff implementációt, determinisztikus ütközéstesztet és egy összehasonlító kísérletet írt elő.

**Prompt:**

> jó akkor folytassuk a 7.4. hét: MAC protokollok-el

**MI válasz összefoglalója:**
Az AI elolvasta a spec releváns részét, majd létrehozta a `wsnsim/models/mac.py` fájlt három fő komponenssel: `Medium` (osztott közeg, retroaktív ütközés-jelöléssel és iteratív `busy_until()`-lal), `ALOHAMac` (azonnali adás) és `CSMAMac` (carrier-sense + BEB). Mellé 25 unit tesztet (`tests/test_mac.py`) és egy kísérleti scriptet (`experiments/mac_comparison.py`) készített, amely G vs. S és G vs. PDR görbéket ábrázol, beleértve az analitikus ALOHA `G·e^{-2G}` referenciagörbét.

**Döntésem:**
Az egész megközelítést elfogadtam. A `busy_until()` iteratív keresése (láncoltan egymás mögé szervezett adások helyes kezelése) és a `unittest.mock.patch`-alapú kényszeres ütközésteszt (rejtett állomás szimulálása) különösen jó döntésnek bizonyult. Az eredeti `busy_until()` egy-lépéses verzióját az AI maga javította ki, miután az első futtatás feltárt egy hibát a háromcsomópontos szeriális tesztben.

**Validálás:**

- `pytest tests/ -v --tb=short` → **76/76 teszt zöld** (+25 MAC teszt, 51-ről)
- `mac.py` coverage: **97%**
- `python experiments/mac_comparison.py` → táblázat és `reports/figures/mac_comparison.png` generálva
- Manuális ellenőrzés: ALOHA PDR G=1-nél ≈40%, G≥7-nél 0% (klasszikus görbe); CSMA PDR minden G-nél 100% (szekvenciális feldolgozásban mindig ütközésmentes)
- DoD ✅: mac modul v1, ütközésteszt seed-del, összehasonlító ábra

### 2026-03-21 — 7.5. hét: Topológia és kapcsolatgráfok

**Cél:**
Topológia generátor modul elkészítése három deployment stratégiával (random, grid, cluster),
hatótáv alapú szomszédsági gráf építéssel és összefüggőség vizsgálattal.

**Kontextus:**
A 7.1–7.4. hetek elkészültek (DES motor, csatorna, energia, MAC), 76/76 teszt zöld.
A wsnsim/utils/ csomag üres volt. A spec (7.5. hét) legalább 2 deployment stratégiát,
szomszédsági gráfot, összefüggőség tesztet és 1 ábrát írt elő seed dokumentálással.

**Prompt:**

> Jó akkor folytassuk a 7.5. hét: Topológia és kapcsolatgráfok feladatot.
> Kezdhetjük, az általad ajánlott struktúra jó lesz.

**MI válasz összefoglalója:**
Az AI létrehozta a wsnsim/utils/topology.py fájlt Node dataclass-szal és három deployment
függvénnyel (random_deployment, grid_deployment, cluster_deployment), hatótáv-alapú
uild_neighbor_graph() NetworkX-integrációval és connectivity_stats() metrika-függvénnyel.
35 unit tesztet és egy 3-panel vizualizációs kísérleti scriptet is elkészített.

**Döntésem:**
Teljes egészében elfogadtam. A busy_until() iteratív megközelítés mintájára a build_neighbor_graph()
weight attribútumot is kap (1/d), ami a következő heti routing modulhoz előremutat.

**Validálás:**

- pytest tests/ --tb=short → **112/112 teszt zöld** (76 → 112, +36 topológia teszt)
- opology.py coverage: **97%**
- python experiments/topology_viz.py → konzol táblázat +
  eports/figures/topology_viz.png
- Manuális ellenőrzés: Random: 2 komp., sink elér. 95%; Grid: összefüggő, 100%; Cluster: összefüggő, 100%
- DoD: topology modul (3 stratégia) + összefüggőség teszt + 1 ábra seed paraméterekkel ✅

---

### 2026-03-21 — 7.6. hét: Routing és adatgyűjtés

**Cél:**
Két routing stratégia implementálása a WSN szimulátorba: (1) flooding TTL-lel és seen-cache-szel a végtelen hurkok elkerülésére, (2) ETX-alapú statikus sink-fa Dijkstra-algoritmussal.

**Kontextus:**
A 7.1–7.5. hetek elkészültek (DES motor, csatorna, energia, MAC, topológia), 112/112 teszt zöld. A wsnsim/models/ csomagban channel.py, energy.py, mac.py és packet.py volt jelen. A uild_neighbor_graph() már distance és weight él-attribútumokat ad, amelyekre a routing épít. A spec (7.6. hét) flooding + sink-fa routing implementációt, összehasonlító kísérletet és ábrát írt elő.

**Prompt:**

> Kezdhetjük, az általad ajánlott struktúra jó lesz. Amennyiben valami hiba alakul ki javítjuk majd.

**MI válasz összefoglalója:**

- wsnsim/models/routing.py — RoutedPacket dataclass (packet_id, src, dst, 	tl, hops, delivered, dropped, drop_reason; hop_count property), FloodRouter (BFS + seen-cache set[tuple[int,int]], inject(), pdr(), vg_hop_count(), 
eset()), _etx() segédfüggvény (1/PRR), SinkTreeRouter (Dijkstra ETX-súlyokkal a sinkből visszafelé, path_to_sink(), 
oute(), parent_of(), etx_to_sink(), ll_reachable(), 	ree_edges()).
- wsnsim/models/__init__.py — FloodRouter, RoutedPacket, SinkTreeRouter exportálva.
- 	ests/test_routing.py — 29 unit teszt 7 osztályban: TestRoutedPacket, TestFloodRouterBasic, TestFloodRouterTTL, TestFloodRouterCache, TestSinkTreeBasic, TestSinkTreeETX, TestSinkTreeIsolated.
- experiments/routing_comparison.py — 5×5 rácstopológia (25 csomópont, sink=0), Flooding vs Sink-fa összehasonlítás; PDR / átlagos hop-count táblázat stdout-ra; 4-panel ábra (PDR sávdiagram, hop-count sávdiagram, hop-count hisztogram, ETX-alapú sink-fa topológia).

**Döntésem:**

- Elfogadva: a sink-fa statikus (nincs dinamikus újraszámolás link-hiba esetén) — dokumentált korlátként kezelve, a következő heti ARQ modul kezeli a link-szintű megbízhatóságot.
- Elfogadva: ETX = 1/PRR, ha van prr él-attribútum; egyébként exp(-d/scale) heurisztika.
- Elfogadva: FloodRouter seen-cache (node_id, packet_id) párokkal — végtelen hurkot és duplikált kézbesítést egyaránt megakadályoz.

**Validálás:**

- [x] pytest tests/ --tb=short → **141/141 teszt zöld** (112 → 141, +29 routing teszt) ✅
- [x] 
outing.py coverage: **95%** ✅
- [x] python experiments/routing_comparison.py → PDR=1.000 mindkét stratégiánál, átlagos hop-count=4.17 ✅
- [x] 
eports/figures/routing_comparison.png generálva (4 panel, ETX hőtérkép) ✅
- [x] Izolált csomópont drop_reason="no_route" visszaadás tesztelve ✅
- [x] TTL lejárat drop_reason="TTL=0" visszaadás tesztelve ✅

---

### 2026-04-18 — 7.7. hét: Megbízhatóság és ARQ

**Cél:**
Stop-and-Wait ARQ modell implementálása WSN pont-pont összeköttetésekhez: konfiguálható újraküldési korláttal, exponenciális backoff-al, energia-könyveléssel és paraméteres sweep kísérlettel.

**Kontextus:**
A 7.1–7.6. hetek elkészültek (DES motor, csatorna, energia, MAC, topológia, routing), 141/141 teszt zöld. A wsnsim/models/ csomag kész modelleket tartalmaz. A spec (7.7. hét) ARQ Stop-and-Wait modellt, PDR vs energia sweep kísérletet és PROMPTLOG frissítést írt elő.

**Prompt:**
Részletes specifikáció alapján: ARQConfig, ARQResult (frozen), ARQLink (Stop-and-Wait, idő-lépéses mód), ARQStats; tesztek 5 osztályban; experiments/arq_sweep.py retry_limit x távolság sweep.

**MI válasz összefoglalója:**

- wsnsim/models/reliability.py — ARQConfig dataclass (retry_limit, ack_timeout_us, backoff_base_us, backoff_factor, ack_size_bytes); ARQResult (frozen=True); ARQLink osztály distance_m paraméterrel, 	ransmit(packet, at_us) → idő-lépéses Stop-and-Wait logika (TX regisztrálás, channel.prr() döntés, ACK energia, exponenciális backoff); ARQStats (add, pdr, mean_attempts, mean_energy_j, total_packets).
- wsnsim/models/__init__.py — ARQConfig, ARQLink, ARQResult, ARQStats hozzáadva.
- 	ests/test_reliability.py — 24 unit teszt 5 osztályban: TestARQConfig (2), TestARQLinkSuccess (5), TestARQLinkRetry (4), TestARQLinkDrop (5), TestARQStats (8).
- experiments/arq_sweep.py — retry_limit ∈ {0,1,2,3,5} × distance_m ∈ {5,10,20,30,40,50}, 200 csomag/kombináció, sigma=3 dB, seed=42; stdout táblázat + 2-panel ábra.

**Döntésem:**

- Elfogadva: 
retry_limit = újraküldések száma (nem beleértve az első adást), tehát maximális összes kísérlet = 
retry_limit + 1. Ez a fizikailag legkézenfoghatóbb szemantika, és a sweep retry_limit=0 esetén értelmes (1 kísérlet, nincs újraküldés) PDR görbét ad.
- Elfogadva: distance_m a konstruktorban — a spec nem definiálta explicit, de a channel.prr() távolság nélkül nem hívható.
- Elfogadva: ACK adásideje arányos ack_size_bytes / packet.size_bytes * tx_duration_us skálával.
- Elfogadva: backoff ideje alatt az energia-modell flush() integrál, nem kell külön transition().

**Validálás:**

- [x] pytest tests/ --tb=short → **165/165 teszt zöld** (141 → 165, +24       reliability teszt) ✅
- [x] reliability.py coverage: **96%** ✅
- [x] python experiments/arq_sweep.py → táblázat és ábra generálva ✅
- [x] retry=0, d=5m: PDR=1.000; retry=0, d=40m: PDR=0.000 ✅
- [x] retry=5, d=20m: PDR=0.935 (látható PDR-javulás retry növeléssel) ✅
- [x] reports/figures/arq_sweep.png mentve (2 panel: PDR és energia vs távolság) ✅
- [x] Determinizmus: azonos seed → azonos sweep-eredmény ✅
