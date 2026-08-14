# Cestovatelský deník hradů a zámků ČR — lokální PWA

**Verze 2** — bez backendu, bez cloudu, bez účtů. Data žijí v telefonu a v PC, výměna přes jeden soubor na Dropboxu.

---

## 1. Co se oproti v1 změnilo a proč

Zadání se zjednodušilo zásadním způsobem: **uživatel je jeden** (švagrová), švagr je jen vývojář, ne druhý zapisovatel. Tím padá jediný argument, který mluvil pro Supabase — sdílení mezi dvěma lidmi v reálném čase.

Zbývá jediný reálný požadavek na synchronizaci: *„zapsat na telefonu → dostat to do PC a tam plánovat cesty"*. To zvládne obyčejný JSON soubor v Dropboxu. Žádný server, žádná registrace, žádné pozastavování projektu po 7 dnech nečinnosti, žádné free-tier limity, nulové provozní náklady, nulová údržba. Pro osobní deník je to **správná volba** — cloud by tady byl zbytečná režie, kterou by někdo musel roky udržovat naživu.

Druhá zásadní změna: **plánování výletů se stává první třídou**, ne dodatkem. PC verze = plánovač, telefon = zapisovač v terénu.

---

## 2. Architektura

```
┌─────────────────────────┐         ┌─────────────────────────┐
│  PC (Chrome/Edge)       │         │  Telefon (PWA na ploše) │
│  ─────────────────────  │         │  ─────────────────────  │
│  stejná PWA             │         │  stejná PWA             │
│  IndexedDB (Dexie)      │         │  IndexedDB (Dexie)      │
│  → plánování výletů     │         │  → zápis v terénu       │
│  → velká mapa           │         │  → foto z fotoaparátu   │
│  → export PDF deníku    │         │  → offline              │
└───────────┬─────────────┘         └───────────┬─────────────┘
            │                                   │
            │   export/import  denik.json       │
            └──────────────┬────────────────────┘
                           ▼
                  ┌─────────────────┐
                  │    Dropbox      │
                  │  /Denik/        │
                  │   denik.json    │
                  │   fotky.zip     │
                  └─────────────────┘
```

**Aplikace je statická stránka.** Nasadí se na Netlify / Cloudflare Pages / GitHub Pages zdarma, jen jako HTML+JS. Nemá server, nemá databázi, nemá API. Vše běží v prohlížeči.

**Seznam památek je součástí aplikace.** Soubor `mista.json` (vygenerovaný jednorázově z Wikidata + NPÚ) se přibalí jako statický asset. Při prvním spuštění se nahraje do IndexedDB. Když švagr časem seznam aktualizuje, nasadí novou verzi aplikace a v ní bude tlačítko *„Aktualizovat seznam míst"*, které přepíše jen katalogová data a **nesáhne na návštěvy a poznámky**. Tohle je klíčový trik, který úplně eliminuje potřebu backendu.

---

## 3. Rozdělení rolí

| Kdo | Co dělá | Jak často |
|---|---|---|
| **Švagr** | vygeneruje `mista.json` ze SPARQL, napíše PWA v Cursoru, nasadí na Netlify | jednorázově, pak 1–2× ročně update seznamu |
| **Švagrová** | otevře URL v telefonu → „Přidat na plochu" → používá | denně/o víkendech |

Švagrová se nikdy nedotkne Cursoru, konzole ani terminálu. Vidí jen appku a Dropbox, který už na telefonu má.

---

## 4. Datový model

Zásadní rozdíl proti serverové verzi: **žádná autoinkrementální ID.** Když se stejná databáze mění na dvou zařízeních nezávisle, číselná ID se nutně srazí. Proto **UUID** (`crypto.randomUUID()`), plus `updated_at` a `deleted_at` u každého záznamu — bez toho nelze slučovat.

### Dexie schéma

