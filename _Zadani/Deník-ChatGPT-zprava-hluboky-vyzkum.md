# Evidence hradů a zámků v ČR jako osobní „deník dobrodruha“

## Hlavní závěr výzkumu

Ten nápad je podle mě **velmi dobře realizovatelný** a není potřeba ručně zakládat stovky položek. Existuje několik zdrojů, ze kterých lze sestavit poměrně kvalitní výchozí databázi, a část z nich nabízí přímo strukturovaná otevřená data. Největší chyba by podle mě byla postavit import pouze na webu Národního památkového ústavu nebo pouze na Wikipedii.

Doporučil bych vytvořit **vlastní centrální katalog míst**, který bude vznikat sloučením několika zdrojů. Každé místo dostane vlastní interní ID a současně si ponechá identifikátory z Wikidata, Památkového katalogu, OpenStreetMap apod. Tím se později dají data aktualizovat bez ztráty vlastních poznámek.

Základ bych stavěl takto:

**Wikidata → Památkový katalog NPÚ → seznam objektů NPÚ → Wikimedia Commons → RÚIAN → případně OpenStreetMap → ruční kontrola.**

Jako hlavní zdroj seznamu bych **nepoužíval Hrady.cz**, přestože je obsahově téměř přesně tím, co hledáš. Jejich podmínky totiž výslovně říkají, že použití textového a obrazového obsahu mimo Hrady.cz je bez písemného povolení provozovatele zakázáno. citeturn23search0turn23search1

Zásadní je také opravit předpoklad, že seznam bude v podstatě totožný se státními památkami. NPÚ aktuálně uvádí **105 jím spravovaných památek**, přičemž mezi nimi nejsou jen hrady a zámky, ale například zahrady, kostely, hospitál nebo vily. citeturn21search0turn28search3 CzechTourism naproti tomu evidoval k 31. 12. 2023 v kategorii **„Hrady a zámky“ 242 klasických turistických cílů**. To je mnohem lepší orientační představa o velikosti seznamu veřejně turisticky zajímavých objektů. citeturn24view0turn26view0

A ani číslo 242 bych nebral jako konečný počet. CzechTourism má konkrétní pravidla, co považuje za turistický cíl, a například **tvrze řadí do jiné tematické kategorie**. Pokud do projektu zahrneme také volně přístupné zříceniny, tvrze, objekty otevřené pouze příležitostně a podobná „dobrodružná“ místa, bude výsledná databáze pravděpodobně větší. To je inference z metodiky CzechTourism a dalších katalogů, nikoliv oficiální počet. citeturn24view0turn25view0turn23search0

**Moje doporučení:** už od začátku nebudovat „seznam navštívitelných zámků“, ale **obecný katalog historických sídel se stavem přístupnosti**. Potom si švagrová jednoduše zapne filtr „kam se můžu vydat“.

## Nejlepší oficiální české zdroje

### Národní památkový ústav – seznam spravovaných památek

NPÚ má veřejnou stránku **„Hrady, zámky a jiné památky“**, která aktuálně obsahuje 105 objektů a umožňuje filtrovat podle typu památky a kraje. U položek je název, fotografie, typ objektu, kraj a u většiny odkaz na vstupenky. Jednotlivý objekt může mít více typů, například Bečov nad Teplou je veden jako zámek i hrad. citeturn21search0

Pro tvůj projekt je ale ještě zajímavější struktura jednotlivých webů NPÚ. Jsou do značné míry standardizované. Například oficiální stránky Bečova obsahují adresu, telefon a e-mail a dále oddíly pro prohlídkové okruhy, návštěvní dobu, rezervaci, vstupné, dopravu a parkování. citeturn28search1turn28search5 Karlštejn používá prakticky stejnou strukturu a navíc přímo uvádí okres Beroun. citeturn28search6turn28search14

To znamená, že pro objekty NPÚ lze potenciálně automaticky získávat například:

| Informace | Dostupnost na NPÚ |
|---|---:|
| Název | ano |
| Typ hrad/zámek/ostatní | ano |
| Kraj | ano |
| Adresa | ano |
| Okres | často ano |
| Oficiální web | ano |
| Fotografie | ano |
| Popis/historie | ano |
| Prohlídkové okruhy | ano |
| Otevírací doba | ano |
| Vstupné | ano |
| Rezervace/vstupenky | ano |
| Parkování/doprava | často ano |
| Bezbariérovost | podle objektu |
| Psi/zvířata | podle objektu |
| Vhodnost pro děti | podle objektu |
| Občerstvení | podle objektu |
| Akce | ano |

NPÚ bych proto používal jako **autoritativní zdroj návštěvnických informací pro objekty, které spravuje**, nikoliv jako kompletní katalog českých hradů a zámků. NPÚ sám uvádí, že spravuje více než sto státních památkových objektů různých druhů. citeturn28search3turn28search7

Je zde ale důležitý licenční háček. Není-li uvedeno jinak, texty a fotografie webů NPÚ jsou pod licencí **CC BY-NC-ND 3.0 CZ**: je nutné uvést autora/zdroj, obsah nelze používat komerčně a licence obsahuje podmínku „No Derivatives“, tedy zákaz zásahu do díla. NPÚ zároveň požaduje uvedení svého webu a textu „zdroj: Národní památkový ústav“. citeturn28search0turn28search4

