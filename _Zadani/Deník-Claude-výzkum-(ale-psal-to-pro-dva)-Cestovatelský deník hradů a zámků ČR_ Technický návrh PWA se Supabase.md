# Cestovatelský deník hradů a zámků ČR — kompletní technický návrh

## TL;DR

- **Zlatý standard importu = Wikidata (SPARQL, licence CC0) jako páteř seznamu + otevřená data NPÚ z pamatkovykatalog.cz (CSV, CC BY-SA 4.0) pro rejstříková čísla ÚSKP a přesné administrativní zařazení + OpenStreetMap/Overpass (ODbL) pro otevírací doby a web.** Komerční weby (hrady.cz, kudyznudy.cz) nescrapuj — buď mají zákaz, nebo API jen pro smluvní partnery; pro osobní účel je nepotřebuješ.
- **Doporučená architektura: Supabase (Postgres + Storage + Auth) + PWA (React/Vite + MapLibre + service worker).** Dá se to celé vyvíjet z Cursoru; ve webové konzoli Supabase uděláš jen založení projektu a zkopírování API klíčů (jednorázově ~15 minut). Švagrová se nikdy konzole ani Cursoru nedotkne — dostane jen URL hotové PWA, kterou si „nainstaluje” na plochu telefonu.
- **Čistě lokální PWA (Dexie/IndexedDB + export JSON) je jednodušší a zdarma navždy, ale neumí pohodlnou synchronizaci mezi dvěma lidmi.** Protože chceš, aby zapisovali švagrová i její manžel, Supabase se vyplatí. Hotové appky (Notion, Airtable, Wanderlog, Polarsteps) zavrhuji — neumí dobře ten kurátorovaný seznam ~2 000+ českých památek s filtrem „zpřístupněno”.

## Key Findings

### A) Zdroje dat — co je použitelné

1. **Wikidata** (`query.wikidata.org/sparql`) — nejlepší strojově čitelný zdroj a páteř celého projektu. Jedním dotazem vrátí název, souřadnice (P625), obrázek z Commons (P18), okres/kraj (P131), typ objektu (P31), odkazy na Wikipedii, oficiální web (P856) a rejstříkové číslo ÚSKP (P4075). Licence **CC0** (public domain) — smíš cokoli, bez atribuce. To je klíčová výhoda: seznam míst si legálně stáhneš a uložíš celý.
1. **Otevřená data NPÚ** (`pamatkovykatalog.cz/opendata/`) — dva CSV soubory ke stažení: `npu_opendata_KP.csv` (kulturní památky) a `npu_opendata_NKP.csv` (národní kulturní památky). Ověřené sloupce: `katalogové_číslo, název, kategorie, kraj, okres, obec, část_obce, historická_lokalita, katastrální_území, adresa, typ_památkové_ochrany, rejstříkové_číslo_ÚSKP, PrStavId, AktStav_Id, anotace`.  Data se aktualizují 1× měsíčně k poslednímu dni měsíce. Licence **CC BY-SA 4.0** (nutná atribuce „Geoportál památkové péče, Národní památkový ústav”). Tatáž data jsou i jako WMS/WFS/ATOM služby na `geoportal.npu.cz` a v Národním katalogu otevřených dat (data.gov.cz). Pozor: movité památky veřejné nejsou; nemovité (což jsou hrady a zámky) veřejné jsou.
1. **Seznam zpřístupněných objektů ve správě NPÚ** — dle Wikipedie („Seznam památkových objektů ve správě NPÚ”) spravuje NPÚ **celkem 106 státních památkových objektů**, konkrétně **29 hradů, 59 zámků, 5 hradozámků, 4 kláštery, 3 kostely, 2 usedlosti, 2 zdravotnická zařízení, 3 komplexy zahrad, vilu a důlní technickou památku**;  z toho 9 památek zapsaných na seznamu UNESCO (Lednicko-valtický areál se počítá jako 3 samostatné).  Toto je tvůj přirozený jádrový seznam „zpřístupněno = ano, ve správě státu”. Návštěvnost dle tiskové zprávy NPÚ: **v roce 2025 celkem 4 259 979 návštěvníků, což je o 6 % více než v roce 2024**  (4 005 970).
1. **OpenStreetMap / Overpass API** — tagy `historic=castle` doplněné o `castle_type=defensive|stately|palace|manor`; pro české **tvrze** se v OSM po diskusi ustálilo `castle_type=fortified_manor` (případně `motte`).  Objekty nesou `name`, `website`, `opening_hours`, `wikidata`, `wikipedia` a adresní tagy. Stahuje se přes Overpass API / overpass-turbo (export GeoJSON). Licence **ODbL** (atribuce + share-alike). Overpass zvládne miliony prvků za minuty, takže celá ČR je bez problému. 
1. **Wikimedia Commons** — obrázky získáš přímo z názvu souboru přes `https://commons.wikimedia.org/wiki/Special:FilePath/{soubor}?width=800`  (P18 z Wikidata dává rovnou název souboru). Licence se liší kus od kusu (typicky CC BY-SA, někdy public domain); pro osobní deník to není problém, při veřejné publikaci nutno hlídat atribuci.
1. **Kudy z nudy (CzechTourism)** — Content API existuje (vrací JSON včetně GPS), ale je **přístupné jen smluvním partnerům**, vyžaduje schválenou registraci a API klíč, s limitem **max. 1 volání za hodinu**.  Pro tento projekt nepoužitelné a zbytečné.
1. **hrady.cz, hrady-zriceniny.cz, turistika.cz, zamky-hrady.cz** — bohaté katalogy, ale komerční databáze chráněné zvláštním právem pořizovatele. Systematicky nescrapuj.
1. **RÚIAN / ČÚZK** — pro doplnění adres a administrativního členění k souřadnicím. V praxi to ale už máš z Wikidata (P131) a NPÚ CSV, takže ČÚZK řešit nemusíš — byla by to zbytečná komplikace.

