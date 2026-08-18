"""SPARQL šablony. Typové třídy jsou rozdělené kvůli timeoutu WDQS (60 s)."""

from __future__ import annotations

# Q2288643 ze zadání je lékařská položka (přesměrování). Tvrz = fortified house.
TYPE_CLASSES: dict[str, str] = {
    "CASTLE": "Q23413",
    "CHATEAU": "Q751876",
    "RUIN": "Q109607",
    "MANOR": "Q1408475",
    "PALACE": "Q16560",
    "LOOKOUT_TOWER": "Q1440300",  # observation tower / rozhledna
    "ZOO": "Q43501",
    "CAVE": "Q35509",
}

COUNTRY_QID = "Q213"  # Česko
EXISTING_QIDS_KEY = "EXISTING_QIDS"
CONDITION_KEY = "CONDITION"
STYLE_KEY = "STYLE"
QID_BATCH_SIZE = 40

_OPTIONAL_CLAUSES = """
  OPTIONAL { ?item wdt:P625 ?coord . }
  OPTIONAL { ?item wdt:P18 ?image . }
  OPTIONAL { ?item wdt:P856 ?web . }
  OPTIONAL { ?item wdt:P4075 ?uskp . }
  OPTIONAL { ?item wdt:P4856 ?cp . }
  OPTIONAL { ?item wdt:P131 ?cast . }
  OPTIONAL {
    ?item wdt:P131+ ?obec .
    ?obec wdt:P31/wdt:P279* wd:Q5153359 .
  }
  OPTIONAL {
    ?item wdt:P131+ ?okres .
    ?okres wdt:P31 wd:Q3389049 .
  }
  OPTIONAL {
    ?item wdt:P131+ ?kraj .
    ?kraj wdt:P31 wd:Q1615742 .
  }
  OPTIONAL {
    ?article schema:about ?item ;
             schema:isPartOf <https://cs.wikipedia.org/> .
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "cs,en" . }
""".strip()


def _qid_ok(qid: str) -> bool:
    return qid.startswith("Q") and qid[1:].isdigit()


def _select_body(where: str) -> str:
    return f"""
SELECT DISTINCT ?item ?itemLabel ?coord ?image ?web ?uskp ?article
                ?obecLabel ?okresLabel ?krajLabel ?castLabel ?cp WHERE {{
  {where}
  {_OPTIONAL_CLAUSES}
}}
""".strip()


def build_query(class_qid: str) -> str:
    """Dotaz na instance (včetně podtříd) dané třídy v Česku.

    Souřadnice jsou volitelné — místa bez GPS se importují.
    """
    if not _qid_ok(class_qid):
        raise ValueError(f"Neplatné QID třídy: {class_qid}")
    where = f"?item wdt:P31/wdt:P279* wd:{class_qid} .\n  ?item wdt:P17 wd:{COUNTRY_QID} ."
    return _select_body(where)


def build_items_query(qids: list[str]) -> str:
    """Jen P18 u už uložených QID — bez P131 hierarchie, WDQS to jinak nezvládá."""
    if not qids:
        raise ValueError("Prázdný seznam QID")
    for qid in qids:
        if not _qid_ok(qid):
            raise ValueError(f"Neplatné QID: {qid}")
    values = " ".join(f"wd:{qid}" for qid in qids)
    return f"""
SELECT ?item ?itemLabel ?image WHERE {{
  VALUES ?item {{ {values} }}
  OPTIONAL {{ ?item wdt:P18 ?image . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "cs,en" . }}
}}
""".strip()


def build_condition_query(qids: list[str]) -> str:
    """Stav objektu po dávkách — mimo typový SPARQL, ať WDQS nestihne timeout."""
    if not qids:
        raise ValueError("Prázdný seznam QID")
    for qid in qids:
        if not _qid_ok(qid):
            raise ValueError(f"Neplatné QID: {qid}")
    values = " ".join(f"wd:{qid}" for qid in qids)
    return f"""
SELECT ?item ?conservation ?dissolved ?goneClass WHERE {{
  VALUES ?item {{ {values} }}
  OPTIONAL {{ ?item wdt:P5816 ?conservation . }}
  OPTIONAL {{ ?item wdt:P576 ?dissolved . }}
  OPTIONAL {{
    ?item wdt:P31 ?goneClass .
    VALUES ?goneClass {{ wd:Q177751 wd:Q19860854 wd:Q839818 }}
  }}
}}
""".strip()


def build_style_query(qids: list[str]) -> str:
    """Rok vzniku (P571) a sloh (P149) po dávkách."""
    if not qids:
        raise ValueError("Prázdný seznam QID")
    for qid in qids:
        if not _qid_ok(qid):
            raise ValueError(f"Neplatné QID: {qid}")
    values = " ".join(f"wd:{qid}" for qid in qids)
    return f"""
SELECT ?item ?inception ?style ?styleLabel WHERE {{
  VALUES ?item {{ {values} }}
  OPTIONAL {{ ?item wdt:P571 ?inception . }}
  OPTIONAL {{ ?item wdt:P149 ?style . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "cs,en" . }}
}}
""".strip()