Proto bych **nestahoval kompletní články NPÚ do databáze jako hlavní popisy a nenechal AI tyto texty automaticky přepisovat**. Pro dlouhodobě čisté řešení bych z NPÚ ukládal především strukturovaná fakta, oficiální URL a návštěvnické údaje. U textového popisu je bezpečnější mít vlastní popis nebo otevřenější zdroj.

### Památkový katalog a ÚSKP

Druhý zásadní zdroj je **Památkový katalog Národního památkového ústavu a jeho otevřená data ÚSKP**. To je z hlediska evidence mnohem důležitější zdroj než běžné stránky jednotlivých zámků.

NPÚ zveřejňuje otevřené datové sady kulturních památek a národních kulturních památek a registruje je také v Národním katalogu otevřených dat. Dataset kulturních památek představuje aktuální seznam památek vedených v Ústředním seznamu kulturních památek. citeturn21search1turn21search2turn21search6

Záznamy Památkového katalogu obsahují identifikátor objektu a lokalizační informace. U jednotlivých památek lze nalézt například kraj, okres, obec, ORP, část obce a katastrální území. citeturn0search13turn0search7 Otevřená datová sada kulturních památek obsahuje identifikátory, názvy, anotace a lokalizaci a je publikována ve strojově zpracovatelných formátech, mimo jiné CSV. citeturn0search29turn21search4

Ještě zajímavější jsou prostorová otevřená data NPÚ, kde existují bodové a polygonové identifikace nemovitých kulturních památek. To může být velmi dobrý zdroj pro kontrolu geografického umístění objektu. citeturn0search26

**Památkový katalog bych použil jako úřední referenci památky**, například:

`pamatkovy_katalog_id`

`uskp_id`

`heritage_status`

`region`

`district`

`municipality`

`cadastral_area`

`official_annotation`

`source_url`

Nevýhoda je, že ÚSKP je obecný seznam kulturních památek, nikoliv hotový seznam „všech hradů a zámků“. Proto je nutné jeho objekty napárovat na Wikidata, případně na další seznamy.

### RÚIAN pro kraje, okresy, obce a adresy

Pro územní členění bych **určitě nevytvářel vlastní číselník okresů a krajů ručně**. Český úřad zeměměřický a katastrální zveřejňuje RÚIAN přes Veřejný dálkový přístup zdarma a bez registrace. citeturn27search0turn27search8

RÚIAN obsahuje vazby mezi územními prvky a oficiální adresní data. Celostátní data adresních míst jsou dostupná také jako CSV a jsou poskytována jako otevřená data pod CC BY 4.0. citeturn27search4turn27search9

U adresního místa jsou například kódy a názvy obce, části obce, ulice, číslo domu, PSČ a definiční souřadnice v S-JTSK. citeturn27search3turn27search7 RÚIAN zároveň poskytuje územní vrstvy krajů, okresů, ORP, obcí a dalších územních prvků. citeturn27search22

Pro první verzi aplikace bych ovšem RÚIAN nepoužíval při každém importu. Stačí ho využít jako **normalizační a kontrolní vrstvu**:

> souřadnice objektu → obec → okres → kraj → příslušné RÚIAN kódy.

Tím nebude problém, když jeden zdroj napíše například „Praha-východ“, jiný „okres Praha-východ“ a třetí poskytne jen obec.

## Otevřené zdroje pro kompletní seznam, fotografie a mapu

### Wikidata je podle mě nejlepší technický základ

Kdybych měl zvolit **jeden zdroj, kterým první import začne**, zvolil bych Wikidata.

Důvod není v tom, že by Wikidata byla autoritativnější než NPÚ. Není. Výhodou je **struktura, obrovské množství propojení a velmi příznivá licence**.

Wikidata přímo ukazují ukázkový SPARQL dotaz „Map of Czech castles“. Dotaz vybírá české hrady, jejich souřadnice, obrázek a architektonický styl a zobrazí je na mapě. citeturn22search0

Například už samotný princip ukázkového dotazu pracuje s:

```text
instance of / subclass of
country
coordinate location
image
architectural style
```

Wikidata ale mohou pro konkrétní objekt obsahovat mnohem více vlastností, například oficiální web, identifikátory památkových registrů, vazbu na českou Wikipedii, správní území a další údaje. Dostupnost jednotlivých vlastností se samozřejmě objekt od objektu liší. citeturn22search10turn2search9

Nejdůležitější je licence: **strukturovaná data Wikidata jsou CC0**, tedy prakticky nejjednodušší možný základ pro vlastní databázi. Wikidata navíc umožňují programový přístup a poskytují i databázové dumpy určené mimo jiné pro offline použití. citeturn22search1turn22search16

Proto bych interně u každého místa povinně uchovával třeba:

```text
wikidata_id = Q...
```

To je mimořádně užitečné při slučování zdrojů:

```text
Wikidata QID
      ↓
Wikipedia
      ↓
Wikimedia Commons
      ↓
OpenStreetMap
      ↓
Památkový katalog
```

Mnoho systémů se tak dá propojit bez fuzzy porovnávání názvu „Hrad X“ versus „Státní hrad X“.