### B) Právní stránka (osobní, nekomerční užití)

- **Wikidata CC0** = bez jakéhokoli omezení, ani atribuce. **OSM ODbL** a **NPÚ + Wikipedia CC BY-SA 4.0** = smíš použít; pro veřejnou publikaci nutná atribuce a zachování licence, pro soukromý deník v praxi bez rizika.
- **Scraping komerčních webů:** Podle §88 a násl. autorského zákona (č. 121/2000 Sb.) náleží pořizovateli databáze zvláštní právo na vytěžování/zužitkování celého obsahu nebo jeho kvalitativně/kvantitativně podstatné části  (trvá 15 let od zpřístupnění). Oprávněný uživatel smí vytěžovat jen **nepodstatné části** — a to nikoli systematicky či opakovaně.  Stažení celého soupisu míst z jednoho komerčního katalogu = vytěžení podstatné části = zásah do práva pořizovatele. Proto ber seznam z otevřených/CC0 zdrojů. Ruční okopírování pár popisů pro sebe je fakticky neškodné, ale systematický scrape ano.
- **Fotky:** stahuj z Commons (volné licence). Vlastní fotky z telefonu jsou tvoje. Fotky z komerčních webů lokálně neukládej.
- **GDPR zde relevantní není** (nejde o osobní údaje třetích osob).

### C) Technické varianty — srovnání

|Kritérium      |V1 Lokální PWA (Dexie)|V2 **Supabase** ✅            |V3 Firebase                            |V4 SQLite + sync|V5 Hotové appky  |
|---------------|----------------------|-----------------------------|---------------------------------------|----------------|-----------------|
|Cena osobní    |zdarma navždy         |zdarma (free tier)           |zdarma jen bez fotek*                  |zdarma          |zdarma / freemium|
|Offline        |výborné               |dobré (cache + fronta zápisů)|výborné (nativní persistence Firestore)|dobré           |různé            |
|Fotky          |v IndexedDB / soubor  |Storage 1 GB (free)          |**Storage vyžaduje kartu (Blaze)**     |lokálně         |ano              |
|Sync 2 lidí    |ruční JSON soubor     |**nativní realtime**         |nativní realtime                       |složité         |ano              |
|Vendor lock-in |žádný                 |nízký (je to čistý Postgres) |vysoký (Firestore)                     |žádný           |vysoký           |
|Vývoj z Cursoru|100 %                 |100 %                        |100 %                                  |100 %           |n/a              |
|Složitost      |nízká                 |střední                      |střední                                |vysoká          |nulová           |

**Free-tier limity (data k červenci 2026):**

