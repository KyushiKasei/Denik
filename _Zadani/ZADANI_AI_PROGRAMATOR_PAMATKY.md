# Zadání projektu: Osobní katalog hradů, zámků a dalších historických míst

## 1. Cíl projektu

Vytvoř lokální aplikaci pro osobní evidenci hradů, zámků, zřícenin, tvrzí a případně dalších historických míst v České republice.

Aplikace má dvě oddělené části:

1. **PC aplikace – hlavní master databáze**
   - jediná část systému, kde se upravují údaje o památkách,
   - importuje a doplňuje data z externích zdrojů,
   - řeší deduplikaci,
   - umožňuje ruční opravy,
   - exportuje katalog pro mobilní aplikaci,
   - importuje osobní deník z mobilní aplikace.

2. **Mobilní PWA – katalog a cestovatelský deník**
   - načte katalog z JSON souboru,
   - katalog památek je v mobilu pouze pro čtení,
   - funguje co nejvíce offline,
   - umožňuje zaznamenávat návštěvy, datum, účastníky, hodnocení a poznámku,
   - osobní data exportuje do samostatného JSON souboru.

**Nechci server, backend v internetu, účty, přihlašování ani REST API mezi PC a mobilem.**

Přenos dat bude záměrně jednoduchý přes soubory, např. Dropbox, iCloud Drive, Google Drive, USB nebo jinou běžnou cestu.

---

# 2. Základní princip architektury

## 2.1 Zdroj pravdy

**PC databáze je jediný zdroj pravdy pro katalog památek.**

Mobilní PWA nikdy nesmí měnit master data památky.

Na mobilu lze upravovat pouze osobní data:
- návštěvy,
- poznámky,
- hodnocení,
- účastníky,
- případně „chci navštívit“ a „oblíbené“.

---

## 2.2 Datový tok

```text
EXTERNÍ ZDROJE
    │
    ▼
PC IMPORTERY
    │
    ▼
NORMALIZACE + DEDUPLIKACE + KONTROLA
    │
    ▼
SQLite MASTER DB
    │
    ├──────────────► catalog.json ───────────────► PWA
    │                                                 │
    │                                                 ▼
    │                                           IndexedDB
    │                                                 │
    │                                                 ▼
    ◄────────────── diary.json ◄──────────── osobní deník
```

Dropbox ani jiná cloudová služba není součást aplikační logiky.

Je to pouze transportní místo pro soubory.

---

# 3. Doporučený technologický základ

Preferované řešení:

## PC

- Python 3.12+
- SQLite
- SQLAlchemy
- Alembic nebo jiný rozumný mechanismus migrací databáze
- lokální webová aplikace spuštěná na PC

Technologii uživatelského rozhraní můžeš zvolit podle toho, co bude pro projekt nejjednodušší na údržbu.

Preferuji:
- jednoduchost,
- čitelnost kódu,
- minimum závislostí,
- snadné spuštění na Windows,
- snadnou budoucí údržbu pomocí AI.

Nepoužívej složitou infrastrukturu, Docker ani mikroservisy, pokud pro ně není skutečný důvod.

## Mobilní PWA

Preferováno:

- TypeScript
- Vite
- React nebo jiný lehký moderní frontend
- IndexedDB
- případně knihovna Dexie.js pro jednodušší práci s IndexedDB
- Service Worker / PWA manifest

PWA musí být připravena tak, aby ji bylo možné otevřít z mobilu a přidat na plochu.

---

# 4. Zásadní pravidlo identity památek

Toto je jedna z nejdůležitějších částí projektu.

## 4.1 Interní ID

Každá památka dostane při prvním založení vlastní interní stabilní identifikátor.

Doporučený model:

```text
places.id
```

- interní databázový primární klíč, například integer,

a současně:

```text
places.public_id
```

- neměnný UUID,
- používá se v JSON exportech,
- používá se ve všech návštěvách,
- nesmí se nikdy znovu generovat,
- nesmí se měnit při aktualizaci nebo opakovaném importu.

Příklad:

```text
0198f23a-5e5e-7b31-a8be-8c99507a2138
```

Použij UUIDv7, pokud jej zvolený stack rozumně podporuje. Jinak použij UUIDv4.

---

## 4.2 Externí ID nejsou naše primární ID

Památka může mít současně:

```text
Wikidata: Q12345
Památkový katalog: 1000123456
ÚSKP: ...
OSM: relation/12345
Wikipedia: ...
NPÚ slug/url: ...
```

Tato ID ukládej jako vazby na externí zdroje.

Nikdy nepoužívej externí ID jako hlavní interní identifikátor aplikace.

---

# 5. Opakovaný import a doplňování památek

Musí být bezpečně možné kdykoliv znovu spustit import.

Například:

```text
první import:
350 míst

za rok:
spustím import znovu

výsledek:
12 nových
48 změněných
287 beze změny
3 nejasné
0 ztracených interních ID
```

## 5.1 Povinné pravidlo

**Import nesmí vytvořit novou památku, pokud už je možné bezpečně zjistit, že dané místo v databázi existuje.**

---

## 5.2 Pořadí párování

Při importu se pokus objekt spojit s existující památkou v tomto pořadí:

### Úroveň A – jistá shoda

Stejné:
- Wikidata ID,
- Památkový katalog ID,
- ÚSKP ID,
- jiný jednoznačný externí identifikátor.

Výsledek:

```text
MATCHED_EXACT
```

Aktualizuj existující `Place`.

Nikdy nevytvářej nový `public_id`.

---

### Úroveň B – velmi pravděpodobná shoda

Pokud chybí externí identifikátor, použij kombinaci:

- normalizovaný název,
- obec,
- GPS vzdálenost,
- typ objektu,
- případně okres.

Například:

```text
"Hrad Karlštejn"
"Státní hrad Karlštejn"
"Karlštejn"
```

mohou být jedna památka.

Pokud je shoda bezpečná:

```text
MATCHED_PROBABLE
```

Záznam aktualizuj a do historie importu ulož, proč byl spárován.

---

### Úroveň C – nejasná shoda

Pokud existuje podezření na duplicitu, ale není dostatek jistoty:

**NESMÍ se automaticky vytvořit nový Place.**

Vytvoř položku do:

```text
IMPORT_REVIEW
```

PC aplikace zobrazí:

```text
Importovaný objekt:
Zámek Nová Ves

Možná existující památka:
Nová Ves – zámecký areál

GPS rozdíl: 37 m
Obec: stejná

[Sloučit]
[Vytvořit jako nové]
[Ignorovat]
```

Teprve člověk rozhodne.

---

## 5.3 Ruční spojení

Po ručním spojení:

- nový zdroj se připojí k existujícímu `Place`,
- interní `public_id` zůstane původní,
- budoucí importy už musí objekt poznat přes uložené externí ID.

---

# 6. Ochrana ručních změn

Uživatel může na PC importované údaje ručně opravit.

Například:

```text
Wikidata:
name = "Zámek Nová Ves"

ruční úprava:
name = "Nová Ves"
```

Nový import nesmí ruční opravu automaticky přepsat.

Proto musí systém rozlišovat:

```text
importovanou hodnotu
vs.
master hodnotu zvolenou uživatelem
```

Implementačně může být řešeno například:

- field-level override,
- příznak `manual_override`,
- samostatná tabulka hodnot ze zdrojů,
- jiný čistý návrh.

Výsledek však musí splňovat:

> Ručně potvrzená hodnota v master databázi má vyšší prioritu než nový automatický import.

PC aplikace může nabídnout:

```text
Zdroj změnil hodnotu:

Původní zdroj:
Zámek Nová Ves

Nový zdroj:
Nová Ves – zámek

Master:
Nová Ves

[Ponechat master]
[Převzít novou hodnotu]
```

---

# 7. Zdrojová data

Externí weby nejsou databáze aplikace.

Jsou pouze zdroje.

Pro každý zdroj uchovávej:

```text
source_type
external_id
source_url
fetched_at
raw_data nebo snapshot relevantních strukturovaných dat
license
```

Důvod:

- audit importu,
- deduplikace,
- možnost pozdější aktualizace,
- možnost zjistit původ údaje.

---

# 8. Doporučené zdroje památek

Importery navrhni modulárně.

Například:

```text
/importers
    wikidata
    pamatkovy_katalog
    npu
    wikimedia_commons
    ruian
    wikipedia
    openstreetmap
```

Nemusí být všechny implementované v první fázi.

---

## 8.1 Wikidata

Použití:

- základní discovery,
- názvy,
- typy,
- souřadnice,
- odkazy,
- oficiální web,
- obrázek,
- externí identifikátory.

Preferovaný první automatický importní zdroj.

