# Datový model (Fáze 9)

Platný cílový model je v [PLAN.md](../PLAN.md) kapitole 6. Tady je to, co už existuje v SQLite.

## place_types

Číselník typů. Hradozámek není samostatný kód — místo dostane `CASTLE` i `CHATEAU`.

| code | name_cs |
|---|---|
| CASTLE | Hrad |
| CHATEAU | Zámek |
| RUIN | Zřícenina |
| FORTRESS | Pevnost |
| MANOR | Tvrz |
| PALACE | Palác / letohrádek |
| LOOKOUT_TOWER | Rozhledna |
| ZOO | Zoo |
| CAVE | Jeskyně |
| OTHER | Jiné |

## places

Master záznam památky. `public_id` je neměnný UUIDv7. Integer `id` se do JSON nikdy nedostane. `osm_opening_hours` je volitelný OSM řetězec (ODbL), v `catalog.json` stejnojmenné pole. Volitelně i `dogs`, `payment`, `amenities` (JSON seznam `toilets` / `cafe` / `playground`), `inception_year` a `architectural_style`.

M:N na typy přes `place_place_types`. Řádky se nemažou — archivace nastaví `archived_at`.

České popisky číselníků (`condition`, `visitability`, `quality_status`, `heritage_status`, `source_types`) jsou v `shared/enums.json`.

## Zdroje a ochrana ID

- `place_sources` — externí identita (`source_type` + `external_id`). Unikátní částečný index: jedno ID patří nejvýše jednomu Place.
- `place_source_values` — audit „co zdroj tvrdil“ o jednotlivém poli.
- `place_field_overrides` — ruční oprava v UI; import master pole nepřepíše.
- `place_photos` — ilustrační foto (URL a licence, ne binárně).

## Import

- `import_runs` — náhled / zápis / rollback, cesta k záloze.
- `import_reviews` + `import_review_candidates` — úroveň C, rozhodnutí [Sloučit] [Vytvořit jako nové] [Ignorovat].
- `import_field_changes` — zdroj se liší od chráněného masteru.

Matching A/B/C/D je v `app/services/matching.py` podle prahů v PLAN.md kapitole 8. Fixture importer čte `fixtures/import/*.json`. Wikidata SPARQL importer je v `app/importers/wikidata/`. Památkový katalog, RÚIAN, NPÚ, Commons, Wikipedia a OSM mají vlastní importery ve `app/importers/`. Místa bez GPS se importují se `quality_status = NEEDS_REVIEW`. Join přes ÚSKP / katalogové číslo / QID je úroveň A a `public_id` se nemění.

## app_meta

Klíče `catalog_version`, `last_catalog_export_at`, `last_catalog_content_hash`, `last_diary_import_at`, `last_diary_export_at`. Verze katalogu se zvedne jen když se změní hash kanonického JSON pole `places`.

## Osobní deník

- `visits` — návštěva má vlastní `public_id` (UUIDv7). Vazba na místo je `place_public_id` (JSON `place_id`). Integer `place_id` je volitelné FK; u neznámého UUID je NULL. Soft-delete přes `deleted_at`. Unikátnost je `public_id`, ne (místo, datum).
- `place_journal_states` — `want_to_visit`, `favorite`, `personal_note` podle `place_public_id`, včetně `updated_at` a `deleted_at`.
- `trips` + `trip_stops` — výlet má vlastní `public_id` (UUIDv7). Zastávka drží `place_public_id` a volitelné FK `place_id`. Neznámé UUID zastávku nesmaže a Place nezaloží. Soft-delete výletu přes `deleted_at`.
- `diary_import_issues` — neznámé `place_id` z importu deníku. Návštěva i zastávka výletu se uloží, Place se nezakládá.

Import `diary.json` slučuje podle kapitoly 10 v PLAN.md (last-write-wins podle `updated_at`). Zaškrtnuté **rodinné sloučení** po importu spojí živé návštěvy se stejným `place_id` a dnem (`visited_at`): lidé a poznámky se sjednotí, zůstane vyšší hodnocení, fotky se přesunou na vítěze. Katalogový import deníkové tabulky nemění. Archivace Place návštěvy ani výlety nemaže. Sloučení dvou Place převede návštěvy i zastávky výletů na vítěze, `Visit.public_id` a `Trip.public_id` se nemění. PC umí návštěvy i osobní stav zapisovat na detailu místa a výlety na `/trips` (stejná pole jako PWA); `public_id` návštěvy i výletu je nový UUIDv7, neodvozuje se z místa.

Kontrakt: `shared/schemas/diary.schema.json` (`schema_version` 1 i 2). Sample: `fixtures/diary.sample.json` (verze 1, bez `trips`). Export po této fázi je vždy verze 2 s polem `trips`.

PWA má Dexie store `visits`, `place_states` a `trips`; aktualizace katalogu je nenahrazuje. Před importem deníku ukládá snapshot posledních 5 deníků. Návštěvy i zastávky, jejichž `place_id` v novém katalogu chybí, zůstanou a UI je označí jako „místo už není v katalogu“.

## Zálohy SQLite

Nejsou tabulka. Před rizikovým importem a ručně z `/backup` vznikne kopie do `<data_dir>/backups/YYYYMMDD-HHMMSS-before-<source>.sqlite3`. Drží se posledních 20 souborů. Obnova nahradí živý `pamatky.sqlite3` (nejprve se aktuální soubor zazálohuje). Živou databázi nenechávej v Dropboxu.
