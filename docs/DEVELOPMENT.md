# Vývoj

## Požadavky

- Windows, Python 3.12+
- Pro PWA (Fáze 7) Node.js 18+ na vývojářském PC. Na telefonu ani na cílovém deníkovém PC se Node neinstaluje.

## Start PC aplikace

```powershell
.\scripts\start-pc.ps1
```

Skript vytvoří `.venv`, nainstaluje balíček a spustí Uvicorn na `http://127.0.0.1:8765`.

- `/` — dashboard nad katalogem i deníkem (počty návštěv), export `catalog.json` / `diary.json`, import deníku
- `/places` — seznam, hledání, filtry včetně navštíveno / chci navštívit, stránkování, export `catalog.json`
- `/places/{id}` — detail místa: zápis návštěv a osobního stavu deníku (stejná pole jako PWA)
- `/visits` — seznam návštěv
- `/trips` — výlety (seřazené zastávky, vzdušná km); stejný zápis jako v `diary.json`
- `/nearby` — Poblíž: GPS / obec nebo název / souřadnice, šoupátko km, Leaflet + seznam
- `/places/new` — nové místo
- `/import` — Import centrum (Wikidata, Památkový katalog, RÚIAN, NPÚ, Commons, Wikipedia, volitelné OSM, fixture)
- `/import/reviews` — fronta nejasných shod; tlačítko přepočítá otevřené položky podle aktuálních pravidel B (se zálohou)
- `/backup` — ruční záloha a obnova SQLite

Export z příkazové řádky:

```powershell
.\.venv\Scripts\python -m app.cli export-catalog
.\.venv\Scripts\python -m app.cli export-catalog -o C:\cesta\catalog.json
.\.venv\Scripts\python -m app.cli export-diary
.\.venv\Scripts\python -m app.cli import-diary C:\cesta\diary.json
.\.venv\Scripts\python -m app.cli import-source wikidata
.\.venv\Scripts\python -m app.cli import-source wikipedia
.\.venv\Scripts\python -m app.cli import-source osm
```

Výchozí soubory: `%LOCALAPPDATA%\PamatkyDenik\export\catalog.json` a `diary.json`.

## Kam se ukládá SQLite

Výchozí (vývoj v Dropboxu):

```text
%LOCALAPPDATA%\PamatkyDenik\
  pamatky.sqlite3
  backups\
  logs\
  export\
    catalog.json
    diary.json
  vite\                    # cache Vite (mimo Dropbox, jinak EBUSY)
  cache\
    wikidata_last.json
    pamatkovy_katalog_last.json
    ruian_last.json
    npu_last.json
    commons_last.json
    wikipedia_last.json
    osm_last.json
```

Log založení / úpravy / archivace: `logs\pc-app.log`.

Wikidata import na `/import` nebo `python -m app.cli import-source wikidata` stahuje SPARQL po typech (hrad, zámek, zřícenina, tvrz, rozhledna, zoo, jeskyně). Může trvat několik minut. Tvrz je Wikidata `Q1408475` (fortified house); QID `Q2288643` ze staršího zadání je lékařská položka. Rozhledna je `Q1440300`, zoo `Q43501`, jeskyně `Q35509`.

Další zdroje ve stejném Import centru: Památkový katalog (CSV), RÚIAN (kódy obce/okresu/kraje a obec ze souřadnic), NPÚ spravované objekty (URL, ne texty), Commons metadata k P18, Wikipedia URL/úplnost, OSM jako volitelný doplněk.

Vynucená cesta (testy, přenositelný režim):

```powershell
$env:PAMATKY_DATA_DIR = "C:\cesta\k\data"
```

```powershell
$env:PAMATKY_PORTABLE = "1"   # použije <repo>/data
```

Živou databázi nenechávej v Dropboxu ani OneDrive.

## Migrace

Nová migrace:

```powershell
.\.venv\Scripts\python -m alembic -c pc-app\alembic.ini revision -m "popis"
```

Aplikace volá `upgrade head` při startu. Fáze 8 přidala migraci `004_phase8_diary` (`visits`, `place_journal_states`, `diary_import_issues`).

## Start PWA

```powershell
.\scripts\start-pwa.ps1
```

Dev server: `http://127.0.0.1:5173`. Záložky: Katalog, Mapa (Poblíž), Soubory, Info. Offline shell ověř `npm run build` a `npm run preview` ve složce `pwa/`.

Příprava složky pro [Netlify Drop](https://app.netlify.com/drop):

```powershell
.\scripts\pripravit-deploy-netlify.ps1
```

Na Drop patří jen obsah `deploy-netlify/` (app shell). `catalog.json` ani `diary.json` se tam nesmí objevit.

## Testy

```powershell
.\.venv\Scripts\python -m pytest
```

Testy používají dočasnou SQLite, ne LocalAppData.

```powershell
cd pwa
npm test
```

## Akceptační scénář MVP (kapitola 32)

Bez zásahu do SQL, jen UI a soubory:

1. Spustit PC (`start-pc.bat`) — SQLite vznikne v `data_dir`.
2. Import fixture nebo Wikidata na `/import`.
3. Opakovaný import — žádné duplicity, stejné `public_id`.
4. Nejasná shoda v `/import/reviews`.
5. Ruční oprava názvu přežije další import.
6. Export `catalog.json`.
7. PWA: nahrát katalog, najít Bouzov, dvě návštěvy, export `diary.json`.
8. PC: import deníku, obě návštěvy u Bouzova, druhý import bez duplicit.
9. Úprava/archivace katalogu, nový `catalog.json`, v PWA nahradit katalog — návštěvy zůstanou (osiřelé, pokud místo zmizelo).
10. `/backup` — ruční záloha a obnova SQLite.

Automaticky: `pytest pc-app/tests/test_mvp_acceptance.py` a `pwa/tests/orphans.test.ts`.

Formáty souborů: [JSON_FORMATS.md](JSON_FORMATS.md). Importy a matching: [IMPORTS.md](IMPORTS.md).

## Mimo MVP

Automatický Dropbox, REST mezi zařízeními, účty, osobní fotky, číselník osob, výlety, gamifikace, offline mapové dlaždice, editace master dat v PWA.
