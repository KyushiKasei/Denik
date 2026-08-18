# Památky — osobní katalog a deník

Lokální katalog hradů, zámků a dalších historických míst v ČR + cestovatelský deník na telefonu.

- **PC** spravuje master data v SQLite (jediný zdroj pravdy katalogu).
- **iPhone PWA** je HTML stránka: katalog jen čte, zapisuje návštěvy.
- Mezi PC a mobilem není cloud ani účty. Přenos je `catalog.json` a `diary.json` (Dropbox, USB), nebo volitelně domácí Wi-Fi na 15 minut.
- Interní ID památky (`public_id`) se po vytvoření nikdy nemění.

Plán: [PLAN.md](PLAN.md). Formáty souborů: [docs/JSON_FORMATS.md](docs/JSON_FORMATS.md). Importy: [docs/IMPORTS.md](docs/IMPORTS.md).

## Stav

**MVP je hotové (Fáze 1–9).** Fáze 10: Poblíž na mapě. Fáze 11: čistota katalogu (jednotné zříceniny).

Mimo MVP: automatický Dropbox, veřejné REST / cloud, účty, offline mapy.

## Start

### PC aplikace

Dvojklik na `start-pc.bat`, nebo v PowerShellu:

```powershell
.\scripts\start-pc.ps1
```

Otevře se `http://127.0.0.1:8765`. Okno nenechávej zavřít, dokud aplikaci používáš (Ctrl+C ji vypne). Potřeba je Python 3.12+.

| Adresa | Co tam je |
|---|---|
| `/` | přehled, export katalogu i deníku, import deníku |
| `/places` | seznam, filtry, export `catalog.json` |
| `/diary` | deník, pas, ročník |
| `/trips` | výlety |
| `/nearby` | mapa Poblíž (GPS / obec / souřadnice, šoupátko km) |
| `/import` | Wikidata a další zdroje, review fronta |
| `/backup` | ruční záloha a obnova SQLite |

### PWA

Dvojklik na `start-pwa.bat`, nebo:

```powershell
.\scripts\start-pwa.ps1
```

Otevře se `http://127.0.0.1:5173`. Na iPhone: `.\scripts\pripravit-deploy-netlify.ps1`, složku `deploy-netlify` přetáhnout na [Netlify Drop](https://app.netlify.com/drop), v Safari otevřít HTTPS URL a Přidat na plochu. Na Netlify je jen prázdný app shell, ne katalog.

## Databáze

Při vývoji v Dropboxu se SQLite ukládá mimo sync:

```text
%LOCALAPPDATA%\PamatkyDenik\pamatky.sqlite3
```

Přenositelná instalace ponese `data/pamatky.sqlite3` vedle aplikace. Živou SQLite nenechávej v Dropboxu — korupce. Záloha a obnova: `/backup` v PC UI, nebo zkopírovat soubor při vypnuté aplikaci.

Vynucená cesta: `$env:PAMATKY_DATA_DIR = "C:\cesta"`, nebo `$env:PAMATKY_PORTABLE = "1"` (`<repo>/data`).

## Export a import souborů

Okruh bez serveru:

1. Na PC importovat zdroje (`/import`) nebo založit místo ručně.
2. Exportovat `catalog.json` (přehled nebo `/places`).
3. V PWA na záložce Nastavení nahrát `catalog.json`.
4. Zapsat návštěvy, exportovat `diary.json`.
5. Na PC na přehledu importovat `diary.json`.
6. Úprava katalogu na PC → nový `catalog.json` → v PWA nahradit jen místa. Návštěvy zůstanou; místo, které v katalogu zmizelo, se ukáže jako „místo už není v katalogu“.

CLI (z kořene projektu, s venv):

```powershell
.\.venv\Scripts\python -m app.cli export-catalog
.\.venv\Scripts\python -m app.cli export-catalog -o C:\cesta\catalog.json
.\.venv\Scripts\python -m app.cli export-diary
.\.venv\Scripts\python -m app.cli import-diary C:\cesta\diary.json
```

Výchozí soubory: `%LOCALAPPDATA%\PamatkyDenik\export\catalog.json` a `diary.json`.

Nevalidní JSON a neznámá `schema_version` se odmítnou. Stejný `diary.json` dvakrát nevytvoří duplicity. Deník nikdy nezakládá Place.

## Domácí Wi-Fi (volitelné)

Na přehledu PC lze na 15 minut zapnout domácí síť. Administrace zůstane na `127.0.0.1:8765`. Telefon v **Safari** (ne v nainstalované PWA) otevře `http://<IP-PC>:8766/lan`, zadá PIN z obrazovky PC, nahraje export deníku a stáhne sloučený `diary.zip` (volitelně `catalog.json`). V PWA se zip znovu importuje.

- Windows firewall se při prvním zapnutí zeptá — povolte jen **soukromé** sítě.
- Guest Wi-Fi s izolací klientů telefon k PC nepustí. Musí to být stejná privátní síť.
- Výchozí stav je vypnuto. Po 15 minutách nebo tlačítkem Vypnout listener zmizí.

## Testy

PC:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
```

PWA:

```powershell
cd pwa
npm install
npm test
```

Testy používají dočasnou SQLite, ne LocalAppData. Akceptační souborový okruh (kapitola 32 zadání) je v `pc-app/tests/test_mvp_acceptance.py` a `pwa/tests/orphans.test.ts`.
