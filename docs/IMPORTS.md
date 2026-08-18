# Importy do master katalogu

Importery běží jen na PC. PWA katalog needituje. Každý zdroj vrací stejný `CanonicalRecord`; matching a zápis jsou společné. Importer nesmí sahat do `places` přímo.

UI: `/import` (náhled, zápis, review fronta, master vs zdroj). Před zápisem vznikne záloha SQLite. Fatální chyba → rollback, záloha zůstane.

---

## Kanonický záznam

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

Místa bez GPS se importují se `quality_status = NEEDS_REVIEW`. Nezahazují se.

---

## Deduplikace A / B / C / D

Pořadí je pevné. První úspěšná úroveň vyhraje. Při více různých Place na úrovni A → review, neslučovat.

### A — `MATCHED_EXACT`

Shoda, pokud existuje `place_sources` se stejným `(source_type, external_id)`, nebo jakýmkoli ID z `external_ids` proti už uloženému zdroji (Wikidata QID, katalogové číslo, ÚSKP, OSM ref).

Výsledek: aktualizuj existující Place, **nikdy** negeneruj `public_id`. Nově viditelná externí ID se připojí k témuž Place.

### B — `MATCHED_PROBABLE` (automaticky jen při tvrdé shodě)

Normalizace názvu: lowercase, bez diakritiky pro porovnání, sjednocení mezer, odstranění prefixů `statni hrad|hrad|zamek|zricenina|tvrz|zamecek|statni zamek`.

Automatická shoda, pokud platí **jedna** sada:

1. vzdálenost ≤ 100 m **a** podobnost názvu ≥ 0,90 **a** (stejná obec nebo obec na jedné straně chybí) **a** kompatibilní typy
2. identický normalizovaný název **a** stejná obec **a** vzdálenost ≤ 300 m
3. identický normalizovaný název **a** stejný okres **a** vzdálenost ≤ 80 m
4. identický konkrétní název (ne holé „zámek/hrad/…“) **a** kompatibilní typy **a** (stejná obec nebo obec na jedné straně chybí) **a** vzdálenost ≤ 300 m — typicky OSM centroid vs. bod katalogu
5. identický konkrétní název **a** stejná obec **a** kompatibilní typy, i bez GPS (katalogové řádky bez souřadnic). Katastrální popisky se jako název ignorují.

Kompatibilní typy: prázdná množina na jedné straně, nebo neprázdný průnik, nebo `{CASTLE, CHATEAU, RUIN, MANOR, PALACE, FORTRESS}` mezi sebou. `OTHER` samo o sobě nestačí.

Každé automatické B se zapíše do logu běhu včetně důvodu a vzdálenosti.

### C — `IMPORT_REVIEW`

Podezření, ale ne dost jistota. **Nový Place se nevytvoří.**

Typicky: vzdálenost ≤ 400 m a podobnost ≥ 0,75; stejná obec a podobnost ≥ 0,82; dvě různá existující Place by vyhovovala úrovni B.

Samotný shodný název (bez obce nebo GPS) nestačí. Záznam s vlastním externím ID se založí jako nové místo.

UI: [Sloučit] [Vytvořit jako nové] [Ignorovat]. Ignorované `(source_type, external_id)` se při dalším importu znovu neotevře, dokud uživatel ignoraci nezruší.

Po [Sloučit]: `place_sources` se připojí k existujícímu Place, `public_id` se nemění, další import už jde úrovní A.

### D — nové místo

Žádný kandidát A/B/C → INSERT Place, nový UUIDv7, první `place_sources` řádek.

### Opakovaný import

```text
records_created + records_updated + records_unchanged + records_review + records_ignored + records_failed
  == records_received

0 ztracených public_id
0 duplicit na stejné (source_type, external_id)
```

Náhled (dry-run) je povinný před aplikací větší aktualizace.

---

## Ochrana ručních změn

Úprava pole v UI zapíše `place_field_overrides` a aktualizuje master. Nový import vždy aktualizuje `place_sources` / `place_source_values`. Pokud override existuje, master pole se nemění; rozdíl se objeví ve frontě „Master vs zdroj“.

Priorita zdrojů při automatickém zápisu pole bez override:

| Pole | Preferovaný zdroj |
|---|---|
| heritage_status, unesco | pamatkovy_katalog / uskp |
| municipality, district, region, kódy | ruian > pamatkovy_katalog > wikidata |
| latitude, longitude | pamatkovy_katalog > wikidata > osm |
| name | wikidata (cs) |
| official_website | npu > wikidata > osm |
| wikipedia_url | wikipedia / wikidata |
| image | wikimedia_commons přes wikidata P18 |
| opening_hours_url | npu > official_web > osm |
| ticket_url | npu > official_web |
| osm_opening_hours | osm |
| visitability | npu > osm > official_web > wikidata |

Ruční master má vždy přednost. Zříceniny (`typ RUIN` nebo `condition=RUIN`) bez ručního override dostanou `FREE_ACCESS` — otevírací doba se u nich nehledá.

---

## Zdroje

Všechny síťové importery posílají povinný `User-Agent`. Stažená odpověď se ukládá do `<data_dir>/cache/` — v UI jde použít poslední soubor bez sítě.

### Fixture

`fixtures/import/small_dataset.json` a `small_dataset_update.json`. Pro testy matchingu, ne pro produkční katalog.

### Wikidata

První páteř katalogu. SPARQL z `query.wikidata.org` po typech (hrad, zámek, zřícenina, tvrz, palác, rozhledna, zoo, jeskyně). Tvrz je Wikidata `Q1408475`, palác `Q16560`, rozhledna `Q1440300`, zoo `Q43501`, jeskyně `Q35509`. U míst, která už mají QID ale typový SPARQL je minul (typicky palác natažený přes OSM), se P18 doplní samostatným dotazem. Licence CC0. QID se ukládá jako `place_sources(wikidata, Q…)`.

Po typech se dávkově doplní stav objektu (P5816 / P576) a volitelně rok vzniku (P571) se slohem (P149).

Obec / okres / kraj se berou z hierarchického `P131+` (ne jen z přímé části obce). Adresa se složí z čísla popisného `P4856` a přímého `P131` (např. Dolní Adršpach 75). Text Wikipedie se neparsuje.

### Památkový katalog

CSV otevřená data (KP / NKP / UNESCO). ÚSKP a katalogové číslo jsou dvě různá externí ID. Licence CC BY 4.0.

### RÚIAN

Jen normalizace názvů obce / okresu / kraje a kódů u už existujících míst. Neimportuje nová místa. Pokud místo má GPS a chybí obec, doplní se reverse geocodingem Nominatim (1 req/s, cache) a výsledek se namapuje na číselník RÚIAN.

### NPÚ spravované objekty

Oficiální URL a návštěvní odkazy. Ne autorské texty ani fotky z webů objektů. Anotace z Geoportálu jen jako strukturovaná fakta + URL (CC BY-SA 4.0 u opendat).

### Wikimedia Commons

Metadata k P18 (autor, licence, atribuce, thumbnail URL). Binární fotky se do databáze nestahují. Licence je u každé fotografie.

### Wikipedia

Jen URL a kontrola úplnosti kategorií. Texty článků se nekopírují.

### OpenStreetMap

Volitelný doplněk, ne master katalog. Matching přes tag `wikidata` nebo A/B/C. Licence ODbL. Přístupnost se bere z `opening_hours` (včetně sezónních měsíců), `tourism=attraction|museum`, `fee`, `access` a `ruins=yes` (volný přístup, pokud není `access=private`). Samotný řetězec `opening_hours` se ukládá do `osm_opening_hours` a jde do `catalog.json` — PWA z něj pozná „dnes otevřeno / sezóna“. Volitelně i `dogs`, `payment` a zázemí (`toilets` na místě; kavárna / restaurace / hřiště do 350 m).

### Oficiální weby

Bez zadaných `public_id` všechna místa s `official_website`, kde je `visitability=UNKNOWN` nebo chybí `opening_hours_url` / `ticket_url`. S ID i místa, která už odkazy mají (obnova). Zříceniny a ruční override přístupnosti se přeskakují. Stáhne se homepage, z JSON-LD a odkazů se berou návštěvní signály a URL otevírací doby / vstupného. HTML ani autorský text se neukládá. Chybějící konvenční NPÚ cesty `/navstevni-doba` a `/vstupne` se ověří HTTP 2xx; 404 se nezapíše. Hrady.cz a CzechTourism se nescrapují.

Na detailu místa v PC je tlačítko **Doplnit z oficiálního webu** (náhled/apply stejného importeru pro jedno ID).

Hrady.cz a CzechTourism se nescrapují a nemají API importer.

---

## Co import nemění

Katalogový import nikdy nemění tabulky deníku (`visits`, `place_journal_states`). Archivace Place návštěvy nesmaže. `public_id` se po vytvoření negeneruje znovu.