---

## 8.2 Památkový katalog / otevřená data NPÚ

Použití:

- oficiální identifikace,
- památkový status,
- katalogové ID,
- lokalita,
- obec,
- okres,
- kraj,
- anotace,
- kontrola souřadnic.

---

## 8.3 Weby NPÚ

Použití pouze pro objekty, které NPÚ spravuje.

Možné údaje:

- oficiální web,
- návštěvní informace,
- odkaz na otevírací dobu,
- odkaz na vstupné,
- rezervace,
- kontakt.

Neimportuj bezmyšlenkovitě celé autorské texty a fotografie.

---

## 8.4 RÚIAN

Použití:

- normalizace obce,
- okresu,
- kraje,
- případně adresy,
- oficiální územní kódy.

Není potřeba kvůli MVP implementovat celý RÚIAN systém.

Použij ho jako normalizační vrstvu.

---

## 8.5 Wikimedia Commons

Použití:

- hlavní ilustrační fotografie.

V master databázi eviduj:

```text
source_url
thumbnail_url
author
license
license_url
attribution
```

V první verzi nemusíš obrázek ukládat do databáze binárně.

---

## 8.6 Wikipedia

Použití:

- kontrola úplnosti katalogu,
- odkazy na historii místa.

Do MVP není nutné kopírovat dlouhé texty Wikipedie do databáze.

---

## 8.7 OpenStreetMap

Pouze doplňkový zdroj.

Použití:

- geografická kontrola,
- případně přístupnost,
- další tagy.

Nepovažuj OSM za hlavní zdroj katalogu.

---

## 8.8 Hrady.cz

Používat pouze jako:

- inspiraci,
- ruční kontrolu úplnosti.

**Neimplementuj automatický scraping textů a fotografií z Hrady.cz.**

---

# 9. Master datový model

Níže je koncept. Při návrhu databáze ho můžeš rozumně upravit, ale význam musí zůstat zachován.

---

## 9.1 Place

```text
Place
-----
id
public_id

name
short_name
alternative_names

short_description

condition
visitability

latitude
longitude

address
municipality
district
region
country

official_website
wikipedia_url
opening_hours_url
ticket_url

heritage_status

quality_status

created_at
updated_at
archived_at
```

---

## 9.2 Typy památek

Památka může mít více typů.

Nepoužívej jeden jediný enum přímo v `Place`, pokud to omezuje kombinované objekty.

Použij například:

```text
PlaceType
---------
id
code
name
```

a:

```text
PlacePlaceType
--------------
place_id
place_type_id
```

Počáteční typy:

```text
CASTLE
CHATEAU
CASTLE_CHATEAU
RUIN
FORTRESS
MANOR
PALACE
OTHER
```

České názvy zobrazuj v UI.

---

## 9.3 Stav objektu

Například:

```text
PRESERVED
RUIN
REMAINS
REBUILT
EXTINCT
UNKNOWN
```

---

## 9.4 Přístupnost

Nepoužívej pouze boolean `is_visitable`.

Použij rozšiřitelný číselník:

```text
REGULAR
SEASONAL
BY_APPOINTMENT
EVENTS_ONLY
FREE_ACCESS
EXTERIOR_ONLY
PRIVATE
TEMPORARILY_CLOSED
CLOSED
EXTINCT
UNKNOWN
```

---

## 9.5 PlaceSource

```text
PlaceSource
-----------
id
place_id

source_type
external_id
source_url

fetched_at
license
raw_data

created_at
updated_at
```

Musí existovat unikátní omezení vhodné pro:

```text
source_type + external_id
```

pokud `external_id` existuje.

Tato tabulka je klíčová pro opakované importy.

---

## 9.6 PlacePhoto

V MVP pouze ilustrační fotografie.

```text
PlacePhoto
----------
id
place_id

source
source_url
original_url
thumbnail_url

author
license
license_url
attribution

is_primary
```

Osobní fotografie návštěv zatím nedělej.

---

## 9.7 ImportRun

Každé spuštění importeru eviduj.

```text
ImportRun
---------
id
source_type
started_at
finished_at

records_received
records_created
records_updated
records_unchanged
records_review
records_failed

status
log_path nebo log
```

---

## 9.8 ImportReview

```text
ImportReview
------------
id
import_run_id

source_type
external_id

candidate_place_id

match_score
match_reason

raw_data

status
resolution
resolved_at
```