```js
import Dexie from 'dexie';

export const db = new Dexie('hradyDenik');

db.version(1).stores({
  // katalog míst - přichází z mista.json, uživatel needituje (kromě vlastní poznámky)
  mista:      'id, nazev, typ, kraj, okres, zpristupneno, wikidata_id, *stitky',

  // uživatelská data - to, co se synchronizuje
  navstevy:   'id, misto_id, datum, updated_at, deleted_at',
  fotky:      'id, navsteva_id, updated_at, deleted_at',
  wishlist:   'id, misto_id, priorita, updated_at, deleted_at',
  vylety:     'id, nazev, datum_od, datum_do, stav, updated_at, deleted_at',
  zastavky:   'id, vylet_id, misto_id, poradi, updated_at, deleted_at',
  poznamky:   'id, misto_id, updated_at, deleted_at',   // vlastní poznámka k místu (mimo návštěvu)

  // technické
  meta:       'klic'   // schema_version, device_id, posledni_sync
});
```

### Typy (TypeScript)

```ts
type Misto = {
  id: string;              // UUID, stabilní napříč aktualizacemi katalogu
  nazev: string;
  typ: 'hrad' | 'zamek' | 'zricenina' | 'tvrz' | 'klaster' | 'rozhledna' | 'jine';
  zpristupneno: boolean;   // hlavní filtr "dá se navštívit"
  lat?: number;
  lon?: number;
  adresa?: string;
  obec?: string;
  okres?: string;
  kraj?: string;
  popis?: string;
  zdroj_popisu?: 'wikipedia' | 'npu';
  web?: string;
  foto_url?: string;       // odkaz na Wikimedia Commons, neukládáme lokálně
  wikidata_id?: string;
  uskp?: string;           // rejstříkové číslo ÚSKP
  provozovatel?: string;   // NPÚ / obec / soukromý
  vstupne?: string;
  sezonnost?: string;
  otviraci_doba?: string;  // z OSM opening_hours
  stitky?: string[];       // UNESCO, dětem přátelské, pes vítán, bezbariérové...
};

type Navsteva = {
  id: string;              // UUID
  misto_id: string;
  datum: string;           // 'YYYY-MM-DD'
  s_kym?: string;
  hodnoceni?: 1|2|3|4|5;
  zazitek?: string;        // volný text - jádro deníku
  pocasi?: string;
  cena?: number;
  doba_min?: number;
  vylet_id?: string;       // pokud vznikla v rámci plánovaného výletu
  updated_at: string;      // ISO timestamp - rozhoduje při slučování
  deleted_at?: string;     // soft delete, aby se smazání přeneslo
};

type Fotka = {
  id: string;
  navsteva_id: string;
  blob: Blob;              // zmenšeno na max 1600 px, JPEG q0.8
  nazev_souboru: string;
  exif_lat?: number;
  exif_lon?: number;
  poridil?: string;        // EXIF DateTimeOriginal
  updated_at: string;
  deleted_at?: string;
};

type Vylet = {
  id: string;
  nazev: string;           // "Jižní Čechy - květen"
  datum_od?: string;
  datum_do?: string;
  stav: 'napad' | 'planovany' | 'probiha' | 'hotovy';
  poznamka?: string;
  updated_at: string;
  deleted_at?: string;
};

type Zastavka = {
  id: string;
  vylet_id: string;
  misto_id: string;
  poradi: number;
  planovany_datum?: string;
  planovany_cas?: string;
  poznamka?: string;       // "rezervovat prohlídku dopředu"
  splneno: boolean;
  updated_at: string;
  deleted_at?: string;
};
```

---

## 5. Synchronizace přes Dropbox

### Formát výměnného souboru

```json
{
  "schema_version": 1,
  "exported_at": "2026-08-09T14:32:00.000Z",
  "device_id": "telefon-eva",
  "navstevy": [ ... ],
  "wishlist": [ ... ],
  "vylety": [ ... ],
  "zastavky": [ ... ],
  "poznamky": [ ... ]
}
```

