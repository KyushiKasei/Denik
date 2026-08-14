# PLAN.md — Osobní katalog hradů, zámků a historických míst

Stav: rozhodnutí uzavřena. Fáze 1 se implementuje.

Závazný funkční dokument: `_Zadani/ZADANI_AI_PROGRAMATOR_PAMATKY.md`.
Tento plán ho nerozšiřuje o server, REST mezi PC a mobilem, účty ani automatickou cloud synchronizaci.

---

## 1. Účel

Tento dokument je implementační smlouva pro další práci:

- zvolený stack,
- databázový model,
- přesný tvar `catalog.json` a `diary.json`,
- struktura repozitáře,
- malé, samostatně dokončitelné fáze,
- technické rozpory v zadání a výzkumu,
- věci, které navrhuji jinak, ale bez změny závazných principů.

---

## 2. Závazné principy

Tyto body se nemění bez tvého souhlasu:

1. Master data památek se mění pouze na PC.
2. PC používá lokální databázi.
3. Mobilní PWA dostává katalog pomocí JSON souboru.
4. Osobní deník se přenáší samostatným JSON souborem.
5. Mezi PC a mobilem nebude REST API ani vlastní server.
6. Interní ID památky (`Place.public_id`) se po vytvoření nikdy nemění.
7. Opakovaný import nesmí vytvářet duplicity.
8. Při nejisté shodě se má vyžádat ruční rozhodnutí, ne riskantní automatické sloučení.
9. Aktualizace katalogu nikdy nesmí poškodit osobní návštěvy.

Rozhodovací pořadí při konfliktu požadavků:

1. ochrana osobního deníku,
2. stabilita interních ID,
3. zabránění duplicitám,
4. možnost obnovy ze zálohy,
5. jednoduchost,
6. offline použitelnost PWA,
7. úplnost externích dat,
8. vzhled UI.

---

## 3. Co z podkladů použiji a co ne

### 3.1 Použiji

Z hlavního zadání prakticky vše: dvoučástovou architekturu PC + PWA, SQLite jako zdroj pravdy katalogu, souborový přenos, UUIDv7, `PlaceSource`, importní review frontu, field-level ochranu ručních změn, archivaci místo mazání, JSON Schema, fázování.

Z hlubokého výzkumu (ChatGPT) a Claude v2 pouze to, co posiluje zadání a neporušuje principy:

- Wikidata jako první importní páteř (CC0, SPARQL, QID jako externí ID).
- Památkový katalog / ÚSKP jako oficiální identitu, ne jako hlavní seznam turistických cílů.
- NPÚ weby jen pro objekty, které NPÚ spravuje, a jen strukturovaná fakta + URL, ne autorské texty.
- Wikimedia Commons jako ilustrační foto s evidencí licence a atribuce.
- RÚIAN jako normalizaci obce / okresu / kraje, ne jako plný adresní systém v MVP.
- OSM jen jako doplněk (geografie, případně přístupnost), ne jako master katalog.
- Hrady.cz a Kudy z nudy / CzechTourism jen jako ruční kontrolu úplnosti, bez scrapingu a bez API.
- Prioritu zdrojů podle typu údaje (status z NPÚ, souřadnice z katalogu/Wikidata, web z provozovatele).
- `visitability` jako číselník, ne boolean.
- Typy památek jako M:N (Bečov = hrad i zámek).
- iOS riziko smazání IndexedDB → `storage.persist()`, výzva „Přidat na plochu“, připomínka exportu deníku.
- Online mapa nebo odkaz do Mapy.cz / Google Maps; žádný offline balík map ČR v MVP.

### 3.2 Nepoužiji

Tyto návrhy z podkladů jsou v přímém rozporu se závazným zadáním, nebo zbytečně komplikují MVP:

| Návrh z podkladů | Proč ne |
|---|---|
| Supabase / Firebase / jakýkoli cloud backend | Porušuje „žádný server mezi PC a mobilem“. |
| Stejná PWA na PC i mobilu s IndexedDB jako master DB | Master katalog musí žít v SQLite na PC. |
| `uuid5` odvozené z Wikidata QID jako `public_id` | Externí ID nesmí být naše interní ID. Místo bez QID by nemělo stabilní identitu, místo založené z jiného zdroje by po doplnění QID nemohlo ID změnit. |
| Boolean `zpristupneno` | Zadání chce rozšiřitelný číselník přístupnosti. |
| Jeden enum `typ` na Place | Kombinované objekty (hrad+zámek) by se ořezaly. |
| `favorite` / `want_to_visit` na Place | Osobní stav patří do deníku, ne do master katalogu. |
| Osobní fotky, výlety, gamifikace, PDF, EXIF v MVP | Explicitně mimo MVP. Datový model na ně jen nesmí zavřít dveře. |
| File System Access API do Dropboxu | Pohodlné, ale ne v MVP. Stačí klasický export/import souboru. |
| Nasazení PWA na Netlify jako nutná část architektury | PWA je statický frontend. Hosting app shellu je provozní detail, ne zdroj pravdy. |
| Scraping Hrady.cz | Zakázáno zadáním i licencí. |
| Automatické zahazování míst bez GPS | Místa bez souřadnic patří do katalogu se stavem `NEEDS_REVIEW`. |

---

## 4. Technická konzistence zadání — problémy a rozpory

Níže jsou skutečné mezery nebo rozpory. U každého je navržené řešení, které budu považovat za platné, pokud neřekneš jinak.

### 4.1 Rozpor: `catalog.json` pole `id` vs databázové `public_id`

Zadání v DB používá `places.id` (integer PK) a `places.public_id` (neměnný UUID). V `catalog.json` i `diary.json` se UUID jmenuje `id` / `place_id`.

To není chyba, ale musí být tvrdé pravidlo:

- JSON `places[].id` = `Place.public_id`
- JSON `visits[].id` = `Visit.public_id`
- JSON `place_id` = `Place.public_id`
- Integer `places.id` a `visits.id` se do JSON nikdy nedostanou.

### 4.2 Rozpor: typ `CASTLE_CHATEAU` versus M:N typy

Zadání správně chce M:N typy a zároveň v počátečním číselníku uvádí `CASTLE_CHATEAU`. To je zbytečný třetí stav vedle `CASTLE` + `CHATEAU`.

**Návrh:** `CASTLE_CHATEAU` do číselníku nedávat. Hradozámek = vazby `CASTLE` a `CHATEAU` současně. V UI se to zobrazí jako „hrad a zámek“.

### 4.3 Mezera: práh „bezpečné“ pravděpodobné shody

Úroveň B (`MATCHED_PROBABLE`) má aktualizovat automaticky, ale zadání nedefinuje čísla. Bez prahů by každý implementátor slučoval jinak.

Konkrétní prahy jsou v kapitole 8. Jsou úmyslně přísné. Všechno ostatní jde do review.

### 4.4 Mezera: smazání návštěvy a opakovaný import deníku

Zadání vyžaduje idempotenci podle stabilního ID návštěvy, ale neřeší smazání. Bez `deleted_at` platí: smažu návštěvu na mobilu, na PC zůstane, starší `diary.json` ji znovu nevloží (to je v pořádku), ale smazání z mobilu se na PC nepřenese.