---

# 10. Osobní cestovatelský deník

Osobní data jsou oddělena od master katalogu.

Památka může být navštívena vícekrát.

Proto návštěva není sloupec na `Place`.

---

## 10.1 Visit

```text
Visit
-----
id
public_id

place_public_id

visited_at
rating
note

created_at
updated_at
```

Důležité:

`place_public_id` odkazuje na stabilní `Place.public_id`.

---

## 10.2 Účastníci

Pro MVP lze použít jednoduchý seznam jmen:

```json
"people": [
  "Jana",
  "Petr",
  "Anička"
]
```

PC databáze může později dostat samostatný číselník osob.

V první verzi není nutné projekt komplikovat M:N tabulkami, pokud to nebude potřeba.

---

## 10.3 Volitelné osobní stavy

Je vhodné připravit datový model také na:

```text
want_to_visit
favorite
personal_note
```

Tyto údaje patří do osobního deníku, nikoliv do master katalogu.

Mohou být řešeny například:

```text
PlaceJournalState
```

---

# 11. PC aplikace – funkční požadavky

## 11.1 Dashboard

Zobraz minimálně:

```text
Celkem míst
Hrady
Zámky
Zříceniny
Tvrze

Ověřené
K revizi
Chybějící GPS
Chybějící typ

Počet návštěv
Počet navštívených unikátních míst
```

---

## 11.2 Seznam památek

Musí podporovat:

- hledání,
- filtrování,
- řazení,
- stránkování nebo virtualizaci při větším seznamu.

Filtry:

- typ,
- kraj,
- okres,
- obec,
- stav,
- přístupnost,
- kvalita dat,
- zdroj,
- navštíveno / nenavštíveno.

---

## 11.3 Detail památky

Zobraz:

- název,
- typy,
- popis,
- stav,
- přístupnost,
- souřadnice,
- adresu,
- obec,
- okres,
- kraj,
- hlavní foto,
- oficiální web,
- Wikipedia,
- Památkový katalog,
- další zdroje,
- historii návštěv,
- audit externích ID.

---

## 11.4 Editace

Pouze na PC.

Musí umožnit ručně upravit master údaje.

U importovaných polí musí být možné poznat:

```text
master hodnota
hodnota zdroje
zdroj
čas posledního načtení
```

---

## 11.5 Import centrum

Samostatná stránka:

```text
Import dat
```

Funkce:

- spustit konkrétní importer,
- zobrazit průběh,
- zobrazit výsledek,
- zobrazit nové položky,
- zobrazit změněné položky,
- zobrazit nejasné duplicity,
- otevřít frontu ruční kontroly.

---

## 11.6 Bezpečnost importu

Před aplikací větší aktualizace:

- automaticky vytvoř zálohu SQLite databáze,
- změny prováděj transakčně,
- při fatální chybě rollback.

---

# 12. Export katalogu do PWA

PC aplikace vytvoří:

```text
catalog.json
```

Katalog je určen pouze ke čtení.

---

## 12.1 Struktura

Příklad:

```json
{
  "schema_version": 1,
  "catalog_version": 17,
  "generated_at": "2026-08-09T20:30:00+02:00",
  "places": [
    {
      "id": "0198f23a-5e5e-7b31-a8be-8c99507a2138",
      "name": "Bouzov",
      "types": ["CASTLE"],
      "condition": "PRESERVED",
      "visitability": "REGULAR",

      "short_description": "...",

      "location": {
        "latitude": 49.704,
        "longitude": 16.891,
        "municipality": "Bouzov",
        "district": "Olomouc",
        "region": "Olomoucký kraj"
      },

      "links": {
        "official": "...",
        "wikipedia": "...",
        "heritage_catalog": "..."
      },

      "image": {
        "thumbnail_url": "...",
        "attribution": "..."
      }
    }
  ]
}
```

---

## 12.2 Co do katalogu nedávat

Nevkládej:

- importní raw data,
- auditní logy,
- interní databázové ID,
- kompletní zdrojové snapshoty,
- velké obrázky,
- osobní návštěvy.

---

# 13. Verze katalogu

Každý export musí obsahovat:

```text
schema_version
catalog_version
generated_at
```

PWA si pamatuje aktuální verzi.

Po importu nového katalogu zobraz:

```text
Původní verze: 16
Nová verze: 17

+ 8 nových míst
~ 21 změněných míst
- 0 odstraněných míst
```