- **Supabase Free:** 500 MB Postgres, 1 GB Storage, 5 GB egress/měsíc, 50 000 MAU, 500 000 edge-function invokací, až 2 aktivní projekty, **bez záloh, a projekt se po 7 dnech nečinnosti automaticky pozastaví**  (nutno ho ručně probudit v dashboardu, cca 30 s). Pro dva uživatele a ~2 000 míst je 500 MB / 1 GB bohatě dost. Placený Pro plán (25 USD/měs) pauzování ruší a přidává zálohy. 
- **Firebase Spark (free):** Firestore 1 GB, ~50 000 čtení / 20 000 zápisů / 20 000 mazání denně; Hosting 10 GB přenos/měsíc; Auth 50 000 MAU.  **Zásadní háček: Cloud Storage for Firebase vyžaduje od 30. října 2024 pro nové výchozí buckety plán Blaze  (tj. přiloženou platební kartu)** — bez karty tedy fotky nikam neuložíš, i když do 5 GB zůstávají fakticky zdarma.  To je pro projekt s fotkami hlavní důvod, proč Firebase nedoporučuji.

**Odpověď na tvou klíčovou obavu (vývoj z Cursoru):** Ano — Supabase i Firebase se dají **plnohodnotně vyvíjet z Cursoru / Claude Code / Cowork**. Rozdělení práce je jasné:

- **V editoru (Cursor):** veškerý kód — SQL migrace, PWA frontend, případné edge funkce. Databázi a nasazení řídíš přes `supabase` CLI přímo z terminálu v Cursoru (`supabase init`, `supabase db push`, `supabase gen types`).
- **Ve webové konzoli daného cloudu:** jen tři jednorázové věci — (1) založení projektu, (2) zkopírování URL a `anon` klíče do `.env`, (3) občasné nahlédnutí do dat / spuštění SQL v editoru. Dohromady ~15 minut za celý život projektu.
- **Netechnická švagrová se konzole ani Cursoru nikdy nedotkne.** Dostane odkaz na hotovou PWA. To, že backend běží v cloudu, je pro ni neviditelné — chová se to jako obyčejná webová stránka/appka.

Závěr: **Supabase je pro tebe správná volba** — je to Postgres (znáš SQL), vývoj běží z Cursoru, sdílení mezi dvěma lidmi je nativní, a fotky uložíš zdarma bez karty (na rozdíl od Firebase).

### E) Nápady navíc (o které jsi explicitně žádal)

- **Mapa s barevným rozlišením** navštíveno (zelená) / nenavštíveno (šedá) / wishlist (žlutá).
- **Statistiky pokrytí:** „navštíveno 37 % zámků v Jihomoravském kraji”, progress bary po krajích a okresech.
- **„Co je do 50 km ode mě a ještě jsem tam nebyl”** — filtr podle vzdálenosti od aktuální GPS polohy.
- **Plánovač výletu** — vyber víc míst, zobraz je na mapě, seřaď podle trasy.
- **Sdílený deník pro dva** — každý zápis má autora (švagrová / manžel), oba vidí vše.
- **Export do PDF** fotoknihy/deníku (přes jsPDF nebo tisk prohlížeče).
- **Gamifikace** — odznaky za kompletně navštívený kraj, za 10/50/100 památek, za všechny UNESCO objekty.
- **Automatické přiřazení fotek z telefonu podle EXIF GPS + data** — nahraješ fotky, appka podle souřadnic a času navrhne, ke kterému místu a návštěvě patří.
- **Offline mapa** (MBTiles/PMTiles) pro použití bez signálu.
- **Turistické známky / razítka** — evidence sbírky u navštívených míst.
- **Integrace otevíracích dob** z OSM `opening_hours`.

## Details

### Doporučená kombinace zdrojů — „takhle bych to naimportoval”

1. **Základní seznam z Wikidata** (CC0 → souřadnice + obrázek + kraj/okres + typ + Wikipedia + web + ÚSKP číslo). Jeden SPARQL dotaz → JSON → import.
1. **Obohacení o NPÚ CSV** — join přes rejstříkové číslo ÚSKP (`P4075` ve Wikidata ↔ `rejstříkové_číslo_ÚSKP` v CSV). Doplní přesnou adresu, obec, anotaci a příznak, že jde o chráněnou památku.
1. **Příznak „zpřístupněno”** — nastav `TRUE` pro 106 objektů ve správě NPÚ (mají oficiální web na doméně `*.npu.cz`) a pro objekty, které mají v OSM `tourism=attraction` nebo vyplněné `opening_hours`.
1. **Otevírací doby a web z OSM Overpass** — volitelný druhý průchod, spojovacím klíčem je `wikidata` tag.
1. **Fotky památek** nech jako URL na Commons (nestahuj lokálně — ušetříš místo i řešení licencí); jen **vlastní fotky** ukládej do Supabase Storage.