**Rozhodnuto:** u `Visit` i `PlaceJournalState` evidovat `deleted_at`. Import deníku slučuje podle ID; novější `updated_at` vyhrává; nastavené `deleted_at` je soft-delete. Fyzicky se návštěvy nemažou.

### 4.5 Mezera: konflikt deníku změněného na obou stranách

Jeden uživatel, ale PC i PWA umí deník exportovat i importovat. Pokud se stejná návštěva upraví na obou stranách mezi dvěma přenosy, zadání neříká, kdo vyhraje.

**Návrh:** last-write-wins podle `updated_at`. Při shodném času vyhraje příchozí soubor a zapíše se varování do logu. Tlačítko „nahradit celý deník“ v MVP nebude.

### 4.6 Mezera: neznámé `place_id` v deníku

Zadání říká ověřit existenci `place_id`. Archivované místo musí PC poznat. Neříká, co dělat s úplně neznámým UUID (starý export, ručně upravený soubor, místo ještě nenaimportované).

**Návrh:** návštěvu uložit s `place_public_id`, nenavázat FK pokud Place neexistuje, zařadit do fronty `DiaryImportIssue`. Nikdy nevytvářet `Place` z deníku.

### 4.7 Rozpor fází: dashboard a filtry „navštíveno“ v PC katalogu

Funkční požadavky PC (kap. 11) chtějí počty návštěv a filtr navštíveno/nenavštíveno. Deník je až fáze 8.

**Návrh:** ve fázi 2 dashboard jen nad katalogem (počty míst, typy, kvalita, chybějící GPS). Filtry a statistiky návštěv až ve fázi 8.

### 4.8 Překryv `EXTINCT` ve stavu objektu i v přístupnosti

`condition = EXTINCT` = fyzicky zaniklý objekt. `visitability = EXTINCT` = nelze navštívit, protože zanikl. Může existovat zřícenina (`condition = RUIN`) s `visitability = FREE_ACCESS`.

**Návrh:** oba číselníky nechat, ale UI a importery je nesmějí zaměňovat. Fyzický stav ≠ režim přístupu.

### 4.9 Rozpor výzkumu vs zadání: jedna PWA versus dvě aplikace

Claude v2 navrhuje jednu statickou PWA pro PC i telefon. Závazné zadání chce PC jako jediné místo editace master dat, se SQLite, importery, deduplikací a review frontou.

**Návrh:** dvě aplikace. PC = Python webová app na localhost. Mobil = React PWA. PC může deník prohlížet, ale katalog se edituje jen tam.

### 4.10 SQLite je jeden soubor a musí jít přenést

SQLite není přibitá k jednomu počítači. Celá master databáze je jeden soubor (`pamatky.sqlite3`) plus složka záloh. Přesun na jiný PC = zkopírovat složku aplikace (nebo jen `data/`) při vypnuté aplikaci.

**Nesmí** se nechat živou SQLite synchronizovat Dropboxem / OneDrive, zatímco je aplikace otevřená. To databázi umí tiše poškodit. Dropbox je transport pro `catalog.json` a `diary.json`. SQLite se kopíruje ručně, jako záloha.

