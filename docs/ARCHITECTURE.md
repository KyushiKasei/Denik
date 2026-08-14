# Architektura

Dvě aplikace, žádný server mezi nimi.

```text
EXTERNÍ ZDROJE
      │
      ▼
PC (Python, SQLite)          ← jediný zdroj pravdy katalogu
      │
      ├─ catalog.json  ──►  PWA (iPhone / prohlížeč)
      │                         IndexedDB: katalog + deník
      │
      ◄─ diary.json    ───  osobní návštěvy
```

Dropbox / USB je jen doprava souborů. Netlify je jen doručení prázdného HTML app shellu na iPhone ([Netlify Drop](https://app.netlify.com/drop)), stejný postup jako u IphoneApp. Katalog a deník se na Netlify **nenahrávají**.

## Zdroj pravdy

Vždy existuje **jeden** admin PC s jednou SQLite. Vývoj je v tomto repozitáři. Až se aplikace předá, zkopíruje se přenositelná složka na PC správce. Souběžná administrace ze dvou PC není.

`Place.public_id` (UUIDv7) se po INSERT nikdy nemění. JSON `places[].id` je toto UUID, ne integer PK.

## PC

FastAPI na `127.0.0.1`, SQLite, Alembic, Jinja2 + HTMX (HTMX od fáze 2). Importery až od fáze 3.

## PWA

Vite + React + TypeScript + Dexie — od fáze 7. Na telefonu žádný Python.

Podrobnosti fází: [PLAN.md](../PLAN.md).
