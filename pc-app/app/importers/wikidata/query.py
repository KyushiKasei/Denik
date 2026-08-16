"""SPARQL šablony. Typové třídy jsou rozdělené kvůli timeoutu WDQS (60 s)."""

from __future__ import annotations

# Q2288643 ze zadání je lékařská položka (přesměrování). Tvrz = fortified house.
TYPE_CLASSES: dict[str, str] = {
    "CASTLE": "Q23413",
    "CHATEAU": "Q751876",
    "RUIN": "Q109607",
    "MANOR": "Q1408475",
    "LOOKOUT_TOWER": "Q1440300",  # observation tower / rozhledna
    "ZOO": "Q43501",
    "CAVE": "Q35509",
}

COUNTRY_QID = "Q213"  # Česko


def build_query(class_qid: str) -> str:
    """Dotaz na instance (včetně podtříd) dané třídy v Česku.

    Souřadnice jsou volitelné — místa bez GPS se importují.
    """
    if not class_qid.startswith("Q") or not class_qid[1:].isdigit():
        raise ValueError(f"Neplatné QID třídy: {class_qid}")
    return f"""
SELECT DISTINCT ?item ?itemLabel ?coord ?image ?web ?uskp ?article
                ?obecLabel ?okresLabel ?krajLabel ?castLabel ?cp WHERE {{
  ?item wdt:P31/wdt:P279* wd:{class_qid} .
  ?item wdt:P17 wd:{COUNTRY_QID} .
  OPTIONAL {{ ?item wdt:P625 ?coord . }}
  OPTIONAL {{ ?item wdt:P18 ?image . }}
  OPTIONAL {{ ?item wdt:P856 ?web . }}
  OPTIONAL {{ ?item wdt:P4075 ?uskp . }}
  OPTIONAL {{ ?item wdt:P4856 ?cp . }}
  OPTIONAL {{ ?item wdt:P131 ?cast . }}
  OPTIONAL {{
    ?item wdt:P131+ ?obec .
    ?obec wdt:P31/wdt:P279* wd:Q5153359 .
  }}
  OPTIONAL {{
    ?item wdt:P131+ ?okres .
    ?okres wdt:P31 wd:Q3389049 .
  }}
  OPTIONAL {{
    ?item wdt:P131+ ?kraj .
    ?kraj wdt:P31 wd:Q1615742 .
  }}
  OPTIONAL {{
    ?article schema:about ?item ;
             schema:isPartOf <https://cs.wikipedia.org/> .
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "cs,en" . }}
}}
""".strip()