Výchozí umístění: složka `data/` vedle spustitelné PC aplikace (přenositelná). V nastavení půjde cestu změnit. Při vývoji v Dropbox repu se použije cesta mimo sync (např. `%LOCALAPPDATA%\PamatkyDenik\`), aby se vývojová DB nesynchronizovala.

### 4.11 PWA a HTTPS

Přidání na plochu a Service Worker vyžadují HTTPS (výjimka `localhost`). To není REST API ani vlastní server mezi PC a mobilem. Je to jen doručení statického app shellu.

**Návrh pro později (ne MVP blokující):** PWA jako statické soubory. Pro reálný telefon stačí GitHub Pages / Cloudflare Pages, nebo ruční nahrání buildu. Katalog se i tak nahrává souborem, nenačítá se z hostingu. Do fáze 7 stačí Vite dev/preview.

### 4.12 Drobnosti, které sjednotím

- `alternative_names` je pole řetězců, ne jeden string.
- `quality_status` v zadání není vyjmenovaný; použiji `VERIFIED | PROBABLE | NEEDS_REVIEW | REJECTED`.
- ÚSKP ID a katalogové číslo Památkového katalogu jsou různá externí ID, ne jedno.
- Ignorovaná položka review se musí zapamatovat (`source_type` + `external_id`), jinak se při dalším importu vrátí.
- Archivované Place se do `catalog.json` neexportují. Návštěvy na PC zůstanou. PWA po aktualizaci katalogu ukáže návštěvu u „místo už není v katalogu“, deník nesmaže.

---

## 5. Technologický stack

Kritéria: jednoduchost, lokální Windows, minimum závislostí, čitelnost pro budoucí AI údržbu.

### 5.1 PC aplikace

| Vrstva | Volba | Proč |
|---|---|---|
| Jazyk | Python 3.12+ | Importery, SQLite, Windows, AI to dobře udržuje. |
| Web | FastAPI + Uvicorn na `127.0.0.1` | Lokální UI bez Electronu a Dockeru. Není to server mezi PC a mobilem. |
| UI | Jinja2 + HTMX + Pico.css | CRUD, import, review fronta bez druhé Node aplikace. |
| ORM | SQLAlchemy 2.0 (mapped style) | Explicitní model, dobré migrace. |
| Migrace | Alembic | Každá změna schématu je soubor v gitu. |
| DB | SQLite 3, WAL, `busy_timeout=5000` | Jeden soubor, záloha zkopírováním / `VACUUM INTO`. |
| UUID | UUIDv7 | Python 3.13+ má `uuid.uuid7()`. Na 3.12 knihovna `uuid-utils`. Nikdy UUIDv5 z Wikidata. |
| Validace JSON | `jsonschema` proti souborům v `shared/schemas` | Stejný kontrakt jako PWA. |
| HTTP klient importů | `httpx` | SPARQL, stažení CSV. Povinný `User-Agent`. |
| Testy | pytest | Kritické datové operace. |
| Start (vývoj) | `scripts/start-pc.ps1` | Venv, závislosti, Uvicorn, prohlížeč. Jen na vývojářském PC. |
| Start (provoz) | přenositelná složka, viz 5.4 | Na cílovém PC bez Cursoru, Node i instalovaného Pythonu. |

Proč ne React i na PC: PC musí mít Python kvůli importerům a SQLite. Druhý frontend by znamenal dva dev servery a Node jen kvůli administraci. HTMX stačí. Pokud by se PC UI později ukázalo jako limitující, lze ho vyměnit za React SPA proti stejnému FastAPI — datový model se nemění.

Proč ne Docker, Tauri, Electron: zbytečná infrastruktura pro jednouživatelskou localhost aplikaci. Přenositelný provoz řeší zabalený Python, ne další desktopový framework.

### 5.2 Mobilní PWA

| Vrstva | Volba | Proč |
|---|---|---|
| Jazyk | TypeScript | Kontrakt s JSON Schema, méně tichých chyb. |
| Build | Vite | Standard, rychlý, AI-známý. |
| UI | React | Zadání to preferuje, ekosystém PWA je k tomu hotový. |
| PWA | `vite-plugin-pwa` | Manifest + Service Worker bez vlastního frameworku. |
| Data | Dexie.js nad IndexedDB | Oddělené store pro katalog a deník. |
| Validace | Ajv proti `shared/schemas` | Stejné schéma jako PC. |
| Mapa v MVP | Leaflet + odkaz do externí mapy | Jednodušší než MapLibre. Offline mapy ČR nejsou v MVP. |
| Testy | Vitest | Import katalogu, ochrana deníku, validace JSON. |

PWA **nesmí** obsahovat editaci master dat, importery, slučování duplicit.

Na iPhonu to je obyčejná HTML/JS stránka přidaná na plochu. Žádný Python, žádný Node, žádný Cursor. Katalog a deník žijí v IndexedDB v Safari; ven a dovnitř jdou jen `catalog.json` a `diary.json`.

Stejnou PWA lze otevřít i v prohlížeči na jiném PC — jako deník a katalog, ne jako administrace master dat.

### 5.3 Sdílené

```text
shared/schemas/catalog.schema.json
shared/schemas/diary.schema.json
shared/enums.json
```

`enums.json` drží kódy typů, stavů, přístupnosti a zdrojů. PC i PWA je čtou. České popisky jsou jen v UI, v datech jsou anglické kódy.

### 5.4 Vývoj vs. provoz — co musí být na cílovém stroji

Vývojářské nástroje (Cursor, Python, Node, Git, pytest, Vite) jsou jen na vývojářském PC. Na iPhonu a na „jiném PC“ se neinstalují.

Rozdělení rolí:

| Kde | Co uživatel dělá | Co k tomu potřebuje |
|---|---|---|
| iPhone | katalog, zápis návštěv, export/import `diary.json`, import `catalog.json` | Safari, jednou otevřít HTTPS stránku PWA, Přidat na plochu. Nic jiného. |
| Jiný PC jen jako deník | totéž co telefon | prohlížeč (Edge/Chrome) a stejná PWA. Žádný Python, žádný Node. |
| PC administrace katalogu | import Wikidata, deduplikace, ruční opravy, export `catalog.json`, import deníku z telefonu | přenositelná složka PC aplikace + prohlížeč. Ne Cursor, ne Node, ne instalace Pythonu z python.org. |

Administrace **nejde** udělat čistou HTML stránkou v prohlížeči. Prohlížeč neumí bezpečně držet master SQLite, pouštět SPARQL importery a dělat zálohy souboru. Proto:

- **PWA** = finální HTML/JS, běží v Safari/Chrome.
- **Admin na PC** = zabalená lokální aplikace, která po dvojkliku otevře v prohlížeči `http://127.0.0.1:…` a vedle sebe má `data/pamatky.sqlite3`.

Obsah přenositelné složky (vznikne až ke konci, ne ve fázi 1):

```text
PamatkyDenik/
  PamatkyDenik.exe          # nebo start.bat + vestavěný Python
  data/
    pamatky.sqlite3         # celý katalog + deník na PC
    backups/
  export/                   # sem se ukládá catalog.json / diary.json podle volby
```

Přesun na jiný počítač: zkopírovat tuto složku (aplikace vypnutá). SQLite jde s sebou. Interní `public_id` se tím nemění.

iPhone a PWA: stejný postup jako u projektu IphoneApp. Build prázdného app shellu se nahraje na [Netlify Drop](https://app.netlify.com/drop), na telefonu se otevře vygenerovaná HTTPS URL a stránka se přidá na plochu. Na Netlify **nebude katalog ani deník** — na rozdíl od jazykové appky se sem data nepřibalují. Uživatel nahraje `catalog.json` v PWA ručně.

### 5.5 Co do stacku nepatří

Docker, Postgres, Redis, REST mezi zařízeními, OAuth, Dropbox SDK, Supabase, Firebase, ORM na PWA straně, vlastní UI framework, mikroservisy. Instalace Pythonu/Node na cílovém telefonu nebo na PC, které jen zapisuje deník.

---

## 6. Databázový model (PC, SQLite)

Jedna SQLite databáze, dva světy tabulek:

- **Master katalog** — Place a vše kolem zdrojů/importu.
- **Osobní deník** — Visit a PlaceJournalState.

Propojení je jen přes `Place.public_id`. Katalogový import deníkové tabulky nikdy nemění. Deníkový import nikdy nevytváří Place.

### 6.1 Číselníky

```text
place_types
-----------
id              INTEGER PK
code            TEXT UNIQUE NOT NULL   -- CASTLE, CHATEAU, RUIN, FORTRESS, MANOR, PALACE, OTHER
name_cs         TEXT NOT NULL
sort_order      INTEGER NOT NULL DEFAULT 0
```

Počáteční typy (bez `CASTLE_CHATEAU`):

| code | name_cs |
|---|---|
| CASTLE | Hrad |
| CHATEAU | Zámek |
| RUIN | Zřícenina |
| FORTRESS | Pevnost |
| MANOR | Tvrz |
| PALACE | Palác / letohrádek |
| OTHER | Jiné |

Další typy (klášter, rozhledna, jeskyně) se přidají migrací, až budou potřeba. Entita se nejmenuje Castle.

```text
condition:     PRESERVED | RUIN | REMAINS | REBUILT | EXTINCT | UNKNOWN
visitability:  REGULAR | SEASONAL | BY_APPOINTMENT | EVENTS_ONLY | FREE_ACCESS |
               EXTERIOR_ONLY | PRIVATE | TEMPORARILY_CLOSED | CLOSED | EXTINCT | UNKNOWN
quality_status: VERIFIED | PROBABLE | NEEDS_REVIEW | REJECTED
source_type:   wikidata | pamatkovy_katalog | uskp | npu | wikipedia |
               wikimedia_commons | osm | ruian | manual
```

### 6.2 Place — master záznam

```text
places
------
id                    INTEGER PK
public_id             TEXT UNIQUE NOT NULL   -- UUIDv7, neměnný
name                  TEXT NOT NULL
short_name            TEXT
alternative_names     TEXT NOT NULL DEFAULT '[]'  -- JSON pole řetězců
short_description     TEXT
condition             TEXT NOT NULL DEFAULT 'UNKNOWN'
visitability          TEXT NOT NULL DEFAULT 'UNKNOWN'
latitude              REAL
longitude             REAL
address               TEXT
municipality          TEXT
municipality_code     TEXT                   -- RÚIAN, volitelné
district              TEXT
district_code         TEXT
region                TEXT
region_code           TEXT
country               TEXT NOT NULL DEFAULT 'CZ'
official_website      TEXT
wikipedia_url         TEXT
opening_hours_url     TEXT
ticket_url            TEXT
heritage_status       TEXT                   -- NONE | KP | NKP | UNKNOWN
unesco                INTEGER NOT NULL DEFAULT 0  -- 0/1
quality_status        TEXT NOT NULL DEFAULT 'NEEDS_REVIEW'
created_at            TEXT NOT NULL          -- ISO-8601
updated_at            TEXT NOT NULL
archived_at           TEXT                   -- NULL = aktivní
```

Indexy: `public_id` UNIQUE; `(name)`; `(municipality, district, region)`; `(latitude, longitude)`; `(archived_at)`; `(quality_status)`.

Pravidla:

- `public_id` se generuje jednou při INSERT. Žádný UPDATE, žádný regenerátor, žádný odvozený UUID z externího ID.
- Řádky se fyzicky nemažou. Místo toho `archived_at`.
- Sloupce v `places` jsou **vyřešené master hodnoty** (to, co vidí UI a co jde do `catalog.json`).
- Původ jednotlivých hodnot je v `place_source_values` + `place_field_overrides`.

```text
place_place_types
-----------------
place_id         INTEGER NOT NULL FK places.id
place_type_id    INTEGER NOT NULL FK place_types.id
PRIMARY KEY (place_id, place_type_id)
```

### 6.3 Externí identifikátory a snapshoty zdrojů

```text
place_sources
-------------
id               INTEGER PK
place_id         INTEGER NOT NULL FK places.id
source_type      TEXT NOT NULL
external_id      TEXT
source_url       TEXT
fetched_at       TEXT
license          TEXT
raw_data         TEXT                 -- JSON snapshot relevantních polí
created_at       TEXT NOT NULL
updated_at       TEXT NOT NULL
```

Unikátnost — klíč k opakovaným importům:

```sql
CREATE UNIQUE INDEX ux_place_sources_external
  ON place_sources(source_type, external_id)
  WHERE external_id IS NOT NULL AND external_id != '';
```

Jeden `(source_type, external_id)` patří nejvýše jednomu Place. Wikidata `Q12345` proto nemůže vytvořit druhé místo.

Formát `external_id`:

| source_type | příklad |
|---|---|
| wikidata | `Q122922` |
| pamatkovy_katalog | katalogové číslo z CSV |
| uskp | rejstříkové číslo ÚSKP |
| osm | `relation/12345` / `way/…` / `node/…` |
| npu | slug nebo oficiální URL path |
| wikipedia | `cs:Karlštejn_(hrad)` |
| wikimedia_commons | název souboru |
| ruian | kód obce, pokud kdy budeme vázat místo na RÚIAN prvek |
| manual | prázdné nebo interní poznámka |

```text
place_source_values
-------------------
id                  INTEGER PK
place_source_id     INTEGER NOT NULL FK place_sources.id
field_name          TEXT NOT NULL      -- name, latitude, municipality, ...
value_json          TEXT NOT NULL      -- JSON-encoded skalár nebo pole
fetched_at          TEXT NOT NULL
UNIQUE (place_source_id, field_name)
```

Tato tabulka je audit „co zdroj tvrdil“. Master sloupec z ní automaticky přepisujeme jen tehdy, když na poli není override.

### 6.4 Ochrana ručních změn

```text
place_field_overrides
---------------------
place_id      INTEGER NOT NULL FK places.id
field_name    TEXT NOT NULL
value_json    TEXT NOT NULL
note          TEXT
created_at    TEXT NOT NULL
updated_at    TEXT NOT NULL
PRIMARY KEY (place_id, field_name)
```

Chování:

1. Uživatel opraví pole v UI → zapíše se override + aktualizuje se `places.<field>`.
2. Nový import vždy aktualizuje `place_sources` a `place_source_values`.
3. Pokud override existuje, `places.<field>` se nemění. Pokud se hodnota zdroje liší od masteru, vznikne `ImportFieldChange` (náhled „zdroj změnil hodnotu“).
4. Uživatel zvolí „Převzít novou hodnotu“ → override se smaže, master se nastaví ze zdroje.
5. Uživatel zvolí „Ponechat master“ → override zůstane, change se označí za vyřízenou.

Priorita zdrojů při automatickém zápisu pole bez override:

| Pole | Preferovaný zdroj |
|---|---|
| heritage_status, unesco | pamatkovy_katalog / uskp |
| municipality, district, region, kódy | ruian > pamatkovy_katalog > wikidata |
| latitude, longitude | pamatkovy_katalog > wikidata > osm |
| name | wikidata (cs) |
| official_website | npu > wikidata > osm |
| wikipedia_url | wikipedia / wikidata |
| short_description | vlastní / wikidata; NPÚ anotace jen pokud není licence problém a uživatel ji potvrdí |
| image | wikimedia_commons přes wikidata P18 |
| opening_hours_url, ticket_url | npu > oficiální web |

Ruční master má vždy přednost před touto tabulkou.

### 6.5 Fotografie katalogu

```text
place_photos
------------
id              INTEGER PK
place_id        INTEGER NOT NULL FK places.id
source          TEXT NOT NULL          -- wikimedia_commons, ...
source_url      TEXT
original_url    TEXT
thumbnail_url   TEXT
author          TEXT
license         TEXT
license_url     TEXT
attribution     TEXT
is_primary      INTEGER NOT NULL DEFAULT 0
created_at      TEXT NOT NULL
```

V MVP jen ilustrační foto, ne binárně v DB. Osobní `visit_photos` se v MVP nevytváří; až později jako samostatná tabulka s FK na `visits.id`, ne na Place.

### 6.6 Importní běhy a review

```text
import_runs
-----------
id                   INTEGER PK
source_type          TEXT NOT NULL
started_at           TEXT NOT NULL
finished_at          TEXT
records_received     INTEGER NOT NULL DEFAULT 0
records_created      INTEGER NOT NULL DEFAULT 0
records_updated      INTEGER NOT NULL DEFAULT 0
records_unchanged    INTEGER NOT NULL DEFAULT 0
records_review       INTEGER NOT NULL DEFAULT 0
records_failed       INTEGER NOT NULL DEFAULT 0
records_ignored      INTEGER NOT NULL DEFAULT 0
status               TEXT NOT NULL     -- running | preview | applied | failed | rolled_back
backup_path          TEXT
log                  TEXT
```

```text
import_reviews
--------------
id                    INTEGER PK
import_run_id         INTEGER NOT NULL FK import_runs.id
source_type           TEXT NOT NULL
external_id           TEXT
candidate_place_id    INTEGER FK places.id     -- nejlepší kandidát, může být NULL
match_score           REAL
match_reason          TEXT
raw_data              TEXT NOT NULL            -- JSON kanonického záznamu
status                TEXT NOT NULL            -- open | merged | created_new | ignored
resolution            TEXT
resolved_at           TEXT
```

```text
import_review_candidates
------------------------
id                  INTEGER PK
import_review_id    INTEGER NOT NULL FK import_reviews.id
place_id            INTEGER NOT NULL FK places.id
score               REAL
reason              TEXT
```

```text
import_field_changes
--------------------
id                  INTEGER PK
import_run_id       INTEGER NOT NULL FK import_runs.id
place_id            INTEGER NOT NULL FK places.id
field_name          TEXT NOT NULL
old_source_value    TEXT
new_source_value    TEXT
master_value        TEXT
status              TEXT NOT NULL      -- open | keep_master | take_source
resolved_at         TEXT
```

Po ručním [Sloučit]:

- `place_sources` se připojí k existujícímu Place,
- `public_id` se nemění,
- další import už jde úrovní A.

Po ručním sloučení **dvou existujících Place** (až bude v UI potřeba):

- vítěz si nechá `public_id`,
- zdroje, typy, fotky a návštěvy poraženého se převedou na vítěze,
- poražený se archivuje a do logu se zapíše `merged_into_public_id`,
- nikdy se negeneruje nový `public_id` a nikdy se nepřepisují návštěvy na nové ID.

Ignorované `(source_type, external_id)` se při dalším importu znovu neotevřou, dokud uživatel ignoraci nezruší.

### 6.7 Osobní deník

```text
visits
------
id                 INTEGER PK
public_id          TEXT UNIQUE NOT NULL    -- UUIDv7 návštěvy
place_id           INTEGER FK places.id    -- NULL pokud Place zatím neznáme
place_public_id    TEXT NOT NULL           -- vždy, i po archivaci Place
visited_at         TEXT                    -- YYYY-MM-DD
rating             INTEGER                 -- 1–5 nebo NULL
people_json        TEXT NOT NULL DEFAULT '[]'
note               TEXT
created_at         TEXT NOT NULL
updated_at         TEXT NOT NULL
deleted_at         TEXT                    -- soft-delete
```

Unikátnost návštěvy je `public_id`, ne `(place, datum)`. Stejné místo ve stejný den může mít dvě návštěvy, pokud vznikly jako dva záznamy. Opakovaný import stejného `diary.json` duplicitu nevytvoří, protože ID je stejné.

```text
place_journal_states
--------------------
id                 INTEGER PK
place_public_id    TEXT NOT NULL UNIQUE
place_id           INTEGER FK places.id
want_to_visit      INTEGER NOT NULL DEFAULT 0
favorite           INTEGER NOT NULL DEFAULT 0
personal_note      TEXT
updated_at         TEXT NOT NULL
deleted_at         TEXT
```

Účastníci v MVP: JSON pole jmen. Číselník `people` + M:N až později, bez změny `diary.json` schema_version pokud pole `people` zůstane polem řetězců.

Návštěvy se nevážou na integer `places.id` jako na jediný klíč. `place_public_id` je ten, který přežije archivaci, export a import.

### 6.8 Meta, zálohy

```text
app_meta
--------
key     TEXT PK
value   TEXT NOT NULL
```

Klíče: `catalog_version`, `last_catalog_export_at`, `last_catalog_content_hash`, `last_diary_import_at`.

Zálohy nejsou tabulka. Před rizikovým importem PC udělá `VACUUM INTO` (nebo bezpečný backup API) do:

```text
<data_dir>/backups/YYYYMMDD-HHMMSS-before-<source>.sqlite3
```

`data_dir` je u přenositelné aplikace `./data` vedle exe, při vývoji v Dropboxu mimo sync (např. `%LOCALAPPDATA%\PamatkyDenik\`). Drží se posledních 20 záloh. UI umožní ruční zálohu, obnovení a změnu složky dat.

### 6.9 Co v DB úmyslně není (zatím)

- `trips` / `trip_stops` — fáze po MVP, nesmí blokovat model Place/Visit.
- `visit_photos` — totéž.
- `people` tabulka — totéž.
- Binární obrázky.
- Uživatelé, role, auth.

---

## 7. Kanonický importní záznam

Každý importer vrací stejnou strukturu. UI v tom není.

```text
CanonicalRecord
---------------
source_type          str
external_id          str | null
external_ids         dict   # {"wikidata": "Q…", "uskp": "…", "osm": "relation/…"}
name                 str
alternative_names    list[str]
types                list[str]          # kódy place_types
condition            str | null
visitability         str | null
latitude             float | null
longitude            float | null
address              str | null
municipality         str | null
district             str | null
region               str | null
short_description    str | null
official_website     str | null
wikipedia_url        str | null
heritage_status      str | null
source_url           str | null
license              str | null
image                dict | null
raw                  dict
fetched_at           str
```

Importer nesmí sahat do `places` přímo. Matching + apply vrstva je společná.

---

## 8. Deduplikace a opakovaný import

Pořadí je pevné. První úspěšná úroveň vyhraje. Při více různých Place na úrovni A → review, neslučovat.

### Úroveň A — `MATCHED_EXACT`

Shoda, pokud existuje `place_sources` s:

- stejným `(source_type, external_id)`, nebo
- jakýmkoli ID z `external_ids` proti už uloženému zdroji (Wikidata QID, katalogové číslo, ÚSKP, OSM ref).

Výsledek: aktualizuj existující Place, **nikdy** negeneruj `public_id`. Nově viditelná externí ID se připojí k témuž Place.

### Úroveň B — `MATCHED_PROBABLE` (automaticky jen při tvrdé shodě)

Normalizace názvu: lowercase, odstranění diakritiky pro porovnání, sjednocení mezer, odstranění prefixů `statni hrad|hrad|zamek|zricenina|tvrz|zamecek|statni zamek`.

Automatická shoda, pokud platí **jedna** z těchto sad:

1. vzdálenost ≤ 100 m **a** podobnost názvu ≥ 0,90 **a** (stejná obec nebo obec na jedné straně chybí) **a** kompatibilní typy,
2. identický normalizovaný název **a** stejná obec **a** vzdálenost ≤ 300 m,
3. identický normalizovaný název **a** stejný okres **a** vzdálenost ≤ 80 m.

Kompatibilní typy: prázdná množina na jedné straně, nebo neprázdný průnik, nebo `{CASTLE, CHATEAU, RUIN, MANOR}` mezi sebou. `OTHER` samo o sobě nestačí k automatickému sloučení.

Každé automatické B se zapíše do `import_runs.log` včetně důvodu a vzdálenosti.

### Úroveň C — `IMPORT_REVIEW`

Podezření, ale ne dost jistota. **Nový Place se nevytvoří.**

Typicky:

- vzdálenost ≤ 400 m a podobnost ≥ 0,75,
- stejná obec a podobnost ≥ 0,82,
- stejný okres a identický normalizovaný název, ale vzdálenost > 80 m,
- dvě různá existující Place by vyhovovala úrovni B.

UI: importovaný objekt, kandidáti, GPS rozdíl, obec, [Sloučit] [Vytvořit jako nové] [Ignorovat].

### Úroveň D — nové místo

Žádný kandidát A/B/C → INSERT Place, nový UUIDv7, první `place_sources` řádek.

### Opakovaný import — očekávaný výsledek

```text
records_created + records_updated + records_unchanged + records_review + records_ignored + records_failed
  == records_received

0 ztracených public_id
0 duplicit na stejné (source_type, external_id)
```

Preview (dry-run) je povinné před aplikací větší aktualizace. Aplikace běží v transakci. Fatální chyba → rollback + zachovaná záloha.

---

## 9. Finální struktura `catalog.json`

Kontrakt mezi PC a PWA. Změna tvaru = zvýšení `schema_version`. Neznámá verze = odmítnout, nikdy tiše neparsovat.

`catalog_version` je celé číslo v `app_meta`. Zvýší se jen když se změní obsah míst (hash kanonického JSON polí `places`). Prázdný re-export se stejnými daty verzi nezvýší. PWA podle toho pozná „už mám tuto verzi“.

Archivovaná místa se neexportují.

### 9.1 Příklad

```json
{
  "schema_version": 1,
  "catalog_version": 17,
  "generated_at": "2026-08-14T20:30:00+02:00",
  "attribution": {
    "wikidata": "Wikidata contributors, CC0",
    "npu_opendata": "Geoportál památkové péče, Národní památkový ústav, CC BY-SA 4.0",
    "osm": "© OpenStreetMap contributors, ODbL",
    "commons": "Licence u jednotlivých fotografií"
  },
  "places": [
    {
      "id": "0198f23a-5e5e-7b31-a8be-8c99507a2138",
      "name": "Bouzov",
      "short_name": null,
      "alternative_names": ["Hrad Bouzov", "Státní hrad Bouzov"],
      "types": ["CASTLE"],
      "condition": "PRESERVED",
      "visitability": "REGULAR",
      "short_description": "Gotický hrad ze 14. století.",
      "heritage_status": "NKP",
      "unesco": false,
      "location": {
        "latitude": 49.704,
        "longitude": 16.891,
        "address": null,
        "municipality": "Bouzov",
        "district": "Olomouc",
        "region": "Olomoucký kraj",
        "country": "CZ"
      },
      "links": {
        "official": "https://www.hrad-bouzov.cz/",
        "wikipedia": "https://cs.wikipedia.org/wiki/Bouzov_(hrad)",
        "wikidata": "https://www.wikidata.org/wiki/Q122922",
        "heritage_catalog": "https://pamatkovykatalog.cz/...",
        "opening_hours": null,
        "tickets": null
      },
      "image": {
        "thumbnail_url": "https://commons.wikimedia.org/wiki/Special:FilePath/....jpg?width=640",
        "original_url": "https://commons.wikimedia.org/wiki/File:....jpg",
        "attribution": "Jan Novák / Wikimedia Commons",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/"
      }
    }
  ]
}
```

`image` může být `null`. Souřadnice mohou být `null` (místo bez GPS). PWA je zařadí do seznamu, ne na mapu.

### 9.2 Co do katalogu nesmí

- integer databázová ID,
- `raw_data`, importní logy, review fronta,
- `quality_status`, `archived_at`, override tabulky,
- osobní návštěvy, wishlist, poznámky,
- velké binární obrázky.

### 9.3 PWA při importu katalogu

1. Validace JSON Schema.
2. Kontrola `schema_version` (MVP: pouze `1`).
3. Diff proti aktuální IndexedDB: nové / změněné / zmizelé `id`.
4. Náhled počtů.
5. Transakčně nahradit **jen** store `places`.
6. Store `visits` a `place_states` se nemění.
7. Uložit `catalog_version`.
8. Návštěvy, jejichž `place_id` v novém katalogu chybí, zůstanou a v UI se označí jako osiřelé.

---

## 10. Finální struktura `diary.json`

Oddělený soubor. Katalog v něm není.

### 10.1 Příklad

```json
{
  "schema_version": 1,
  "exported_at": "2026-08-14T21:00:00+02:00",
  "exported_from": "pwa",
  "place_states": [
    {
      "place_id": "0198f23a-5e5e-7b31-a8be-8c99507a2138",
      "want_to_visit": true,
      "favorite": false,
      "personal_note": null,
      "updated_at": "2026-08-09T18:20:00+02:00",
      "deleted_at": null
    }
  ],
  "visits": [
    {
      "id": "0198f93b-618d-762f-a589-ccf375139dd9",
      "place_id": "0198f23a-5e5e-7b31-a8be-8c99507a2138",
      "visited_at": "2026-08-09",
      "rating": 5,
      "people": ["Jana", "Petr"],
      "note": "Výborná prohlídka.",
      "created_at": "2026-08-09T18:20:00+02:00",
      "updated_at": "2026-08-09T18:20:00+02:00",
      "deleted_at": null
    }
  ]
}
```

`exported_from` je `"pwa"` nebo `"pc"`. Slouží diagnostice, ne logice slučování.

### 10.2 Import deníku (PC i PWA) — idempotentní sloučení

Před importem záloha (PC: SQLite backup, PWA: snapshot posledních 5 deníků v IndexedDB).

Pro každou návštěvu podle `visits[].id`:

| Stav | Akce |
|---|---|
| ID neexistuje | INSERT |
| ID existuje a `incoming.updated_at` > `local.updated_at` | UPDATE všech deníkových polí |
| ID existuje a příchozí není novější | beze změny |
| `deleted_at` nastaveno u novějšího záznamu | soft-delete |

Stejné pravidlo pro `place_states` podle `place_id`.

Nikdy:

- nevytvářet Place,
- neměnit master sloupce Place,
- nevytvářet druhou návštěvu se stejným `id`.

Neznámé `place_id`: návštěvu uložit, zařadit issue, v UI „neznámé místo“.

Stejný soubor dvakrát = nula nových návštěv.

### 10.3 Odchylky od příkladu v zadání, které doporučuji

Zadání má u `place_states` jen `want_to_visit`, `favorite`, `personal_note`. **Rozhodnuto:** v schema_version 1 budou `updated_at` a `deleted_at` u návštěv i place_states. Smazání se přenáší soft-delete, záznamy se fyzicky nemažou.

---

## 11. Struktura repozitáře

```text
Denik/
  PLAN.md
  README.md
  .gitignore
  pyproject.toml                 # PC app + pytest
  pc-app/
    app/
      __init__.py
      main.py                    # FastAPI
      config.py                  # data_dir (přenositelná složka / LocalAppData při vývoji), port
      db/
        session.py
        models.py
        enums.py
      services/
        matching.py
        apply_import.py
        catalog_export.py
        diary_io.py
        backup.py
        overrides.py
      importers/
        base.py
        fixture.py               # fáze 3
        wikidata/
        pamatkovy_katalog/
        npu/
        ruian/
        wikimedia_commons/
        wikipedia/
        osm/
      web/
        templates/
        static/
        routers/
    alembic.ini
    migrations/
    tests/
  pwa/
    package.json
    vite.config.ts
    index.html
    src/
      db/                        # Dexie: places, visits, place_states, meta
      catalog/
      diary/
      pages/
    tests/
  shared/
    schemas/
      catalog.schema.json
      diary.schema.json
    enums.json
  fixtures/
    import/
      small_dataset.json         # fáze 3 matching testy
    catalog.sample.json
    diary.sample.json
  docs/
    ARCHITECTURE.md
    DATA_MODEL.md
    IMPORTS.md
    JSON_FORMATS.md
    DEVELOPMENT.md
  scripts/
    start-pc.ps1
    start-pwa.ps1
  _Zadani/                       # neměnit, není součást runtime
```

`.gitignore`: `.venv/`, `pwa/node_modules/`, `data/`, `*.sqlite3`, `.env`, build výstupy.

Živá data: `data/pamatky.sqlite3` vedle přenositelné aplikace. Při vývoji v Dropboxu: mimo sync, viz 4.10 a 5.4.

---

## 12. Fáze realizace

Každá fáze musí jít samostatně dokončit, otestovat a zastavit. Další fáze se nezačíná rozpracováním předchozí.

---

### Fáze 1 — Architektura a skeleton

**Cíl:** Vznikne spustitelná prázdná PC aplikace s migracemi a modelem Place, bez importerů a bez PWA funkcí.

**Implementuje se:**

- struktura repozitáře výše,
- `pyproject.toml`, Alembic, SQLAlchemy modely: `place_types`, `places`, `place_place_types`, `app_meta`,
- seed typů,
- FastAPI hello + prázdná stránka „Katalog“ (počítadlo 0 míst),
- `scripts/start-pc.ps1`,
- docs kostry: README, ARCHITECTURE, DATA_MODEL, DEVELOPMENT,
- draft `shared/enums.json`.

**Neimplementuje se:**

- importery, PlaceSource, review, deník, PWA, catalog.json export, UI CRUD.

**Testy:**

- migrace na prázdné SQLite projde,
- insert Place vygeneruje `public_id` (UUIDv7),
- druhý insert má jiné `public_id`,
- UPDATE name nezmění `public_id`,
- seed obsahuje očekávané typy.

**Hotovo když:** `start-pc.ps1` otevře localhost, DB soubor vznikne v nastaveném `data_dir` (mimo Dropbox sync), testy výše procházejí, dokumentace popisuje stack, přenositelnost SQLite a princip `public_id`.

---

### Fáze 2 — PC master katalog

**Cíl:** Ručně založit, upravit, vyhledat a filtrovat památky na PC.

**Implementuje se:**

- CRUD Place + typy M:N + lokalita + stav + přístupnost + odkazy,
- seznam: hledání, filtry (typ, kraj, okres, obec, stav, přístupnost, kvalita, chybějící GPS, chybějící typ), řazení, stránkování,
- detail,
- dashboard jen nad katalogem (celkem, podle typů, k revizi, bez GPS, bez typu),
- archivace (ne fyzické mazání),
- základní logování.

**Neimplementuje se:**

- import z webu, matching, deník, filtry navštíveno, catalog.json, PWA, fotky.

**Testy:**

- vytvoření místa,
- archivované místo zmizí z výchozího seznamu, ale v DB zůstane včetně `public_id`,
- místo může mít dva typy,
- validace souřadnic.

**Hotovo když:** Bez SQL jde založit „Bouzov“, upravit název, přiřadit typ CASTLE, archivovat a znovu najít v archivu se stejným `public_id`.

---

### Fáze 3 — Identita, import framework, ochrana ID

**Cíl:** Opakovatelný import z fixture souboru s matchingem, review frontou, override a zálohou. Žádný živý SPARQL.

**Implementuje se:**

- tabulky `place_sources`, `place_source_values`, `place_field_overrides`, `place_photos`, `import_runs`, `import_reviews`, `import_review_candidates`, `import_field_changes`,
- `CanonicalRecord` + matcher A/B/C/D,
- fixture importer (`fixtures/import/small_dataset.json`),
- preview + apply,
- automatická záloha před apply,
- UI Import centrum + fronta [Sloučit] [Vytvořit jako nové] [Ignorovat],
- UI override: master vs hodnota zdroje,
- transakce a rollback.

**Neimplementuje se:**

- Wikidata/NPÚ/OSM síťové importery,
- deník, PWA, catalog.json.

**Testy (povinné, ze zadání):**

- opakovaný import stejné fixture zachová `public_id`,
- nové místo dostane nové ID,
- stejné externí ID nikdy nevytvoří druhé místo,
- shoda přes Wikidata ID,
- shoda přes Památkový katalog ID,
- pravděpodobná shoda GPS+název v prahu B,
- nejasná shoda skončí v review a nevytvoří Place,
- ruční oprava názvu přežije druhý import,
- před apply vznikne záloha,
- fatální chyba apply → rollback.

**Hotovo když:** Fixture 1: N míst. Fixture 2 (opakování + 1 nové + 1 nejasné): 1 created, 0 duplicit, 1 review, všechna původní `public_id` beze změny. Testy výše zelené.

---

### Fáze 4 — Wikidata importer

**Cíl:** První skutečný zdroj. Opakované stažení bez duplicit.

**Implementuje se:**

- SPARQL klient s User-Agent, timeout, případné rozdělení dotazu po typech (hrad, zámek, zřícenina, tvrz),
- mapování QID, názvu, typů, souřadnic, webu, Wikipedie, P18, P4075 ÚSKP,
- místa bez GPS se importují, `quality_status = NEEDS_REVIEW`,
- preview počtů, apply přes framework z fáze 3,
- log běhu.

**Neimplementuje se:**

- NPÚ CSV, RÚIAN, Commons stažení nad rámec URL z P18, OSM, Wikipedia scrape, catalog.json, PWA.

**Testy:**

- unit testy parseru SPARQL JSON z fixture odpovědi,
- QID se uloží jako `place_sources(wikidata, Q…)`,
- druhý běh na stejné fixture: 0 created, public_id beze změny,
- konflikt dvou QID na jedno místo se nepřepisuje, jen se připojí chybějící ID.

**Hotovo když:** Na PC jde spustit Wikidata import, vznikne katalog v řádu stovek až tisíců míst, opakovaný běh nevytvoří duplicity, review fronta není prázdný slib.

---

### Fáze 5 — Další zdroje

Každý zdroj je vlastní podfáze se stejným pravidlem: po napojení musí fungovat deduplikace.

Pořadí:

1. Památkový katalog (CSV otevřená data) — ÚSKP / katalogové číslo, obec, okres, kraj, anotace, status.
2. RÚIAN — normalizace názvů obce/okresu/kraje a kódů, ne plný import adres.
3. NPÚ spravované objekty — oficiální URL, návštěvní odkazy, ne autorské texty a fotky.
4. Wikimedia Commons — metadata k P18 (author, license, attribution, thumbnail URL).
5. Wikipedia — jen URL / kontrola úplnosti, ne kopírování článků.
6. OSM — volitelný doplněk, matching přes tag `wikidata` nebo A/B/C.

**Neimplementuje se:** Hrady.cz scrape, CzechTourism API, stahování binárních fotek do DB.

**Testy po každém zdroji:** join přes externí ID nevytvoří duplicitní Place; nejasné páry → review; licence/atribuce uložená u zdroje.

**Hotovo když:** Wikidata místo s ÚSKP se při importu NPÚ CSV spojí úrovní A a `public_id` zůstane.

---

### Fáze 6 — `catalog.json`

**Cíl:** PC umí vyexportovat validní katalog a PWA (zatím klidně jen test) ho umí validovat.

**Implementuje se:**

- `shared/schemas/catalog.schema.json` (zmrazené schema_version 1),
- export z master hodnot Place,
- inkrement `catalog_version` podle content hashe,
- vynechání archivovaných,
- CLI i tlačítko v PC UI,
- sample ve `fixtures/catalog.sample.json`.

**Neimplementuje se:** PWA UI, deník.

**Testy:**

- validní export proti schématu,
- nevalidní soubor se odmítne,
- v JSON není integer `places.id`,
- archivované místo v JSON není,
- `places[].id` == `public_id`.

**Hotovo když:** Export `catalog.json` projde schématem a obsahuje Bouzov se stabilním UUID po opakovaném importu zdrojů.

---

### Fáze 7 — PWA katalog

**Cíl:** Telefon (nebo desktop Chrome) načte katalog, hledá a ukáže detail offline.

**Implementuje se:**

- Vite + React + TS + vite-plugin-pwa + Dexie,
- import `catalog.json` (file picker), validace, diff verzí, náhrada pouze store `places`,
- seznam, hledání, filtry typ/kraj/okres,
- detail, odkazy, GPS, odkaz do externí mapy,
- Leaflet mapa online, pokud jsou souřadnice,
- offline shell (app + naposledy importovaný katalog),
- výzva k přidání na plochu, pokus o `navigator.storage.persist()`.

**Neimplementuje se:** návštěvy, deník, editace master dat, offline mapové dlaždice, fotky uživatele.

**Testy:**

- validní catalog se načte,
- nevalidní a neznámá `schema_version` se odmítne,
- druhý import katalogu nepřepíše prázdný deníkový store (připravený test s fixture návštěvou vloženou mimo UI).

**Hotovo když:** Po nahrání `catalog.json` jde najít Bouzov, otevřít detail a po obnovení stránky bez sítě seznam pořád funguje.

---

### Fáze 8 — Deník

**Cíl:** Zápis návštěv na mobilu, `diary.json` tam i zpět, idempotence.

**Implementuje se:**

- PC tabulky `visits`, `place_journal_states`,
- `shared/schemas/diary.schema.json`,
- PWA: přidat návštěvu (datum, 1–5, people[], poznámka), více návštěv na jedno místo, want_to_visit, favorite, osobní poznámka,
- PWA export/import `diary.json`,
- PC import/export `diary.json`,
- sloučení podle pravidel kapitoly 10,
- seznam návštěv v PC detailu Place,
- dashboard doplněný o počet návštěv a unikátních navštívených míst,
- filtr navštíveno / chci navštívit,
- připomínka exportu deníku na PWA (14 dní nebo 5+ nových návštěv).

**Neimplementuje se:** osobní fotky, číselník osob, výlety, last-write UI konflikty nad rámec `updated_at`, Dropbox API.

**Testy:**

- validní / nevalidní diary,
- opakovaný import stejného souboru → 0 duplicit,
- dvě návštěvy stejného místa zůstanou dvě,
- aktualizace katalogu na PWA nesmaže návštěvy,
- archivace Place na PC nesmaže návštěvy,
- neznámé `place_id` nevytvoří Place.

**Hotovo když:** Splněné body 12–18 akceptačního scénáře MVP (návštěvy Bouzova, export, import na PC, druhý import bez duplicit).

---

### Fáze 9 — Propojení PC ↔ PWA a akceptace MVP

**Cíl:** Celý ruční souborový okruh bez sahání do SQL.

**Implementuje se:**

- end-to-end kontrola scénáře z kapitoly 32 zadání,
- osiřelé návštěvy v PWA UI,
- ruční záloha/obnova SQLite v PC UI,
- dotažení README (start, export, import, testy),
- docs/JSON_FORMATS.md a docs/IMPORTS.md v konečné podobě.

**Neimplementuje se:** automatický Dropbox, REST, účty, fotky, výlety, gamifikace, offline mapy.

**Testy:** ruční akceptační checklist + regresse testů fází 3, 6, 8.

**Hotovo když:** Akceptační scénář MVP (32 kroků v zadání) projde na Windows PC + mobilním Chrome/Safari.

---

## 13. Mapování akceptačního scénáře na fáze

| Krok zadání | Fáze |
|---|---|
| 1–2 spuštění PC, SQLite | 1 |
| 3 import katalogu | 3–4 |
| 4–6 duplicity, public_id, review | 3–4 |
| 7 ruční oprava přežije import | 3 |
| 8 export catalog.json | 6 |
| 9–11 PWA + Bouzov | 7 |
| 12–14 návštěvy + diary export | 8 |
| 15–18 import deníku na PC, idempotence | 8 |
| 19–22 update katalogu, návštěvy beze změny | 8–9 |

---

## 14. Rizika

| Riziko | Dopad | Opatření |
|---|---|---|
| SPARQL timeout / nestabilní endpoint | První import selže | Dotaz po typech, fixture cache odpovědi, User-Agent, retry. |
| Kvalita Wikidata | Duplicity, chybějící GPS, špatný okres | Matching C → review, quality_status, RÚIAN později. |
| Příliš volné automatické B | Chybné sloučení, ztráta identity | Přísné prahy, raději review. |
| Živá SQLite v Dropbox/OneDrive sync | Korupce DB | `data/` mimo sync; přenos jen kopií při vypnuté aplikaci. |
| iOS maže IndexedDB | Ztráta deníku | persist(), přidat na plochu, připomínka exportu. |
| Dva deníky upravené naráz | Tichá ztráta starší úpravy | last-write-wins + záloha před importem. |
| Licence NPÚ CC BY-NC-ND na webech objektů | Právní problém textů | Do DB jen URL a fakta, ne články. |
| ÚSKP ≠ katalogové číslo | Falešné neshody | Dva `source_type`, ověřit sloupce CSV ve fázi 5. |
| PWA bez HTTPS na telefonu | Nejde „přidat na plochu“ | Ve fázi 7/9 statický hosting app shellu. |
| Rozsah 2 000–3 500+ míst | UI seznam | Stránkování na PC, virtualizace na PWA až když bude potřeba. |

---

## 15. Navrhovaná vylepšení oproti doslovnému textu zadání

Nemění principy. Potvrzené a platné:

1. `deleted_at` + `updated_at` v `diary.json` u návštěv i place_states — **ano**.
2. Typ `CASTLE_CHATEAU` neexistuje, použije se M:N.
3. SQLite je jeden přenositelný soubor; živá DB se nesynchronizuje Dropboxem.
4. Integer PK se do JSON nikdy nedostane; JSON `id` = `public_id`.
5. Ignorace v review je trvalá do ručního zrušení.
6. Místa bez GPS se importují.
7. `catalog_version` se zvedá jen při změně obsahu.
8. PWA je HTML/JS na iPhonu. App shell se nahraje na [Netlify Drop](https://app.netlify.com/drop) stejně jako IphoneApp; katalog a deník se na Netlify nedávají.
9. PC UI je HTMX, ne druhý React. Na cílovém admin PC poběží zabalená aplikace, ne vývojářský stack.
10. Sloučení dvou existujících Place archivuje poraženého a převádí návštěvy; vítězné `public_id` zůstává.
11. Vždy je jen jeden zdroj pravdy: jeden admin PC, jedna SQLite. Vývoj je tady; později se přenositelná složka předá správci. Souběžná administrace na dvou PC není.

---

## 16. Fáze 1

Kapitola 17 je uzavřená. Implementuje se Fáze 1.

---

## 17. Uzavřená rozhodnutí

### 17.1 Odkud iPhone jednou načte PWA — Netlify Drop

Stejný postup jako IphoneApp: připravit statickou složku, přetáhnout na [app.netlify.com/drop](https://app.netlify.com/drop), otevřít URL v Safari, Přidat na plochu.

Rozdíl proti jazykové appce: na Netlify jde **jen prázdný app shell** (HTML/JS/manifest/service worker). `catalog.json` a `diary.json` se nahrávají v PWA ze souboru (Dropbox / USB), ne z hostingu.

Skript `pripravit-deploy-netlify` vznikne až ve fázi 7.

### 17.2 Administrace na jiném Windows PC — jeden zdroj pravdy

Teď se vyvíjí tady. Až bude hotovo, předá se přenositelná složka (aplikace + `data/pamatky.sqlite3`) správci na **jednom** PC. Ten PC je od té chvíle jediný zdroj pravdy katalogu.

Do budoucna lze složku zkopírovat na jiný stroj, ale nikdy se nesmí administrovat ze dvou PC naráz. PWA na telefonu ani na jiném PC katalog needituje.
