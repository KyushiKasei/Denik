# Vývoj

## Požadavky

- Windows, Python 3.12+
- Pro Fázi 1 není Node potřeba

## Start PC aplikace

```powershell
.\scripts\start-pc.ps1
```

Skript vytvoří `.venv`, nainstaluje balíček a spustí Uvicorn na `http://127.0.0.1:8765`.

## Kam se ukládá SQLite

Výchozí (vývoj v Dropboxu):

```text
%LOCALAPPDATA%\PamatkyDenik\
  pamatky.sqlite3
  backups\
  logs\
```

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

Aplikace volá `upgrade head` při startu.

## Testy

```powershell
.\.venv\Scripts\python -m pytest
```

Testy používají dočasnou SQLite, ne LocalAppData.

## Co v této fázi nepřidávat

Importery, CRUD míst, PWA, JSON export. To jsou další fáze v PLAN.md.
