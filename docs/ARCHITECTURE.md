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
      ◄─ diary.json    ───  osobní návštěvy a výlety
```

Dropbox / USB je jen doprava souborů. Netlify je jen doručení prázdného HTML app shellu na iPhone ([Netlify Drop](https://app.netlify.com/drop)), stejný postup jako u IphoneApp. Katalog a deník se na Netlify **nenahrávají**.

## Zdroj pravdy

Vždy existuje **jeden** admin PC s jednou SQLite. Vývoj je v tomto repozitáři. Až se aplikace předá, zkopíruje se přenositelná složka na PC správce. Souběžná administrace ze dvou PC není.

`Place.public_id` (UUIDv7) se po INSERT nikdy nemění. JSON `places[].id` je toto UUID, ne integer PK.

## PC

FastAPI na `127.0.0.1`, SQLite, Alembic, Jinja2 + HTMX + Pico.css. CRUD katalogu, importy s matchingem, zápis návštěv na detailu místa, výlety na `/trips`, export `catalog.json`, import/export `diary.json`, ruční záloha a obnova SQLite (`/backup`), Poblíž na `/nearby`.

## PWA

Vite + React + TypeScript + Dexie + `vite-plugin-pwa`. Na telefonu žádný Python. PWA importuje `catalog.json` do IndexedDB (store `places`) a zapisuje návštěvy do store `visits` / `place_states`. Záložka Mapa umí Poblíž (GPS / napsané místo, šoupátko km). Aktualizace katalogu deník nemění; návštěvy u zmizelého `place_id` zůstanou a UI je označí jako „místo už není v katalogu“. App shell na [Netlify Drop](https://app.netlify.com/drop) je prázdný — bez `catalog.json` i `diary.json`.

Podrobnosti fází: [PLAN.md](../PLAN.md).
