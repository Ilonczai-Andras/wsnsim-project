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

## 2026-03-07

### 1. Projektstruktúra és fejlesztői környezet kialakítása

**Cél:**  
A wsnsim Python csomag alapvető repo-vázának, fejlesztői környezetének és dokumentációjának elkészítése egyetlen, jól specifikált AI-prompttal.

**Kontextus:**  
Üres workspace (`d:\wsnsim-project`), csak egy üres `README.md` létezett. Semmilyen kód, konfiguráció vagy mappastruktúra nem volt még jelen.

**Prompt:**

> Egy Python-alapú vezeték nélküli szenzorhálózat szimulátor (wsnsim) fejlesztésébe kezdek.  
> Segíts az alapvető projektstruktúra és a fejlesztői környezet kialakításában az alábbiak szerint:
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
