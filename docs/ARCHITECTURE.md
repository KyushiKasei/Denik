# Architektura

Dvě aplikace, žádný cloud mezi nimi.

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
    │
    ├─ výměnná složka (Dropbox / USB): diary.zip → PC, zpět diary-z-pc.zip / catalog.json
    │
    └─ volitelně LAN :8766 /lan  (PIN, 15 min, výchozí vypnuto)
         stejné diary.zip / catalog.json, ne editor katalogu
```

Dropbox / USB je doprava souborů, když nejste na stejné Wi-Fi. Na PC lze jednou nastavit **složku pro telefon** (typicky Dropbox): telefon tam uloží `diary.zip`, tlačítko na přehledu deník sloučí a zapíše `diary-z-pc.zip`. Není to Dropbox API. Na domácí síti může PC na 15 minut otevřít jen stránku sloučení (`http://<LAN-IP>:8766/lan`). Nainstalovaná PWA (HTTPS) na tuto adresu sama nesahá — telefon otevře Safari (to **není** PWA na ploše), nahraje export a stáhne sloučený zip. Netlify je jen doručení prázdného HTML app shellu na iPhone ([Netlify Drop](https://app.netlify.com/drop)). Katalog a deník se na Netlify **nenahrávají**.

## Zdroj pravdy

Vždy existuje **jeden** admin PC s jednou SQLite. Vývoj je v tomto repozitáři. Až se aplikace předá, zkopíruje se přenositelná složka na PC správce. Souběžná administrace ze dvou PC není.

`Place.public_id` (UUIDv7) se po INSERT nikdy nemění. JSON `places[].id` je toto UUID, ne integer PK.

## PC

FastAPI na `127.0.0.1:8765`, SQLite, Alembic, Jinja2 + HTMX + Pico.css. CRUD katalogu, importy s matchingem, zápis návštěv na detailu místa, výlety na `/trips`, export `catalog.json`, import/export `diary.json`, výměnná složka pro telefon (`diary.zip` / `diary-z-pc.zip`), ruční záloha a obnova SQLite (`/backup`), Poblíž na `/nearby`. Volitelná domácí relace spustí druhý listener na `0.0.0.0:8766` jen se stránkou `/lan` (PIN, upload/download deníku, stažení katalogu). Safari na `/lan` deník z PWA nevidí.

## PWA

Vite + React + TypeScript + Dexie + `vite-plugin-pwa`. Na telefonu žádný Python. PWA importuje `catalog.json` do IndexedDB (store `places`) a zapisuje návštěvy do store `visits` / `place_states`. Záložka Mapa umí Poblíž (GPS / napsané místo, šoupátko km). Aktualizace katalogu deník nemění; návštěvy u zmizelého `place_id` zůstanou a UI je označí jako „místo už není v katalogu“. App shell na [Netlify Drop](https://app.netlify.com/drop) je prázdný — bez `catalog.json` i `diary.json`.

Podrobnosti fází: [PLAN.md](../PLAN.md).
