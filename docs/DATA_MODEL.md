# Datový model (Fáze 1)

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
| OTHER | Jiné |

## places

Master záznam památky. `public_id` je neměnný UUIDv7. Integer `id` se do JSON nikdy nedostane.

M:N na typy přes `place_place_types`.

## app_meta

Klíč/hodnota (verze katalogu až ve fázi 6).

## Zatím není

PlaceSource, importní tabulky, Visit, PlaceJournalState — fáze 3 a 8.