**Pozor:** ukázkový Wikidata dotaz pouze na jeden obecný typ hradu by nestačil. Pro náš projekt bude nutné sestavit širší dotaz pro hrady, zámky/châteaux, zříceniny, hradozámky a podle rozhodnutí také tvrze. Samotný Wikidata výsledek následně doplníme dalšími seznamy.

### Wikipedia jako zdroj seznamů a textů

Česká Wikipedie obsahuje velmi rozsáhlé stránky **„Seznam hradů, tvrzí a zřícenin v Česku“** a **„Seznam zámků v Česku“**. citeturn14search0turn14search2

Kromě toho existují kategorie podle jednotlivých okresů a krajů. Kategorie českých zámků je členěna mimo jiné podle krajů a okresů a podobná struktura existuje pro hrady. citeturn14search1turn14search3 Existují také samostatné seznamy zámků a hradů podle krajů. citeturn14search4turn14search10

To je výborný **kontrolní zdroj completeness**: po vytvoření databáze lze automaticky porovnat, co Wikipedia zná a naše databáze nikoliv.

Wikipedia ale není tak licenčně jednoduchá jako Wikidata. Text je poskytován pod licencí **CC BY-SA 4.0**, takže při jeho přebírání je potřeba řešit atribuci a podmínku ShareAlike. citeturn2search3

Proto bych pro MVP doporučil:

**Krátký základní popis:** Wikidata / vlastní text.

**Dlouhý článek:** neukládat, pouze tlačítko „Wikipedia“.

**Později:** můžeme přidat licenčně správně zpracované převzetí či shrnutí, pokud bude vůbec potřeba.

Upřímně si myslím, že v deníku hradů není deset odstavců historie zásadní. Daleko cennější bude krátká anotace typu:

> Gotický hrad ze 14. století, později upravovaný. Zachovalý areál s několika prohlídkovými okruhy.

a tlačítka **Oficiální web / Wikipedia / Památkový katalog**.

### Wikimedia Commons pro fotografie

Pro automatické fotografie bych jako první volbu použil **Wikimedia Commons**.

Wikimedia Commons umožňuje další použití otevřeně licencovaných médií, ale licence se posuzuje **u každého konkrétního souboru**. Některé vyžadují uvedení autora, některé uvedení licence a u některých platí ShareAlike. citeturn22search2turn22search8turn22search14

Proto databáze fotografie nesmí obsahovat jen:

```text
image.jpg
```

ale měla by mít například:

```text
image_id
place_id
image_type          imported / user
source              Wikimedia Commons
source_page
original_url
thumbnail_url
author
license
license_url
attribution
downloaded_at
```

To nám jednou umožní zobrazit například:

> Foto: Jan Novák / Wikimedia Commons / CC BY-SA 4.0

bez ručního doplňování.

Wikidata vlastnost „image“ je výborný způsob, jak pro místo najít výchozí fotografii na Commons. Ukázkový dotaz českých hradů s touto vazbou už přímo pracuje. citeturn22search0

### OpenStreetMap jako doplňkový katalog

OpenStreetMap je zajímavý především jako **kontrolní a doplňkový zdroj pro geografii a přístupnost**.

Pro hrady používá OSM například `historic=castle`, který zahrnuje různé druhy hradních a zámeckých objektů a lze jej dále upřesňovat pomocí `castle_type=*`. citeturn21search3

K objektu mohou být přiřazeny také tagy například:

```text
wikidata
wikipedia
access
fee
opening_hours
tourism
heritage
ruins
```

OSM výslovně používá `access=*` a `fee=*` pro informace o přístupu a placení a umožňuje evidovat také provozní dobu. citeturn21search11turn21search14

Data není potřeba „scrapovat“ z mapy. Pro výběrové dotazy existuje **Overpass API**, které je přímo určeno pro získávání objektů podle polohy, typu a tagů. citeturn29search2turn29search6

Například koncepčně:

```text
ČR
  AND historic=castle
```

a následně získat všechny odpovídající objekty, jejich souřadnice a tagy.

OSM je ale pod licencí **ODbL**, která obsahuje atribuci a ShareAlike podmínky pro databáze. Pokud by se aplikace později veřejně distribuovala i s databází odvozenou z OSM, bylo by potřeba licenční dopady posoudit podrobněji. citeturn29search0turn29search3turn29search22

Pro osobní projekt bych ho proto použil jako **sekundární enrichment**, nikoliv jako hlavní databázi.

A ještě jedna důležitá věc pro PWA: hlavní veřejný server mapových dlaždic OpenStreetMap výslovně **zakazuje hromadné stahování a vytváření offline mapových archivů**. Není tedy dobrý nápad „stáhnout si celou ČR z openstreetmap.org do telefonu“. citeturn29search1turn29search5

## Zdroje, které jsou výborné ke kontrole, ale ne k automatickému importu

### Hrady.cz

Obsahově je Hrady.cz skoro neuvěřitelně blízko tomu, co chceš vybudovat.

Jejich vlastní pravidla pro založení objektu požadují:

- označení a název,
- typ,
- stav,
- přístupnost,
- stát,
- v ČR kraj, okres a obec nebo část obce,
- GPS souřadnice,
- textové informace,
- zdroje,
- fotografie. citeturn23search0