---

# 14. Odstraňování památek

Památku z master databáze běžně fyzicky nemaž.

Použij archivaci:

```text
archived_at
```

Důvod:

Osobní deník může obsahovat starou návštěvu památky.

Export může archivované místo:
- vynechat z běžného seznamu,
- ale při importu deníku musí být PC schopno jeho `public_id` stále rozpoznat.

---

# 15. Mobilní PWA

## 15.1 Základ

PWA je primárně offline katalog.

Při prvním použití:

```text
Nahraj catalog.json
```

PWA:

1. validuje strukturu,
2. zkontroluje `schema_version`,
3. načte data,
4. uloží je do IndexedDB,
5. začne je používat lokálně.

---

## 15.2 Nový katalog

Funkce:

```text
Aktualizovat katalog
```

Uživatel vybere nový `catalog.json`.

Aplikace:

- ověří formát,
- zobrazí změny,
- nahradí lokální master katalog,
- NESMÍ změnit osobní deník.

---

## 15.3 Seznam

PWA musí podporovat:

- hledání,
- filtrování,
- řazení.

Minimální filtry:

- typ,
- kraj,
- okres,
- navštíveno,
- nenavštíveno,
- případně chci navštívit.

---

## 15.4 Detail

Zobraz:

- název,
- hlavní fotografii, pokud je dostupná,
- typ,
- krátký popis,
- obec,
- okres,
- kraj,
- přístupnost,
- odkazy,
- GPS,
- moje návštěvy.

---

## 15.5 Mapa

V první verzi stačí online mapa nebo možnost otevřít souřadnice v externí mapové aplikaci.

Nevytvářej komplikovaný offline balík map celé ČR v MVP.

---

# 16. Zápis návštěvy v PWA

Na detailu:

```text
[Přidat návštěvu]
```

Formulář:

```text
Datum
Hodnocení 1–5
Kdo tam byl
Poznámka
```

Příklad:

```text
18. 7. 2026
★★★★★
Jana, Petr, Anička
Dětem se nejvíce líbila věž.
```

Jedno místo může mít neomezený počet návštěv.

---

# 17. Osobní fotografie

**Osobní fotografie nejsou součást MVP.**

Důvod:

- velikost dat,
- složitější přenos,
- složitější zálohování,
- komplikace na mobilu.

Architekturu však navrhni tak, aby bylo možné později přidat:

```text
VisitPhoto
```

bez zásadního přepisování systému.

---

# 18. diary.json

Mobil exportuje samostatný soubor:

```text
diary.json
```

Příklad:

```json
{
  "schema_version": 1,
  "exported_at": "2026-08-09T21:00:00+02:00",

  "place_states": [
    {
      "place_id": "0198f23a-5e5e-7b31-a8be-8c99507a2138",
      "want_to_visit": true,
      "favorite": false,
      "personal_note": null
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
      "updated_at": "2026-08-09T18:20:00+02:00"
    }
  ]
}
```

---

# 19. Import diary.json do PC

PC aplikace:

```text
Importovat deník
```

Musí:

1. validovat JSON,
2. ověřit `schema_version`,
3. ověřit existenci `place_id`,
4. vložit nové návštěvy,
5. aktualizovat existující návštěvy podle jejich stabilního ID,
6. nevytvářet duplicity při opakovaném importu stejného souboru.

Import musí být **idempotentní**.

Když stejný `diary.json` importuji dvakrát, nevzniknou dvě stejné návštěvy.

---

# 20. Export deníku z PC

PC musí umět také vytvořit nový kompletní:

```text
diary.json
```

Důvod:

- obnova telefonu,
- nový telefon,
- návrat upraveného deníku do PWA.

PWA proto musí mít:

```text
Importovat deník
Exportovat deník
```

---

# 21. Synchronizace přes soubory

Neimplementuj automatické Dropbox API.

Workflow:

```text
PC:
Export catalog.json

↓ uživatel uloží soubor například do Dropboxu

Mobil:
Import catalog.json

Mobil:
zapisuje návštěvy

Mobil:
Export diary.json

↓ uživatel uloží soubor například do Dropboxu

PC:
Import diary.json
```

To je požadované řešení.

Nepřidávej:
- OAuth,
- Dropbox SDK,
- cloudovou databázi,
- vlastní server,
- login,
- background sync.

---

# 22. Validace JSON