### Funkční SPARQL dotaz (spustitelný na query.wikidata.org)

```sparql
SELECT DISTINCT ?item ?itemLabel ?typeLabel ?coord ?image ?okresLabel ?krajLabel ?web ?uskp ?article WHERE {
  VALUES ?tridy { wd:Q23413 wd:Q751876 wd:Q109607 }   # hrad, zámek, zřícenina
  ?item wdt:P31/wdt:P279* ?tridy .
  ?item wdt:P17 wd:Q213 .                               # stát = Česko
  ?item wdt:P31 ?type .
  OPTIONAL { ?item wdt:P625 ?coord . }
  OPTIONAL { ?item wdt:P18 ?image . }
  OPTIONAL { ?item wdt:P131 ?okres . ?okres wdt:P31 wd:Q3389049 . }  # okres
  OPTIONAL { ?item wdt:P131* ?kraj . ?kraj wdt:P31 wd:Q1615742 . }   # kraj
  OPTIONAL { ?item wdt:P856 ?web . }
  OPTIONAL { ?item wdt:P4075 ?uskp . }                 # rejstř. číslo ÚSKP
  OPTIONAL { ?article schema:about ?item ; schema:isPartOf <https://cs.wikipedia.org/> . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "cs,en" . }
}
```

Endpoint vrací JSON přes `GET https://query.wikidata.org/sparql?format=json&query=...` (hard limit 60 s na dotaz).   Pro tvrze a rozhledny přidej do `VALUES` další třídy (tvrz ≈ `wd:Q2288643`, rozhledna ≈ `wd:Q1440476`, klášter ≈ `wd:Q44613`) — QID si nejdřív ověř kliknutím v query.wikidata.org.

### Ukázkový importní skript (Python)

```python
import requests, json, csv

WDQS = "https://query.wikidata.org/sparql"
QUERY = open("dotaz.sparql", encoding="utf-8").read()

def fetch_wikidata():
    r = requests.get(WDQS, params={"format": "json", "query": QUERY},
                     headers={"User-Agent": "HradyDenik/1.0 (osobni projekt; kontakt@example.cz)"})
    r.raise_for_status()
    rows = r.json()["results"]["bindings"]
    out = []
    for b in rows:
        def g(k): return b[k]["value"] if k in b else None
        coord = g("coord")  # "Point(lon lat)"
        lat = lon = None
        if coord and coord.startswith("Point("):
            lon, lat = map(float, coord[6:-1].split())
        image = g("image")
        out.append({
            "wikidata_id": g("item").split("/")[-1],
            "nazev": g("itemLabel"),
            "typ": g("typeLabel"),
            "lat": lat, "lon": lon,
            "foto_url": image,  # už je to přímá Commons URL (Special:FilePath)
            "okres": g("okresLabel"),
            "kraj": g("krajLabel"),
            "web": g("web"),
            "uskp": g("uskp"),
            "wikipedia": g("article"),
        })
    return out

def merge_npu(mista):
    # NPÚ CSV: rejstříkové_číslo_ÚSKP je spojovací klíč
    npu = {}
    for fname in ("npu_opendata_KP.csv", "npu_opendata_NKP.csv"):
        with open(fname, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                npu[row["rejstříkové_číslo_ÚSKP"]] = row
    for m in mista:
        n = npu.get(m["uskp"])
        if n:
            m["adresa"]  = n["adresa"]
            m["obec"]    = n["obec"]
            m["anotace"] = n["anotace"]
            m["chranena_pamatka"] = True
    return mista

data = merge_npu(fetch_wikidata())
json.dump(data, open("mista.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"Uloženo {len(data)} míst.")
```

### SQL DDL (Postgres / Supabase)