To je mimochodem silné potvrzení, že tvůj návrh datového modelu dává smysl.

Ale **Hrady.cz bych nescrapoval**. Jejich copyright stránka výslovně uvádí, že textové i obrazové materiály jsou chráněné a není-li uvedeno jinak, použití mimo server je podmíněno písemným povolením provozovatele. citeturn23search1

Použití tedy:

> „Máme všechny objekty, které zná Hrady.cz?“

ano, jako ruční kontrola.

> „Stáhneme z Hrady.cz jejich seznam, popisy a fotky?“

**Ne.**

Jediná rozumná cesta k automatickému využití jejich databáze by byla požádat provozovatele o povolení nebo datový export s jasnými podmínkami.

### CzechTourism / Tourdata

CzechTourism je mimořádně zajímavý zdroj zejména pro otázku **„co je reálně turisticky navštívitelné“**.

Jeho metodika definuje typy turistických cílů včetně:

- Hrad,
- Zámek,
- Zřícenina hradu,
- Tvrz,

a tematická kategorie „hrady a zámky“ zahrnuje hrady, zámky a zříceniny hradů. Tvrze jsou podle této metodiky řazeny mezi vojenské turistické cíle. citeturn24view0turn25view0

Jejich centrální databáze je datově velmi podobná tomu, co potřebujeme. Metodika uvádí mimo jiné:

| Pole CzechTourism |
|---|
| ID |
| Název |
| Typ |
| Kategorie |
| Kraj |
| Místo |
| Okres |
| DMO |
| Provozovatel |
| Zeměpisná šířka |
| Zeměpisná délka |
| Průměrná cena vstupenky |
| Denní kapacita |
| Statistiky návštěvnosti |
| Zdroj údajů |

Tyto sloupce jsou popsány přímo v metodice. citeturn24view0

A právě odsud pochází velmi zajímavá statistika: k 31. 12. 2023 obsahovala centrální databáze **1 417 klasických turistických cílů**, z nichž **242 patřilo do kategorie Hrady a zámky**. citeturn24view0turn26view0

![Tabulka CzechTourism ukazující 242 turistických cílů v kategorii Hrady a zámky](turn26view0)

Z metodiky ale nevyplývá, že by celá centrální pracovní databáze byla poskytována veřejnosti jako volně stažitelný dataset. Naopak metodika popisuje sběr dat prostřednictvím DMO a uvádí, že poskytované údaje jsou sdíleny v centrální databázi pro účely vyhodnocování návštěvnosti a tvorby infografik. citeturn24view0turn25view1

Proto bych CzechTourism považoval za:

**výborný seznam pro kontrolu veřejně navštěvovaných míst a jejich významnosti, ale zatím ne za jistý automatický importní zdroj.**

Za pokus by podle mě rozhodně stálo CzechTourism později oslovit a zeptat se, zda mohou poskytnout export základního seznamu turistických cílů bez údajů o návštěvnosti.

Jejich současné reporty mimochodem potvrzují, že databáze zahrnuje nejen objekty NPÚ, ale i jiné provozovatele; například v reportech figuruje zámek Loučeň nebo Dětenice vedle státních objektů. citeturn23search4

## Jak bych sestavil výchozí databázi

Tady bych postupoval jinak než klasickým „napíšeme scraper a stáhneme web“.

### Vytvořit nejprve „vesmír míst“

První import by vytvořil kandidátní množinu ze čtyř nezávislých zdrojů:

```text
Wikidata
        +
Wikipedia seznamy
        +
Památkový katalog
        +
NPÚ seznam památek
        +
OSM jako doplňková kontrola
        ↓
DEDUPlIKACE
        ↓
MASTER PLACE DATABASE
```

Wikidata poskytují strukturovanou základnu s CC0, Wikipedia poskytuje velmi rozsáhlé seznamy, Památkový katalog oficiální českou památkovou evidenci a NPÚ své aktuálně spravované objekty. citeturn22search0turn22search1turn14search0turn14search2turn21search1turn21search0

### Neslučovat podle názvu

Tohle je velmi důležité.

**„Karlštejn“ není spolehlivý primární klíč.**

Místo může být v různých zdrojích například:

```text
Karlštejn
Hrad Karlštejn
Státní hrad Karlštejn
Karlštejn Castle
```

Proto bych pároval především podle:

```text
Wikidata QID
Památkový katalog ID
OSM wikidata tag
GPS vzdálenosti
normalizovaný název + obec
```

Až poslední možnost by bylo fuzzy porovnání názvů.

### Zavést prioritu zdrojů podle typu údaje

Nesnažil bych se rozhodnout, který web je „nejlepší“. Každý je nejlepší na něco jiného.

Navrhuji toto pořadí:

| Informace | Preferovaný zdroj |
|---|---|
| Památkový status | Památkový katalog NPÚ |
| Úřední lokalita | Památkový katalog / RÚIAN |
| Souřadnice | Památkový katalog → Wikidata → OSM |
| Typ objektu | Wikidata + Památkový katalog + ruční korekce |
| Oficiální web | Wikidata / provozovatel |
| Aktuální návštěvní doba | oficiální web provozovatele |
| Vstupné | oficiální web provozovatele |
| Přístupnost | oficiální web → OSM |
| Krátký obecný popis | vlastní / Wikidata |
| Rozsáhlejší historie | odkaz Wikipedia / oficiální web |
| Hlavní fotografie | Wikimedia Commons |
| Okres/kraj/obec | RÚIAN |
| Popularita | CzechTourism |
| Uživatelské zkušenosti | naše vlastní data |

Tohle bude zásadní také pro automatické aktualizace. **Nikdy bych nedovolil, aby nový import přepsal uživatelské poznámky.**

### „Navštívitelné“ nemá být boolean

Pole:

```text
is_visitable = true/false
```

by podle mě bylo příliš primitivní.

Navrhuji stav:

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

Dává to mnohem větší smysl. Typickým „dobrodružným cílem“ totiž může být i zřícenina bez pokladny, kam se dá kdykoliv dojít.

Vedle toho může být:

```text
interior_access
grounds_access
fee_required
guided_tour
reservation_available
opening_hours_url
visitability_checked_at
```

Dynamické údaje, jako návštěvní doba a vstupné, bych **nepovažoval za permanentní databázová fakta**. Ukládal bych i datum poslední kontroly a přímý odkaz na oficiální stránku. Weby NPÚ například poskytují samostatné aktuální sekce pro návštěvní dobu a vstupné. citeturn28search1turn28search22

### První import bych rozdělil na automatický a kontrolní

Výsledek by například mohl vypadat:

```text
Imported automatically      327
High confidence              241
Needs review                  64
Potential duplicates          18
Missing coordinates            4
Missing category               7
```

Čísla výše jsou pouze ilustrace mechanismu, nikoliv výsledek současného průzkumu.

Každá položka by měla stav kvality:

```text
VERIFIED
PROBABLE
NEEDS_REVIEW
REJECTED
```

To podle mě výrazně zjednoduší první naplnění databáze. Cursor může později vytvořit administraci „Vyřešit nejasnosti“, kde bude například:

> Wikidata: Zámek Nová Ves  
> Památkový katalog: Areál zámku Nová Ves  
> GPS rozdíl: 32 metrů  
>  
> [Sloučit] [Nejsou stejné]

To je mnohem bezpečnější než se snažit první import udělat dokonale.

## Datový model pro „deník dobrodruha“

Tady bych oproti původní představě udělal jednu zásadní změnu:

**návštěva nesmí být sloupec na místě.**

Hrad může člověk navštívit:

- několikrát,
- v různých letech,
- s různými lidmi,
- pokaždé s jinými fotografiemi a zkušeností.

Proto je potřeba oddělit **místo** a **návštěvu**.

### Place – samotné místo

Konceptuálně:

```text
Place
 ├─ id
 ├─ name
 ├─ alternative_names
 ├─ type
 ├─ condition
 ├─ visitability
 │
 ├─ latitude
 ├─ longitude
 ├─ address
 ├─ municipality
 ├─ district
 ├─ region
 │
 ├─ short_description
 ├─ official_website
 ├─ wikipedia_url
 │
 ├─ heritage_status
 ├─ opening_hours_url
 ├─ ticket_url
 │
 ├─ wikidata_id
 ├─ pamatkovy_katalog_id
 ├─ osm_id
 │
 ├─ favorite
 ├─ want_to_visit
 └─ notes
```

Typ objektu bych od počátku udělal rozšiřitelný například na:

```text
HRAD
ZAMEK
HRADOZAMEK
ZRICENINA
TVRZ
LETOHRADEK
PALAC
JINE
```

Kombinované typy jsou reálné i na NPÚ – například Bečov je klasifikován jako hrad i zámek. citeturn21search0 Proto by možná bylo ještě lepší `PlaceType` řešit jako vazbu M:N místo jednoho enumu.

### Visit – návštěva

```text
Visit
 ├─ id
 ├─ place_id
 ├─ visited_at
 ├─ arrived_at
 ├─ left_at
 ├─ rating
 ├─ experience_text
 ├─ private_note
 ├─ created_at
 ├─ updated_at
 ├─ device_id
 └─ sync_state
```

Pak může Karlštejn obsahovat:

```text
Karlštejn

12. 5. 2019
s Petrem a Janou
★★★★☆

18. 7. 2024
s dětmi
★★★★★

3. 9. 2028
...
```

### Person a účastníci

Pole „kdo tam byl“ bych nedělal textově:

```text
kdo = "Petr, Jana, děti"
```

ale:

```text
Person
 ├ Petr
 ├ Jana
 ├ Anička
 └ Eliška
```

a vazbou:

```text
VisitPerson
 visit_id
 person_id
```

Pak aplikace umí bez jakéhokoliv složitého programování:

> Hrady, kde byla Jana  
> Hrady, kde byly děti  
> Kolik zámků navštívil Petr  
> Společné výlety celé rodiny

### Fotografie

Doporučuji **dva odlišné typy fotografií**.

```text
PlacePhoto
```

je ilustrační fotka objektu z Commons apod.

```text
VisitPhoto
```

je naše vlastní fotografie konkrétní návštěvy.

To pak umožní detail:

