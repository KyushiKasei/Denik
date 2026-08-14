# Památky — osobní katalog a deník

Lokální katalog hradů, zámků a dalších historických míst v ČR + cestovatelský deník na telefonu.

- **PC** spravuje master data v SQLite (jediný zdroj pravdy katalogu).
- **iPhone PWA** je HTML stránka: katalog jen čte, zapisuje návštěvy.
- Mezi PC a mobilem není server ani REST API. Přenos je `catalog.json` a `diary.json` (Dropbox, USB, …).
- Interní ID památky (`public_id`) se po vytvoření nikdy nemění.

Plán a datový model: [PLAN.md](PLAN.md).

## Stav

Hotová je **Fáze 1**: skeleton PC aplikace, SQLite, migrace, model Place, prázdná stránka Katalog.

Ještě není: CRUD míst, importery, PWA, export JSON.

## PC aplikace — spuštění

Dvojklik na `start-pc.bat` v kořeni projektu.

Nebo v PowerShellu:

```powershell
.\scripts\start-pc.ps1
```

Otevře se `http://127.0.0.1:8765`. Okno nenechávej zavřít, dokud aplikaci používáš (Ctrl+C ji vypne). Potřeba je Python 3.12+. Node ani Cursor na cílovém PC nebudou potřeba — to řeší až přenositelný balíček ke konci projektu.

## Databáze

Při vývoji v Dropboxu se SQLite ukládá mimo sync:

```text
%LOCALAPPDATA%\PamatkyDenik\pamatky.sqlite3
```

Přenositelná instalace později ponese `data/pamatky.sqlite3` vedle aplikace. Živou SQLite nenechávej v Dropboxu.

Vytvoření schématu: při startu aplikace (Alembic migrace + seed typů). Ručně:

```powershell
.venv\Scripts\python -m alembic -c pc-app\alembic.ini upgrade head
```

(nastav `PAMATKY_DATA_DIR`, nebo nech výchozí LocalAppData)

## PWA

Až ve fázi 7. Na iPhone se nainstaluje z [Netlify Drop](https://app.netlify.com/drop) stejně jako jazyková appka — ale na Netlify půjde jen prázdná aplikace, ne katalog.

## Export / import

- Export `catalog.json` — fáze 6
- Import / export `diary.json` — fáze 8

## Testy

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
```