```sql
create table mista (
  id            bigint generated always as identity primary key,
  nazev         text not null,
  typ           text,                       -- hrad|zámek|zřícenina|tvrz|klášter|rozhledna
  zpristupneno  boolean default false,      -- filtr "návštěvitelné"
  lat           double precision,
  lon           double precision,
  adresa        text,
  obec          text,
  okres         text,
  kraj          text,
  popis         text,
  zdroj_popisu  text,                        -- 'wikipedia' | 'npu' | 'vlastni'
  web           text,
  foto_url      text,                        -- Commons URL
  wikidata_id   text,
  osm_id        text,
  uskp          text,                        -- rejstříkové číslo ÚSKP
  provozovatel  text,
  vstupne       text,
  sezonnost     text,
  created_at    timestamptz default now()
);

create table navstevy (
  id           bigint generated always as identity primary key,
  misto_id     bigint references mista(id),
  uzivatel     text,                         -- 'svagrova' | 'manzel'
  datum        date,
  s_kym        text,
  hodnoceni    int check (hodnoceni between 1 and 5),
  zazitek      text,
  pocasi       text,
  cena         numeric,
  doba_min     int,
  created_at   timestamptz default now()
);

create table navstevy_foto (
  id           bigint generated always as identity primary key,
  navsteva_id  bigint references navstevy(id),
  storage_path text,                         -- cesta v Supabase Storage
  exif_lat     double precision,
  exif_lon     double precision,
  poridil      timestamptz                   -- EXIF DateTimeOriginal
);

create table stitky (id bigint generated always as identity primary key, nazev text unique);
create table mista_stitky (
  misto_id  bigint references mista(id),
  stitek_id bigint references stitky(id),
  primary key (misto_id, stitek_id)
);
create table wishlist (
  misto_id bigint references mista(id) primary key,
  priorita int,
  poznamka text
);
```

### JSON schéma pro lokální variantu (Dexie)

```js
db.version(1).stores({
  mista:    '++id, nazev, typ, kraj, okres, zpristupneno, wikidata_id',
  navstevy: '++id, misto_id, uzivatel, datum',
  fotky:    '++id, navsteva_id',
  stitky:   '++id, &nazev',
  wishlist: 'misto_id'
});
// export/import celé DB: balíček dexie-export-import (db.export() -> Blob -> JSON soubor)
```

### Doporučený stack

- **Frontend:** React + Vite + TypeScript, plugin `vite-plugin-pwa` (service worker, manifest, offline-first).
- **Mapa:** **MapLibre GL JS** (open-source fork Mapbox GL, MIT licence, vektorové dlaždice,  styl v JSON, offline přes MBTiles/PMTiles,  datově řízené barvení markerů). Alternativa pro maximální jednoduchost a nejlepší mobilní ovládání „out of the box” je **Leaflet** (raster, ~42 KB,  cache dlaždic přes service worker,  širší kompatibilita starších prohlížečů).  **Pro tento projekt jdi do MapLibre** kvůli offline mapě a snadnému barevnému rozlišení navštíveno/nenavštíveno; Leaflet vezmi, jen pokud bys chtěl co nejméně kódu a nevadí ti stažené rastrové dlaždice.
- **DB/backend:** Supabase (Postgres + Storage + Auth + Realtime).
- **Offline vrstva:** IndexedDB přes **Dexie.js** jako lokální cache/„source of truth”; fronta zápisů (Background Sync) se odešle do Supabase po připojení. Vzor: service worker (cache-first pro assety, network-first pro data) + Dexie + Background Sync. 
- **EXIF:** knihovna **`exifr`** (rychlá, promises, čte GPS z JPEG/HEIC, převod DMS→DD)  pro automatické přiřazení fotky k místu a datu návštěvy.
- **Export deníku:** `jsPDF` nebo tisk přes prohlížeč do PDF.

### Postup realizace krok za krokem

- **Den 1 — data:** V Cursoru napiš Python skript výše, spusť SPARQL dotaz, stáhni obě NPÚ CSV, vygeneruj `mista.json`. Ověř počty a kvalitu (kolik záznamů má souřadnice, kolik obrázek, kolik se spojilo s NPÚ přes ÚSKP).
- **Den 2 — kostra PWA:** `npm create vite`, přidej `vite-plugin-pwa`, MapLibre, `@supabase/supabase-js`. Založ Supabase projekt (konzole), zkopíruj URL + anon klíč. Naimportuj `mista.json` do tabulky `mista`.
- **Den 3 — funkce:** seznam + detail + filtr (typ, kraj, `zpristupneno`), mapa s markery, formulář návštěvy, upload fotky do Storage, EXIF přiřazení přes `exifr`.
- **Den 4 — offline + sync:** service worker cache, Dexie fronta zápisů, Supabase Realtime pro sdílení mezi dvěma lidmi, „instalace” PWA na plochu telefonu.
- **Den 5 — nápady navíc:** statistiky krajů/okresů, „do 50 km ode mě”, odznaky, export PDF.

**Ukázkové prompty do Cursoru:**