Pro oba soubory vytvoř formální JSON Schema:

```text
catalog.schema.json
diary.schema.json
```

Při importu vždy validuj.

Při neznámé `schema_version`:

```text
Tento soubor používá novější verzi datového formátu.
Aktualizuj aplikaci.
```

Nikdy se nesnaž neznámou strukturu potichu zpracovat.

---

# 23. Zálohování

PC:

- před importem větší aktualizace vytvoř zálohu databáze,
- přidej možnost ruční zálohy,
- přidej možnost obnovení ze zálohy.

PWA:

- uživatelská data jsou cennější než katalog,
- musí jít kdykoliv exportovat kompletní `diary.json`.

---

# 24. Audit a logování

Loguj minimálně:

- spuštění importerů,
- počty nových a změněných míst,
- chyby,
- deduplikační rozhodnutí,
- import/export JSON,
- ruční spojení duplicit.

Logy drž jednoduché a čitelné.

---

# 25. Co není v MVP

Do první verze NEPATŘÍ:

- účty,
- více uživatelů,
- server,
- REST API,
- Dropbox API,
- automatická cloud synchronizace,
- push notifikace,
- vlastní osobní fotografie,
- automatické generování výletů,
- offline mapy celé ČR,
- gamifikace,
- sociální funkce,
- veřejné sdílení.

Projekt musí nejdříve spolehlivě zvládnout katalog + import + deník.

---

# 26. Co musí být připravené do budoucna

Architektura nesmí blokovat pozdější doplnění:

- osobních fotografií,
- více kategorií míst,
- rozhleden,
- klášterů,
- technických památek,
- jeskyní,
- pevností,
- výletů / Trip,
- gamifikace,
- automatické synchronizace,
- více uživatelských profilů.

Proto nepojmenovávej základní entitu `Castle`.

Použij:

```text
Place
```

Hrady a zámky jsou pouze první sada typů.

---

# 27. Požadovaná struktura projektu

Navrhni přehlednou monorepo nebo jednoduše organizovanou strukturu.

Například:

```text
/project
    /pc-app
    /pwa
    /shared
        /schemas
    /docs
    /scripts
    README.md
```

Sdílené JSON Schema musí být použitelné v PC i PWA.

---

# 28. Dokumentace

Vytvoř:

```text
README.md
docs/ARCHITECTURE.md
docs/DATA_MODEL.md
docs/IMPORTS.md
docs/JSON_FORMATS.md
docs/DEVELOPMENT.md
```

README musí obsahovat:

- co projekt dělá,
- jak PC aplikaci spustit,
- jak PWA spustit,
- jak vytvořit databázi,
- jak provést export,
- jak provést import,
- jak spustit testy.

---

# 29. Testy

Testy nejsou volitelné u kritických datových operací.

Minimálně otestuj:

## ID

- opakovaný import zachová `public_id`,
- nové místo dostane nové ID,
- stejné externí ID nikdy nevytvoří nové místo.

## Deduplikace

- shoda přes Wikidata ID,
- shoda přes Památkový katalog ID,
- pravděpodobná shoda podle GPS/názvu,
- nejasná shoda skončí v review frontě.

## JSON

- validní catalog import,
- nevalidní catalog import,
- validní diary import,
- opakovaný diary import nevytvoří duplicity.

## Ochrana osobních dat

- aktualizace katalogu nikdy nevymaže návštěvy,
- archivace Place nikdy nevymaže návštěvy.

## Backup

- před rizikovou importní operací vznikne záloha.

---

# 30. Zásady implementace

1. Neoptimalizuj předčasně.
2. Nepřidávej technologie bez jasného přínosu.
3. Nevytvářej vlastní framework.
4. Preferuj standardní knihovny a dobře udržované závislosti.
5. Veškeré databázové změny řeš migracemi.
6. Kritické změny dat musí být transakční.
7. Každý externí importer musí být oddělený modul.
8. Importní vrstva nesmí přímo obsahovat UI logiku.
9. PWA nesmí obsahovat logiku editace master dat.
10. JSON soubory jsou kontrakt mezi PC a PWA.
11. Změna JSON struktury vyžaduje zvýšení `schema_version`.
12. Při nejasné deduplikaci preferuj ruční kontrolu před chybným automatickým sloučením.

---

# 31. Doporučené etapy realizace

Projekt neimplementuj jako jeden velký krok.