**Katalog míst se do exportu nedává.** Je v aplikaci na obou zařízeních stejný. Export tak má typicky **desítky až stovky kilobajtů** — pošle se přes Dropbox okamžitě i na mobilních datech.

### Pravidla slučování — tohle je nejdůležitější věc celého návrhu

Import **NIKDY nepřepisuje celou databázi.** Slučuje po záznamech:

```js
async function importuj(soubor) {
  const data = JSON.parse(await soubor.text());
  if (data.schema_version !== 1) throw new Error('Nekompatibilní verze souboru');

  const tabulky = ['navstevy', 'wishlist', 'vylety', 'zastavky', 'poznamky'];
  let novych = 0, aktualizovanych = 0, preskocenych = 0;

  await db.transaction('rw', tabulky.map(t => db[t]), async () => {
    for (const tabulka of tabulky) {
      for (const zaznam of (data[tabulka] ?? [])) {
        const existujici = await db[tabulka].get(zaznam.id);
        if (!existujici) {
          await db[tabulka].put(zaznam);
          novych++;
        } else if (zaznam.updated_at > existujici.updated_at) {
          await db[tabulka].put(zaznam);   // vyhrává novější zápis
          aktualizovanych++;
        } else {
          preskocenych++;                   // lokální je novější, necháváme
        }
      }
    }
  });

  return { novych, aktualizovanych, preskocenych };
}
```

Aplikace po importu ukáže lidsky srozumitelné hlášení: *„Načteno 4 nové návštěvy, 1 aktualizována, 12 beze změny."* To je pro netechnickou uživatelku podstatné — musí vidět, že se něco stalo, a co.

**Proč „last write wins" stačí:** je jeden uživatel. Reálný konflikt (tentýž záznam změněný na obou zařízeních nezávisle mezi dvěma synchronizacemi) je natolik okrajový, že složitější řešení nemá smysl. Jistota, že to v praxi nebude vadit: **~90 %.** Pojistkou je automatická záloha před každým importem (viz níže).

### Workflow v praxi

**Telefon → PC** (po výletě):
1. V appce *Nastavení → Export deníku*
2. Prohlížeč nabídne stažení / sdílení → vybere se **Dropbox → složka /Denik**
3. Na PC se soubor sám objeví ve složce Dropboxu
4. V PC verzi appky *Import* → vybrat soubor → hotovo

**PC → telefon** (naplánované výlety):
Stejný postup opačně. Naplánovaný výlet se tak ocitne v telefonu ještě před odjezdem, i offline.

### Zjednodušení na PC: File System Access API

V Chrome a Edge na desktopu si aplikace může jednorázově vyžádat přístup přímo do složky `Dropbox/Denik/` a pak automaticky číst i zapisovat `denik.json` bez klikání na dialogy — handle se uchová v IndexedDB a přežije zavření prohlížeče. To je z hlediska pohodlí velký rozdíl.