```text
Karlštejn
[oficiální / ilustrační foto]

Historie...
Mapa...
Návštěvnost...

MOJE NÁVŠTĚVY

18. 7. 2024
★★★★★
Byli: Petr, Jana, Anička

[moje foto] [moje foto] [moje foto]

"Dětem se nejvíc líbila..."
```

### Zdroj dat musí být součástí modelu

To považuji za jednu z nejdůležitějších věcí, které bych doplnil oproti původnímu zadání.

Nestačí:

```text
description = "..."
```

Potřebujeme vědět:

```text
hodnota
zdroj
kdy načteno
pod jakou licencí
jaké ID má položka u zdroje
```

Například:

```text
PlaceSource
 ├─ place_id
 ├─ source_type
 ├─ external_id
 ├─ source_url
 ├─ fetched_at
 ├─ license
 └─ raw_data
```

Pak při aktualizaci víme:

```text
Karlštejn
 Wikidata       Q...
 Památkový kat. 1000...
 NPÚ            hrad-karlstejn
 OSM            relation/...
 Wikipedia      Karlštejn_(hrad)
```

To je přesně to, co umožní databázi za několik let aktualizovat, místo aby se první import stal jednorázovým neudržovatelným skriptem.

## PWA, offline telefon a synchronizace

Tvoje představa je technicky **zcela reálná** a podle mě PWA dává pro tento projekt větší smysl než samostatná Android/iOS aplikace.

PWA může prostřednictvím Service Workeru ukládat potřebné prostředky do cache a fungovat offline. Service Worker funguje jako prostředník síťových požadavků a umožňuje vrátit lokálně uložený obsah místo komunikace se serverem. Pro nasazení na telefonu potřebuje zabezpečený HTTPS kontext; výjimkou je lokální vývoj na `localhost`. citeturn20search2turn20search4

Pro samotná data bych použil **IndexedDB**. Ta je určena pro větší objemy strukturovaných dat a umí ukládat i soubory/bloby, tedy například vlastní fotografie pořízené při návštěvě. Funguje nezávisle na aktuální dostupnosti sítě. citeturn20search7turn20search13

Koncepčně tedy:

```text
                    PC / SERVER
                ┌─────────────────┐
                │ hlavní databáze │
                │                 │
                │ Places          │
                │ Visits          │
                │ People          │
                │ Photos          │
                └────────┬────────┘
                         │
                       REST API
                         │
                         ↓
               ┌──────────────────┐
               │       PWA        │
               │                  │
               │ IndexedDB        │
               │                  │
               │ seznam míst      │
               │ moje návštěvy    │
               │ změny k syncu    │
               │ vlastní fotky    │
               └──────────────────┘
```

Telefon si stáhne například celý katalog míst:

```text
300–1000 míst
název
typ
souřadnice
kraj
okres
krátký popis
malý thumbnail
stav navštíveno
```

Takový katalog je pro dnešní telefon zanedbatelně malý. Velký objem začnou tvořit až fotografie.

### Co bude fungovat bez internetu

Bez internetu bych požadoval:

```text
✓ otevřít aplikaci
✓ hledat místo
✓ filtrovat
✓ zobrazit detail
✓ zobrazit uložený krátký popis
✓ označit návštěvu
✓ napsat poznámku
✓ zvolit účastníky
✓ ohodnotit místo
✓ přidat vlastní fotografii
✓ uložit vše lokálně
```

Po opětovném připojení:

```text
PENDING
   ↓
SYNC
   ↓
SERVER
   ↓
SYNCED
```

### Nespoléhal bych na automatický Background Sync

Prohlížeče mají Background Synchronization API, ale MDN ho stále označuje jako **Limited availability** – nefunguje ve všech hlavních prohlížečích. Totéž platí pro periodický background sync. citeturn20search3turn20search6turn20search22

Proto bych aplikaci navrhl tak, že:

> automatická synchronizace je bonus,

ale hlavní spolehlivý mechanismus je:

**tlačítko „Synchronizovat“ + automatický pokus při otevření aplikace, pokud existuje spojení.**

To je pro osobní deník podle mě ideální.

### Ještě bych omezil mobilní editaci

Na telefonu podle mě **není potřeba editovat kompletní databázi hradů**.

Mobil bych primárně nechal dělat:

```text
prohlížení katalogu
hledání
filtry
mapa
wishlist
oblíbené
zápis návštěvy
poznámka
hodnocení
účastníci
vlastní fotografie
```

Administraci:

```text
úprava zdrojových dat
slučování duplicit
import
aktualizace
správa kategorií
kontrola importu
```

bych nechal PC.

To dramaticky zjednoduší synchronizaci. Telefon totiž prakticky jen **přidává nové návštěvy**, místo aby oba systémy současně měnily stejný záznam místa.

### Offline mapa není v první verzi nutná

Zde bych byl poměrně kategorický: **do MVP bych offline mapu celé ČR nedělal**.

OpenStreetMap sice umožňuje využití svých dat pod ODbL, ale veřejné servery OSM dlaždic zakazují předem stahovat mapové dlaždice pro offline použití. citeturn29search0turn29search1

V první verzi stačí:

```text
ONLINE
→ normální interaktivní mapa

OFFLINE
→ seznam + vzdálenost + souřadnice
→ případně jednoduchá lokální vizualizace bodů
```