## Fáze 1 – Architektura a skeleton

Výstup:

- struktura repozitáře,
- zvolený stack,
- SQLite,
- migrace,
- základní Place model,
- dokumentace architektury.

Bez externích importů.

---

## Fáze 2 – PC master katalog

Výstup:

- CRUD Place,
- typy,
- lokalita,
- filtry,
- detail,
- editace,
- základní dashboard.

---

## Fáze 3 – identity a import framework

Výstup:

- PlaceSource,
- ImportRun,
- ImportReview,
- matching,
- ochrana `public_id`,
- deduplikace,
- testy.

Nejdříve vytvoř testovací importer nad malým fixture datasetem.

---

## Fáze 4 – první skutečný importer

Preferovaně Wikidata.

Výstup:

- stažení,
- normalizace,
- matching,
- preview,
- import,
- opakované spuštění bez duplicit.

---

## Fáze 5 – další zdroje

Postupně:

1. Památkový katalog,
2. RÚIAN,
3. NPÚ,
4. Wikimedia Commons,
5. další doplňkové zdroje.

Po každém zdroji musí fungovat deduplikace.

---

## Fáze 6 – catalog.json

Výstup:

- JSON Schema,
- export,
- verze katalogu,
- testy.

---

## Fáze 7 – PWA katalog

Výstup:

- import `catalog.json`,
- IndexedDB,
- seznam,
- filtry,
- detail,
- offline shell aplikace.

---

## Fáze 8 – deník

Výstup:

- návštěvy,
- více návštěv stejného místa,
- osoby jako jednoduchý seznam,
- hodnocení,
- poznámka,
- `diary.json`,
- import/export,
- idempotence.

---

## Fáze 9 – propojení PC ↔ PWA

Otestuj kompletní scénář:

```text
PC
→ catalog.json
→ PWA
→ vytvořit návštěvu
→ diary.json
→ PC
→ znovu export diary.json
→ nový čistý PWA profil
→ obnovit deník
```

---

# 32. Akceptační scénář MVP

MVP je hotové, pokud lze udělat následující bez ručního zásahu do databáze:

1. Spustím PC aplikaci.
2. Mám SQLite databázi.
3. Importuji testovací nebo reálný katalog památek.
4. Opakovaný import nevytvoří duplicity.
5. Památky mají stabilní `public_id`.
6. Nejasné shody skončí v review.
7. Ručně opravím památku a další import opravu nesmaže.
8. Exportuji `catalog.json`.
9. Na mobilu otevřu PWA.
10. Importuji `catalog.json`.
11. Vyhledám Bouzov.
12. Přidám návštěvu.
13. Přidám druhou návštěvu stejného místa.
14. Exportuji `diary.json`.
15. Na PC importuji `diary.json`.
16. Obě návštěvy se zobrazí u Bouzova.
17. Stejný `diary.json` importuji podruhé.
18. Nevzniknou duplicity.
19. Na PC upravím nebo aktualizuji katalog.
20. Exportuji nový `catalog.json`.
21. Na mobilu katalog aktualizuji.
22. Původní návštěvy zůstanou beze změny.

---

# 33. První úkol pro implementaci

Nezačínej okamžitě programovat celý projekt.

Nejprve:

1. prostuduj toto zadání,
2. navrhni konkrétní technologický stack,
3. navrhni databázové schéma,
4. navrhni přesnou strukturu `catalog.json` a `diary.json`,
5. popiš strategii deduplikace,
6. navrhni strukturu repozitáře,
7. rozděl implementaci na malé fáze,
8. identifikuj rizika,
9. vytvoř `PLAN.md`.

Teprve poté začni Fází 1.

---

# 34. Rozhodovací priority

Pokud jsou požadavky v konfliktu, řiď se tímto pořadím:

1. ochrana osobního deníku,
2. stabilita interních ID,
3. zabránění duplicitám,
4. možnost obnovy ze zálohy,
5. jednoduchost,
6. offline použitelnost PWA,
7. úplnost externích dat,
8. vzhled UI.

---

# 35. Definice úspěchu projektu

Výsledkem nemá být „technologicky zajímavá aplikace“.

Výsledkem má být:

> jednoduchý, dlouhodobě udržitelný osobní katalog míst, který lze bezpečně doplňovat z externích zdrojů a používat na mobilu jako cestovatelský deník bez nutnosti provozovat server nebo cloudovou infrastrukturu.