Háček: **File System Access API funguje jen v Chromiu na desktopu.** Firefox a Safari ho nemají, na Androidu a iOS není. Jistota: **~90 %.** Prakticky to znamená:
- **PC:** poloautomatická synchronizace (jedno tlačítko „Synchronizovat"), pokud se použije Chrome/Edge
- **Telefon:** vždy ruční export/sdílení do Dropboxu, cca 3 klepnutí

Doporučuji naprogramovat obojí — na PC zkusit File System Access, a když není k dispozici, spadnout na klasické stažení/nahrání souboru.

### Pojistky, na které se nesmí zapomenout

1. **Automatická záloha před každým importem** — aplikace uloží aktuální stav do IndexedDB jako snapshot (posledních 5). Kdyby import něco pokazil, jde se vrátit.
2. **Připomínka exportu** — pokud od posledního exportu uplynulo víc než 14 dní nebo přibylo 5+ návštěv, ukázat nenápadnou lištu *„Nezálohováno 3 týdny — exportovat?"*.
3. **Nikdy ne přepis, vždy sloučení.** Tlačítko „Nahradit vše" v appce vůbec nebude, aby nešlo omylem přijít o data.

---

## 6. Fotky

**Fotky památek** (ilustrační) = jen URL na Wikimedia Commons, nestahují se. Šetří místo i licenční starosti.

**Vlastní fotky** se ukládají jako Blob přímo do IndexedDB, ale **před uložením se zmenší** — max 1600 px delší strana, JPEG kvalita 0.8. Z 5 MB fotky z telefonu zbude ~300 KB. Bez tohoto kroku databáze během roku nabobtná do gigabajtů a export přestane být použitelný.

```js
async function zmensiFotku(file, maxPx = 1600, kvalita = 0.8) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, maxPx / Math.max(bitmap.width, bitmap.height));
  const canvas = new OffscreenCanvas(bitmap.width * scale, bitmap.height * scale);
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return canvas.convertToBlob({ type: 'image/jpeg', quality: kvalita });
}
```

**Dva režimy exportu:**

| Režim | Obsah | Velikost | Kdy |
|---|---|---|---|
| **Rychlý export** | jen `denik.json`, bez fotek | desítky–stovky kB | běžná synchronizace, klidně týdně |
| **Plná záloha** | ZIP: `denik.json` + `fotky/` | desítky–stovky MB | jednou za čas, na Wi-Fi |

Plná záloha přes JSZip. Fotky pojmenovat `{navsteva_id}_{fotka_id}.jpg`, aby se při importu daly spárovat zpět. EXIF GPS a datum čti knihovnou `exifr` **před** zmenšením (canvas metadata zahodí) — z toho pak appka sama navrhne, ke kterému místu a datu fotka patří.

---

## 7. Import katalogu památek (beze změny z v1)

Tahle část zůstává platná — je to nejcennější kus celého projektu.

### Zlatý standard zdrojů

1. **Wikidata** (SPARQL, licence **CC0** — bez omezení, bez atribuce) → páteř seznamu: název, souřadnice, obrázek z Commons, okres, kraj, typ, Wikipedia, web, rejstříkové číslo ÚSKP.
2. **Otevřená data NPÚ** (`pamatkovykatalog.cz/opendata/`, CSV, **CC BY-SA 4.0**, aktualizace 1× měsíčně) → přesná adresa, obec, anotace, potvrzení památkové ochrany. Spojovací klíč: rejstříkové číslo ÚSKP (`P4075` ve Wikidata).
3. **OpenStreetMap / Overpass** (**ODbL**) → otevírací doby (`opening_hours`), web, bezbariérovost. Spojovací klíč: tag `wikidata`.

**Zpřístupněno = TRUE** nastav pro objekty ve správě NPÚ (**106 památkových objektů** — 29 hradů, 59 zámků, 5 hradozámků, kláštery, kostely, zahrady…) a pro ty, co mají v OSM vyplněné `opening_hours` nebo `tourism=attraction`. Zbytek zůstane jako „lze si prohlédnout zvenku".

**Co nescrapovat:** hrady.cz, turistika.cz, zamky-hrady.cz. Jsou to komerční databáze chráněné zvláštním právem pořizovatele (§88 a násl. autorského zákona) — smí se vytěžovat jen nepodstatné části a nesystematicky. Stažení celého soupisu = zásah do práva. Kudy z nudy sice má API, ale jen pro smluvní partnery s limitem 1 volání/hodinu — nepoužitelné. Z otevřených zdrojů dostaneš stejně dobrý výsledek bez rizika.

### SPARQL dotaz

```sparql
SELECT DISTINCT ?item ?itemLabel ?typeLabel ?coord ?image
                ?okresLabel ?krajLabel ?web ?uskp ?article WHERE {
  VALUES ?tridy { wd:Q23413 wd:Q751876 wd:Q109607 }   # hrad, zámek, zřícenina
  ?item wdt:P31/wdt:P279* ?tridy .
  ?item wdt:P17 wd:Q213 .                              # stát = Česko
  ?item wdt:P31 ?type .
  OPTIONAL { ?item wdt:P625 ?coord . }
  OPTIONAL { ?item wdt:P18 ?image . }
  OPTIONAL { ?item wdt:P131 ?okres . ?okres wdt:P31 wd:Q3389049 . }
  OPTIONAL { ?item wdt:P131* ?kraj . ?kraj wdt:P31 wd:Q1615742 . }
  OPTIONAL { ?item wdt:P856 ?web . }
  OPTIONAL { ?item wdt:P4075 ?uskp . }
  OPTIONAL { ?article schema:about ?item ;
                      schema:isPartOf <https://cs.wikipedia.org/> . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "cs,en" . }
}
```

Pro rozšíření přidej do `VALUES` další třídy: tvrz ≈ `wd:Q2288643`, rozhledna ≈ `wd:Q1440476`, klášter ≈ `wd:Q44613`. **QID si vždy ověř kliknutím v `query.wikidata.org`** — u méně obvyklých typů se pletou.

### Generovací skript

```python
import requests, json, csv, uuid

WDQS = "https://query.wikidata.org/sparql"
QUERY = open("dotaz.sparql", encoding="utf-8").read()
UA = {"User-Agent": "HradyDenik/1.0 (osobni projekt; kontakt@example.cz)"}

def fetch_wikidata():
    r = requests.get(WDQS, params={"format": "json", "query": QUERY}, headers=UA)
    r.raise_for_status()
    out = []
    for b in r.json()["results"]["bindings"]:
        g = lambda k: b[k]["value"] if k in b else None
        lat = lon = None
        if (c := g("coord")) and c.startswith("Point("):
            lon, lat = map(float, c[6:-1].split())
        wd_id = g("item").split("/")[-1]
        out.append({
            # UUID odvozené z Wikidata ID = stabilní napříč regeneracemi katalogu
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"wikidata:{wd_id}")),
            "wikidata_id": wd_id,
            "nazev": g("itemLabel"),
            "typ": mapuj_typ(g("typeLabel")),
            "lat": lat, "lon": lon,
            "foto_url": g("image"),
            "okres": g("okresLabel"),
            "kraj": g("krajLabel"),
            "web": g("web"),
            "uskp": g("uskp"),
            "wikipedia": g("article"),
            "zpristupneno": False,
        })
    return out

def mapuj_typ(label):
    l = (label or "").lower()
    if "zřícen" in l or "ruin" in l: return "zricenina"
    if "zámek" in l or "chateau" in l or "palace" in l: return "zamek"
    if "tvrz" in l: return "tvrz"
    if "klášter" in l: return "klaster"
    if "rozhled" in l: return "rozhledna"
    if "hrad" in l or "castle" in l: return "hrad"
    return "jine"

def merge_npu(mista):
    npu = {}
    for fname in ("npu_opendata_KP.csv", "npu_opendata_NKP.csv"):
        with open(fname, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                npu[row["rejstříkové_číslo_ÚSKP"]] = row
    for m in mista:
        if n := npu.get(m.get("uskp")):
            m["adresa"] = n["adresa"]
            m["obec"] = n["obec"]
            m["popis"] = n["anotace"]
            m["zdroj_popisu"] = "npu"
            m["chranena_pamatka"] = True
    return mista

data = merge_npu(fetch_wikidata())
data = [m for m in data if m["lat"]]          # bez souřadnic nemá smysl
json.dump(data, open("mista.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"Uloženo {len(data)} míst.")
```

**Klíčový detail:** `uuid5` odvozené z Wikidata ID znamená, že když švagr za rok katalog přegeneruje, místa si podrží **stejná ID** — a všechny návštěvy u nich zůstanou navázané. Bez toho by aktualizace katalogu rozbila deník.

---

## 8. Plánování výletů (fáze 2)

Tady je hlavní přidaná hodnota PC verze. Návrh funkcí seřazený podle poměru užitek/práce:

**Musí být:**
- **Wishlist** — hvězdička u místa, samostatný seznam „chci navštívit"
- **Výlet = pojmenovaná skupina zastávek** s pořadím, datem a poznámkou
- **Mapa výletu** — zastávky spojené čarou v pořadí, odhad kilometrů
- **Přenos výletu do telefonu** přes běžnou synchronizaci; v terénu se zastávka odškrtne a rovnou z ní vznikne návštěva (předvyplněné místo a datum)

**Mělo by být:**
- **„Co je do 50 km ode mě a ještě jsem tam nebyl"** — nejužitečnější funkce celé appky, filtr podle aktuální GPS
- **Barevná mapa** — zelená navštíveno / žlutá wishlist / šedá zbytek. Vizuálně nejsilnější prvek, dělá radost.
- **Statistiky pokrytí** — „Jihomoravský kraj: 37 % zámků navštíveno", progress bary po krajích
- **Filtr podle sezóny** — v listopadu skrýt to, co má zavřeno

**Až zbude čas:**
- Odznaky (celý kraj, 10/50/100 památek, všechny UNESCO objekty)
- Export deníku do PDF (jsPDF nebo tisk prohlížeče) — hezký dárek k Vánocům
- Evidence turistických známek a razítek
- Automatické přiřazení fotek podle EXIF GPS a času k místu a návštěvě
- Offline mapové podklady (PMTiles) pro místa bez signálu

Trasování mezi zastávkami (skutečná silniční trasa, čas jízdy) **nedělej** — vyžadovalo by to routing API s klíčem a omezeními, tedy přesně tu závislost na cloudu, kterou jsme právě vyhodili. Vzdušná čára a přímá vzdálenost stačí, na navigaci je Mapy.cz.

---

## 9. Rizika, na která si dát pozor

**iOS maže data webových aplikací.** Safari smaže IndexedDB stránky, kterou uživatel 7 dní nepoužil — pokud není přidaná na plochu. Jistota **~80 %**, detaily se v jednotlivých verzích iOS měnily. Opatření:
- při prvním spuštění důrazně nabídnout *„Přidat na plochu"* (na iOS to jde jen ze Safari přes Sdílet)
- zavolat `navigator.storage.persist()` a stav zobrazit v nastavení
- pravidelný export do Dropboxu tohle riziko stejně eliminuje — proto ta připomínka po 14 dnech

Na Androidu v Chrome je situace výrazně lepší (kvóta v řádu jednotek až desítek GB podle volného místa), jistota **~85 %**.

**Ztráta telefonu = ztráta nezálohovaných zápisů.** Řešeno jen disciplínou exportu. Pokud by to vadilo, je to jediný argument pro návrat k cloudu — ale u deníku výletů to podle mě nevadí.

**Kvalita Wikidata je nerovnoměrná.** Část záznamů nemá souřadnice, obrázek nebo okres. Skript ty bez souřadnic filtruje; zbytek se dočistí ručně v appce (ať je editace polí místa možná).

**Kolik míst to bude:** odhad pro hrady + zámky + zříceniny řádově **2 000–3 500** záznamů, jistota jen **~55 %** — nedokázal jsem to ověřit živě, endpoint byl nedostupný. Spusť dotaz sám. Pro IndexedDB je to tak jako tak zanedbatelné množství.

---

## 10. Stack a plán realizace

**Stack:** React + Vite + TypeScript, `vite-plugin-pwa` (service worker, manifest, offline), **Dexie.js** (IndexedDB), **MapLibre GL JS** (mapa — MIT, vektorové dlaždice, barvení markerů podle dat, možnost offline PMTiles), `exifr` (EXIF), `JSZip` (plná záloha), `jsPDF` (export deníku). Hosting: **Netlify** zdarma.

Pokud by MapLibre působilo jako zbytečná složitost, **Leaflet** (42 kB, rastrové dlaždice) postavíš za třetinu času a pro tenhle účel bohatě stačí. Rozhodni podle toho, jestli chceš offline mapu — s ní MapLibre, bez ní Leaflet.

**Plán:**

| Den | Co |
|---|---|
| **1** | Python skript → SPARQL → NPÚ CSV merge → `mista.json`. Ověřit počty a kvalitu dat. |
| **2** | Kostra PWA: Vite + React + `vite-plugin-pwa` + Dexie, načtení `mista.json` při prvním spuštění, seznam s filtry (typ, kraj, zpřístupněno, hledání). |
| **3** | Detail místa, formulář návštěvy, fotky (zmenšení + IndexedDB), wishlist. |
| **4** | Export/import JSON se slučováním, automatická záloha před importem, na PC File System Access. **Otestovat na skutečném telefonu přes Dropbox.** |
| **5** | Mapa MapLibre s barevnými markery, „do 50 km ode mě", statistiky krajů. |
| **6+** | Výlety a plánování, PDF export, odznaky. |

**Prompty do Cursoru:**

- *„Vytvoř Vite + React + TypeScript PWA s vite-plugin-pwa, offline-first (cache-first assety). Přidej Dexie databázi podle přiloženého schématu a při prvním spuštění naimportuj `public/mista.json` do tabulky `mista`."*
- *„Přidej stránku seznamu s virtualizovaným scrollem, fulltextovým hledáním v názvu a obci a filtry: typ, kraj, zpřístupněno, navštíveno/nenavštíveno."*
- *„Naimplementuj export/import: export vytvoří JSON s uživatelskými tabulkami (bez katalogu míst), import slučuje po záznamech podle UUID s pravidlem novější `updated_at` vyhrává, před importem uloží snapshot do tabulky `zalohy`, a vrátí počty nových/aktualizovaných/přeskočených."*
- *„Přidej upload fotky s předchozím načtením EXIF přes exifr (GPS + DateTimeOriginal), zmenšením na 1600 px přes OffscreenCanvas a uložením Blobu do Dexie; podle EXIF GPS navrhni nejbližší místo z katalogu."*
- *„Na desktopu v Chromiu použij File System Access API pro trvalý handle do složky Dropbox/Denik a tlačítko Synchronizovat; pokud API není dostupné, spadni na klasické stažení a `<input type=file>`."*

---

## 11. Doporučení

1. **Jdi do čistě lokální varianty.** Pro jednoho uživatele je cloud zbytečná režie s doživotní údržbou. Dexie + JSON přes Dropbox je zdarma navždy, funguje offline a nemá co spadnout.
2. **Katalog míst přibal do aplikace jako statický asset**, uživatelská data drž odděleně. Aktualizace seznamu se pak dělá nasazením nové verze appky a nikdy nesáhne na deník.
3. **UUID + `updated_at` + `deleted_at` od úplně prvního commitu.** Dodělat to zpětně bolí. Tohle je jediné místo, kde se nevyplatí šetřit.
4. **Import vždy slučuje, nikdy nepřepisuje**, a před každým importem se dělá snapshot. Tlačítko „Nahradit vše" ať v appce vůbec není.
5. **Zmenšuj fotky před uložením** a odděl rychlý export (jen JSON) od plné zálohy (ZIP s fotkami).
6. **Na iOS trvej na přidání na plochu** a zavolej `persist()`. Pravidelný export je stejně hlavní pojistka.
7. **Data ber z Wikidata (CC0) + NPÚ (CC BY-SA) + OSM (ODbL).** Komerční katalogy nescrapuj — právně sporné a zbytečné.
8. **Plánovač výletů dělej až jako druhou fázi**, ale datový model (`vylety`, `zastavky`) navrhni hned teď. Přidat tabulky do Dexie později znamená migraci, kterou si můžeš ušetřit.

**Kdy by se doporučení změnilo:** pokud by časem zapisovali dva lidé nezávisle a chtěli vidět zápisy toho druhého hned, vrať se k Supabase — ale ne dřív. Do té doby je jakýkoli backend jen práce navíc.