Později lze vybrat poskytovatele mapových podkladů, který výslovně podporuje offline balíčky, nebo vytvořit vlastní vektorový balíček. Ale kvůli osobnímu deníku bych tím první verzi vůbec nezdržoval.

## Doporučený výsledný koncept a další funkce

Ve výsledku bych aplikaci už ani nenazýval „evidence hradů“. Udělal bych z ní **osobní katalog dobrodružných míst**, jen první kolekcí budou hrady a zámky.

Datový model by proto neměl být natvrdo svázaný pouze s hrady. Později totiž skoro jistě přijde:

```text
Hrady
Zámky
Zříceniny
Tvrze
Rozhledny
Technické památky
Jeskyně
Kláštery
Vojenské pevnosti
Zajímavá místa
```

CzechTourism ostatně pracuje s více než stovkou podrobných typů turistických cílů, takže obecnější model má dlouhodobě smysl. citeturn24view0

Pro první verzi bych však **scope držel jen na hradech, zámcích, hradozámcích, zříceninách a tvrzích**.

### Funkce, které bych přidal rovnou

Za velmi užitečné považuji stav:

```text
○ Nenavštíveno
♡ Chci navštívit
✓ Navštíveno
★ Oblíbené
```

Dále:

```text
počet návštěv
datum poslední návštěvy
moje hodnocení
s kým jsem tam byl
počet vlastních fotografií
```

Pak seznam může vypadat třeba:

```text
☐ Karlštejn             Beroun       58 km
✓ Křivoklát             Rakovník     74 km
♡ Točník                Beroun       62 km
☐ Žebrák                Beroun       61 km
★ Český Šternberk       Benešov      89 km
```

### Herní prvek bych tam určitě dal

Nemusí to být nic složitého, ale přesně k tomuto projektu se hodí:

```text
Navštíveno 38 / 274 míst
████████░░░░░░░░  13,9 %

Kraje
✓ Plzeňský          14 / 31
✓ Jihočeský          8 / 42
  Vysočina           6 / 27
```

a odznaky například:

```text
🏰 Prvních 10 hradů
🏰 25 hradů
👑 25 zámků
🧱 10 zřícenin
🗺 všechny kraje
⭐ 100 míst
```

To z obyčejné evidence udělá skutečný **seznam dobrodružství**.

### Velmi užitečný bude filtr „co je poblíž“

Protože budeme mít souřadnice, lze jednoduše udělat:

> **Co ještě nemám navštíveno do 30 km?**

Například:

```text
Okolí mé polohy

12 km  Hrad X        Nenavštíveno
18 km  Zámek Y       Chci navštívit
24 km  Zřícenina Z   Nenavštíveno
29 km  Tvrz A        Navštíveno
```

Právě tady se z databáze stane praktická aplikace na výlety, nikoliv jen archiv.

### Možnost sestavit výlet

Později bych přidal entitu `Trip`:

```text
Výlet: Český ráj
12. 7. 2027

1. Trosky
2. Hrubá Skála
3. Valdštejn
4. Sychrov
```

A po výletu se jednotlivá místa promění v návštěvy.

### Import fotografií z telefonu podle GPS a času

Tohle bych označil jako výbornou funkci pro některou další verzi.

Fotografie z telefonu mohou mít EXIF datum a GPS. Aplikace by tedy mohla při importu nabídnout:

```text
IMG_4821.JPG
18. 7. 2026 14:32
GPS: 49.939...

Nejbližší místo:
Hrad Karlštejn – 84 metrů

[Přiřadit k návštěvě Karlštejna]
```

To by cestovatelský deník výrazně zpříjemnilo.

### Připravenost na další zdroje

Architekturu importu bych udělal jako samostatné konektory:

```text
/importers
    wikidata
    pamatkovy-katalog
    npu
    wikimedia
    ruian
    openstreetmap
```

Každý importer vrátí standardizovaná data:

```json
{
  "externalId": "...",
  "name": "...",
  "coordinates": {
    "latitude": 0,
    "longitude": 0
  },
  "source": "...",
  "fetchedAt": "..."
}
```

Tím nebude aplikace závislá na jednom webu.

### Doporučená priorita realizace

Za mě by měl první skutečný vývoj následovat tento rozsah:

**Jádro MVP**

```text
Databáze míst
↓
automatický počáteční import
↓
deduplikace
↓
seznam + filtr + vyhledávání
↓
detail místa
↓
mapa
↓
Chci navštívit / Navštíveno
↓
návštěvy + osoby + poznámky
↓
vlastní fotografie
↓
PWA offline
↓
synchronizace
```

Až potom:

```text
automatická návštěvní doba
ceny
prohlídkové okruhy
statistiky návštěvnosti
plánování tras
EXIF
gamifikace
automatické aktualizace externích dat
```

Tohle pořadí podle mě výrazně sníží riziko, že se projekt utopí v importech a scraperech ještě dřív, než bude možné zapsat první návštěvu.

## Verdikt a podklad pro budoucí zadání Cursoru

Po výzkumu bych zdroje ohodnotil takto:

| Zdroj | Soupis míst | Souřadnice | Popis | Fotky | Návštěvnost / otevření | Hromadný import | Moje doporučení |
|---|---:|---:|---:|---:|---:|---:|---|
| **Wikidata** | ★★★★★ | ★★★★★ | ★★★ | ★★★★ | ★ | ★★★★★ | **hlavní importní páteř** |
| **Památkový katalog NPÚ** | ★★★★★ | ★★★★ | ★★★ | ★★ | ★ | ★★★★★ | **oficiální identifikace** |
| **NPÚ seznam + weby objektů** | ★★★ | ★★★ | ★★★★ | ★★★★ | ★★★★★ | ★★★ | **státní objekty a návštěvní info** |
| **Wikimedia Commons** | — | — | — | ★★★★★ | — | ★★★★★ | **hlavní fotografie** |
| **Wikipedia** | ★★★★★ | ★★★★ | ★★★★★ | ★★★★ | ★ | ★★★★ | **kontrola seznamu + historie** |
| **RÚIAN** | — | ★★★★★ | — | — | — | ★★★★★ | **obec/okres/kraj/adresy** |
| **OpenStreetMap** | ★★★★ | ★★★★★ | ★ | — | ★★★ | ★★★★★ | **doplňková kontrola** |
| **CzechTourism/Tourdata** | ★★★★ | ★★★★ | — | — | ★★★★★ | ? | **referenční seznam navštívitelných cílů** |
| **Hrady.cz** | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★ | **ne** | **pouze kontrola / inspirace** |

Hodnocení hvězdičkami je moje technické posouzení vhodnosti pro tento konkrétní projekt, nikoliv oficiální hodnocení jednotlivých služeb. Podkladové vlastnosti zdrojů vycházejí z jejich aktuálních dokumentací a webů. citeturn22search0turn22search1turn21search1turn21search0turn22search2turn27search0turn29search2turn24view0turn23search1

**Můj jednoznačný návrh architektury zdrojů je:**

```text
                  ┌─────────────────────┐
                  │      WIKIDATA       │
                  │ základní discovery  │
                  └──────────┬──────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ↓                  ↓                  ↓
 ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
 │ Památkový      │ │ NPÚ objekty    │ │ Wikipedia      │
 │ katalog        │ │ návštěvní info │ │ kontrola       │
 └───────┬────────┘ └───────┬────────┘ └───────┬────────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            ↓
                 ┌─────────────────────┐
                 │  NORMALIZACE +      │
                 │  DEDUPLIKACE        │
                 └──────────┬──────────┘
                            │
              ┌─────────────┼─────────────┐
              ↓             ↓             ↓
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ RÚIAN    │  │ Commons  │  │ OSM      │
        │ území    │  │ fotky    │  │ doplnění │
        └────┬─────┘  └────┬─────┘  └────┬─────┘
             └─────────────┼─────────────┘
                           ↓
                ┌─────────────────────┐
                │    PLACES DB        │
                │ vlastní master data │
                └──────────┬──────────┘
                           │
               ┌───────────┴───────────┐
               ↓                       ↓
       ┌───────────────┐       ┌───────────────┐
       │ PC aplikace   │       │ Offline PWA   │
       │ administrace  │◄─────►│ mobil         │
       └───────────────┘ sync  └───────────────┘
```

Wikidata jsou pro tuto roli vhodná díky strojovému přístupu a CC0 licenci; Památkový katalog přidá oficiální památkovou identitu, RÚIAN oficiální českou územní strukturu a Commons fotografie s evidovatelnými licencemi. citeturn22search1turn21search6turn27search8turn22search14

A **nejdůležitější architektonické rozhodnutí** podle mě je toto:

> **Externí weby nejsou naše databáze. Jsou pouze zdroje.**

Jakmile místo jednou importujeme, vznikne náš vlastní `Place`. K němu budou připojené `PlaceSource` záznamy. Vlastní návštěvy, hodnocení, poznámky a fotografie pak budou úplně oddělené od externích dat. Aktualizace Wikidata nebo NPÚ proto nikdy nemůže poškodit osobní cestovatelský deník.

PWA je pro požadované offline použití vhodná: Service Worker může zajistit offline aplikaci, IndexedDB může držet místní katalog i uživatelská data a synchronizace nemusí záviset na omezeně podporovaném Background Sync API. citeturn20search2turn20search7turn20search3

**Odhad věrohodnosti výzkumu: 96 %.** Dostupnost a charakteristiky NPÚ, Wikidata, Wikimedia Commons, RÚIAN, OSM a PWA technologií jsou přímo doložené jejich aktuálními oficiálními zdroji. citeturn28search0turn22search1turn22search14turn27search0turn29search3turn20search2 Největší zbývající nejistota není technická, ale **rozsahová**: neexistuje jeden veřejný autoritativní registr s přesnou kategorií „všechny hrady a zámky v ČR, které může turista navštívit“. CzechTourism měl k 31. 12. 2023 ve své turistické kategorii 242 takových cílů, NPÚ dnes zobrazuje 105 jím spravovaných památek a širší seznam musí vzniknout kombinací několika registrů. citeturn26view0turn21search0 Právě proto považuji vícezdrojový import s vlastní master databází za výrazně lepší řešení než scraping jediného webu.