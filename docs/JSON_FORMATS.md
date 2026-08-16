# Formáty JSON — catalog.json a diary.json

Kontrakt mezi PC a PWA. Změna tvaru = zvýšení `schema_version`. Neznámá verze se odmítne, nikdy se tiše neparsuje.

Schémata: `shared/schemas/catalog.schema.json`, `shared/schemas/diary.schema.json`.  
Ukázky: `fixtures/catalog.sample.json`, `fixtures/diary.sample.json`.

Pravidlo ID:

- JSON `places[].id` = `Place.public_id` (UUIDv7)
- JSON `visits[].id` = `Visit.public_id` (UUIDv7)
- JSON `trips[].id` = `Trip.public_id` (UUIDv7)
- JSON `place_id` = `Place.public_id`
- Integer databázová `places.id` / `visits.id` / `trips.id` se do JSON nikdy nedostanou

---

## catalog.json

Soubor master katalogu. Osobní deník v něm není. Archivovaná místa se neexportují.

`catalog_version` je celé číslo v `app_meta`. Zvýší se jen když se změní obsah míst (hash kanonického JSON pole `places`). Prázdný re-export se stejnými daty verzi nezvýší. PWA podle toho pozná „už mám tuto verzi“.

### Příklad

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
        "heritage_catalog": "https://pamatkovykatalog.cz/uskp/17905",
        "opening_hours": null,
        "tickets": null
      },
      "image": {
        "thumbnail_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Hrad_Bouzov.jpg?width=640",
        "original_url": "https://commons.wikimedia.org/wiki/File:Hrad_Bouzov.jpg",
        "attribution": "Jan Novák / Wikimedia Commons",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/"
      }
    }
  ]
}
```

`image` může být `null`. Souřadnice mohou být `null` — PWA místo zařadí do seznamu, ne na mapu. Hradozámek = `types: ["CASTLE", "CHATEAU"]`, kód `CASTLE_CHATEAU` neexistuje.

### Co do katalogu nesmí

- integer databázová ID
- `raw_data`, importní logy, review fronta
- `quality_status`, `archived_at`, override tabulky
- osobní návštěvy, wishlist, poznámky, výlety
- velké binární obrázky

### PWA při importu katalogu

1. Validace JSON Schema.
2. Kontrola `schema_version` (MVP: pouze `1`).
3. Diff proti aktuální IndexedDB: nové / změněné / zmizelé `id`.
4. Náhled počtů (včetně návštěv u zmizelých míst).
5. Transakčně nahradit **jen** store `places`.
6. Store `visits` a `place_states` se nemění.
7. Uložit `catalog_version`.
8. Návštěvy, jejichž `place_id` v novém katalogu chybí, zůstanou a v UI se označí jako „místo už není v katalogu“.

PC export: tlačítko na přehledu / v katalogu, nebo `python -m app.cli export-catalog`. Výchozí cesta: `<data_dir>/export/catalog.json`.

---

## diary.json

Oddělený soubor. Katalog v něm není. Přenos deníku je vždy sloučení podle ID, ne náhrada celého deníku.

Import přijímá `schema_version` 1 i 2. Verze 1 pole `trips` nemá — chybějící pole se bere jako prázdný seznam a **nesmaže** výlety, které už v cíli jsou. Export po této fázi je vždy verze 2 a pole `trips` obsahuje (i prázdné).

### Příklad (verze 2)

```json
{
  "schema_version": 2,
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
  ],
  "trips": [
    {
      "id": "0198f93b-618d-762f-a589-ccf375139dd8",
      "name": "Olomoucko",
      "planned_on": "2026-08-20",
      "origin": null,
      "notes": null,
      "stops": [
        {
          "place_id": "0198f23a-5e5e-7b31-a8be-8c99507a2138",
          "sort_order": 0,
          "note": null
        }
      ],
      "created_at": "2026-08-16T10:00:00+02:00",
      "updated_at": "2026-08-16T10:00:00+02:00",
      "deleted_at": null
    }
  ]
}
```

Ukázka `fixtures/diary.sample.json` zůstává ve verzi 1 (bez `trips`) — ověřuje zpětnou kompatibilitu.

`exported_from` je `"pwa"` nebo `"pc"`. Slouží diagnostice, ne logice slučování.

`updated_at` a `deleted_at` jsou u návštěv, `place_states` i výletů. Smazání se přenáší jako soft-delete; záznamy se fyzicky nemažou.

### Import deníku (PC i PWA)

Před importem záloha (PC: SQLite backup, PWA: snapshot posledních 5 deníků v IndexedDB).

Pro každou návštěvu podle `visits[].id`:

| Stav | Akce |
|---|---|
| ID neexistuje | INSERT |
| ID existuje a `incoming.updated_at` > `local.updated_at` | UPDATE všech deníkových polí |
| ID existuje a příchozí není novější | beze změny |
| `deleted_at` nastaveno u novějšího záznamu | soft-delete |

Stejné pravidlo pro `place_states` podle `place_id` a pro `trips` podle `trips[].id`. Při shodném `updated_at` vyhraje příchozí soubor a zapíše se varování.

Neznámé `place_id` v `trips[].stops[]` výlet nesmaže a Place nezakládá (stejně jako osiřelá návštěva).

Nikdy:

- nevytvářet Place
- neměnit master sloupce Place
- nevytvářet druhou návštěvu nebo výlet se stejným `id`

Neznámé `place_id`: návštěvu i zastávku uložit, zařadit issue, v UI „neznámé místo“ / „místo už není v katalogu“. Stejný soubor dvakrát = nula nových návštěv i výletů.

PC: přehled (`/`), `/trips`, nebo `python -m app.cli export-diary` / `import-diary`.  
PWA: stránka Soubory.