- „Vytvoř Vite + React + TypeScript PWA s vite-plugin-pwa, nastav manifest a service worker pro offline-first (cache-first assety, network-first data), přidej Supabase klienta a MapLibre mapu s markery z tabulky `mista`, barva markeru podle toho, zda existuje záznam v `navstevy`.”
- „Naimportuj `mista.json` do Supabase tabulky `mista` přes supabase-js, ošetři duplicity podle `wikidata_id` (upsert).”
- „Přidej formulář návštěvy s uploadem fotky do Supabase Storage a čtením EXIF GPS/data knihovnou exifr; podle souřadnic navrhni nejbližší místo ze seznamu.”
- „Přidej Dexie cache a frontu offline zápisů, která se po připojení synchronizuje do Supabase (Background Sync).”

## Recommendations

1. **Postav to na Supabase + PWA (React/Vite + MapLibre).** Nejlepší poměr mezi jednoduchostí, offline schopností a sdílením mezi dvěma lidmi. Vývoj běží celý z Cursoru; koncová uživatelka jen otevře URL.
1. **Data importuj z Wikidata (páteř, CC0) + NPÚ CSV (rejstřík ÚSKP a přesná adresa/obec/anotace) + volitelně OSM (otevírací doby a web).** Nescrapuj komerční weby ani neřeš Kudy z nudy API.
1. **Rozsah dej maximální** (hrady, zámky, zříceniny, tvrze, kláštery, rozhledny) s booleovským příznakem `zpristupneno` jako filtrem — přesně jak sis přál. Jádro „zpřístupněno = TRUE” tvoří 106 objektů ve správě NPÚ.
1. **Fotky památek nech jako Commons URL** (odkaz, ne kopie), jen vlastní fotky ukládej do Supabase Storage — pohodlně se vejdeš do free tieru (1 GB).
1. **Ošetři pozastavení Supabase projektu po 7 dnech nečinnosti** — buď appku občas otevři, nebo nastav lehký cron ping / GitHub Actions workflow, který jednou denně sáhne do DB.
1. **Kdyby ti vadila jakákoli závislost na cloudu**, jdi do čistě lokální varianty (Dexie + export/import JSON přes `dexie-export-import`) a synchronizaci mezi dvěma lidmi řeš ručním sdílením JSON souboru (např. přes cloudové úložiště). Přijdeš o pohodlí realtime syncu, ale je to zdarma navždy a bez pozastavování.

**Prahové hodnoty, které by změnily doporučení:**

- Přibude-li >2 uživatelů nebo velké množství vlastních fotek (>1 GB Storage / >500 MB DB), zvaž Supabase Pro (25 USD/měs) — přidá zálohy a zruší pauzování.
- Jde-li nakonec jen o jednoho uživatele bez sdílení, přejdi na čistě lokální Dexie (V1) — ušetříš si veškerou správu backendu.
- Trvá-li ti nativní mobilní offline persistence víc než cokoli jiného, byla by silná i Firebase (V3) — ale jen pokud jsi ochoten přiložit platební kartu kvůli Storage; jinak Supabase vyhrává.

## Caveats

- **Přesné počty záznamů na Wikidata jsem nedokázal ověřit živě** — endpoint byl během výzkumu přes dostupné nástroje opakovaně nedostupný (cache-only / bot-detekce), a to i přes pokusy o zrcadla (QLever, OpenLink Virtuoso). Odhad „hrady + zámky + zříceniny řádově 2 000–3 500” má jistotu **~55 %**; **spusť dotaz sám** v `query.wikidata.org` pro přesné číslo (dotaz výše je syntakticky standardní a měl by projít). Celkový počet českých „castles” se navíc podle metodiky počítání pohybuje od nižších stovek po ~1000, takže žádné jediné „správné” číslo neexistuje. 
- **Free-tier limity Supabase i Firebase se mohou měnit** — uvedené hodnoty jsou k červenci 2026; před nasazením ověř na `supabase.com/pricing` a `firebase.google.com/pricing`.
- **Kvalita Wikidata je nerovnoměrná** — ne každý objekt má vyplněné souřadnice, obrázek nebo okres; proto ten join s NPÚ CSV a případně OSM. Počítej s tím, že část záznamů budeš muset dočistit ručně.
- **Firebase Storage vyžaduje platební kartu (Blaze)** — pokud kartu přikládat nechceš, Firebase pro projekt s fotkami odpadá.
- **Licence CC BY-SA (NPÚ, Wikipedia, OSM)** vyžadují atribuci a share-alike při veřejné publikaci. Pro soukromý deník to neřešíš, ale kdybys appku někdy zveřejnil, uveď zdroje a licence.