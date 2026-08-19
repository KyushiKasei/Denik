import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  EMPTY_FILTERS,
  facetCounts,
  filterPlaces,
  filtersFromParams,
  PLACE_SORT_OPTIONS,
  primeHaystacks,
  uniqueSorted,
  withCount,
  type JournalFilter,
  type PlaceFilters,
  type PlaceSort,
} from "../catalog/filterPlaces";
import { loadCatalogMeta, loadPlaces, peekPlaces } from "../catalog/importCatalog";
import {
  formatTypes,
  hasGps,
  CONDITION_OPTIONS,
  HERITAGE_OPTIONS,
  locationLine,
  PLACE_TYPE_OPTIONS,
  VISITABILITY_FILTER_GROUPS,
  VISITABILITY_OPTIONS,
} from "../catalog/labels";
import type { CatalogPlace, ConditionCode, PlaceTypeCode } from "../catalog/types";
import { loadCatalogView, parseCatalogView, saveCatalogView, type CatalogView } from "../catalog/viewMode";
import { HoursBadge } from "../components/HoursBadge";
import { extraFilterCount, FilterDisclosure } from "../components/FilterDisclosure";
import { JournalChips } from "../components/JournalChips";
import { OrphanVisits } from "../components/OrphanVisits";
import { PlaceCard } from "../components/PlaceCard";
import { WorthToggle } from "../components/WorthToggle";
import { useDiaryBadges } from "../diary/useDiaryBadges";
import { appliedSearchQuery, SEARCH_DEBOUNCE_MS } from "../text/fold";
import { saveWorthFilter } from "../catalog/visitWorth";
import { MONTH_OPTIONS } from "../catalog/openingHours";
import { czechCountWord } from "../diary/timeline";

const PAGE_SIZE = 80;

function paramsFromFilters(filters: PlaceFilters, view: CatalogView = "cards"): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.query.trim()) params.set("q", filters.query.trim());
  if (filters.type) params.set("type", filters.type);
  if (filters.region) params.set("region", filters.region);
  if (filters.district) params.set("district", filters.district);
  if (filters.visitability) params.set("visitability", filters.visitability);
  if (filters.journal) params.set("journal", filters.journal);
  if (filters.unesco) params.set("unesco", filters.unesco);
  if (filters.heritage) params.set("heritage", filters.heritage);
  if (filters.condition) params.set("condition", filters.condition);
  if (filters.gps) params.set("gps", filters.gps);
  if (filters.hours) params.set("hours", filters.hours);
  if (filters.openMonth) params.set("month", String(filters.openMonth));
  if (filters.extra) params.set("extra", filters.extra);
  if (filters.lost) params.set("lost", "yes");
  if (filters.style) params.set("style", filters.style);
  if (filters.worth === false) params.set("worth", "all");
  if (filters.sort && filters.sort !== "name") params.set("sort", filters.sort);
  if (view === "list") params.set("view", "list");
  return params;
}

function filtersActive(filters: PlaceFilters): boolean {
  return Boolean(
    filters.query ||
      filters.type ||
      filters.region ||
      filters.district ||
      filters.visitability ||
      filters.journal ||
      filters.unesco ||
      filters.heritage ||
      filters.condition ||
      filters.gps ||
      filters.hours ||
      filters.openMonth ||
      filters.extra ||
      filters.lost ||
      filters.style ||
      (filters.sort && filters.sort !== "name"),
  );
}

export function CatalogPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = filtersFromParams(searchParams);
  const viewFromUrl = parseCatalogView(searchParams.get("view"));
  const [view, setView] = useState<CatalogView>(() => viewFromUrl ?? loadCatalogView());
  const [places, setPlaces] = useState<CatalogPlace[] | null>(() => peekPlaces());
  const [version, setVersion] = useState<number | null>(null);
  const [limit, setLimit] = useState(PAGE_SIZE);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [queryDraft, setQueryDraft] = useState(filters.query);
  const { visitedIds, wantIds, favIds, orphans, error: badgeError } = useDiaryBadges({ orphans: true });

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [rows, meta] = await Promise.all([loadPlaces(), loadCatalogMeta()]);
        if (!cancelled) {
          primeHaystacks(rows);
          setPlaces(rows);
          setVersion(meta.catalog_version);
        }
      } catch {
        if (!cancelled) {
          setLoadError("Katalog se nepodařilo načíst.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setLimit(PAGE_SIZE);
  }, [
    filters.query,
    filters.type,
    filters.region,
    filters.district,
    filters.visitability,
    filters.journal,
    filters.unesco,
    filters.heritage,
    filters.condition,
    filters.gps,
    filters.worth,
    filters.sort,
    filters.hours,
    filters.openMonth,
    filters.extra,
    filters.lost,
    filters.style,
  ]);

  useEffect(() => {
    setQueryDraft(filters.query);
  }, [filters.query]);

  useEffect(() => {
    if (!viewFromUrl || viewFromUrl === view) {
      return;
    }
    setView(viewFromUrl);
    saveCatalogView(viewFromUrl);
  }, [viewFromUrl, view]);

  useEffect(() => {
    const nextQuery = appliedSearchQuery(queryDraft);
    if (nextQuery === filters.query) {
      return;
    }
    const handle = window.setTimeout(() => {
      const next = { ...filtersFromParams(searchParams), query: nextQuery };
      setSearchParams(paramsFromFilters(next, view), { replace: true });
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  }, [queryDraft, filters.query, searchParams, setSearchParams, view]);

  const regions = useMemo(() => uniqueSorted((places ?? []).map((place) => place.location.region)), [places]);
  const styles = useMemo(
    () => uniqueSorted((places ?? []).map((place) => place.architectural_style)),
    [places],
  );
  const districts = useMemo(() => {
    const source = (places ?? []).filter((place) => !filters.region || place.location.region === filters.region);
    return uniqueSorted(source.map((place) => place.location.district));
  }, [places, filters.region]);

  const filtered = useMemo(
    () => filterPlaces(places ?? [], filters, { visitedIds, wantIds, favIds }),
    [places, filters, visitedIds, wantIds, favIds],
  );
  const facets = useMemo(
    () => facetCounts(places ?? [], filters, { visitedIds, wantIds, favIds }),
    [places, filters, visitedIds, wantIds, favIds],
  );
  const visible = filtered.slice(0, limit);
  const remaining = Math.min(PAGE_SIZE, filtered.length - visible.length);

  const visitedCount = useMemo(
    () => (places ?? []).filter((place) => visitedIds.has(place.id)).length,
    [places, visitedIds],
  );
  const wantCount = useMemo(() => (places ?? []).filter((place) => wantIds.has(place.id)).length, [places, wantIds]);
  const favCount = useMemo(() => (places ?? []).filter((place) => favIds.has(place.id)).length, [places, favIds]);

  const update = (patch: Partial<PlaceFilters>) => {
    const next = { ...filters, ...patch };
    if (patch.region !== undefined) {
      next.district = "";
    }
    setSearchParams(paramsFromFilters(next, view), { replace: true });
  };

  const setJournal = (journal: JournalFilter) => {
    update({ journal: filters.journal === journal ? "" : journal });
  };

  const setCatalogView = (next: CatalogView) => {
    setView(next);
    saveCatalogView(next);
    setSearchParams(paramsFromFilters(filters, next), { replace: true });
  };

  const setWorth = (worth: boolean) => {
    saveWorthFilter(worth);
    update({ worth });
  };

  if (loadError) {
    return (
      <p className="error" role="alert">
        {loadError}
      </p>
    );
  }

  if (places === null) {
    return <p className="muted">Načítám katalog…</p>;
  }

  if (places.length === 0) {
    return (
      <section className="empty-state">
        <h1>Katalog</h1>
        <p>
          Zatím tu nic není. Nahrajte <code>catalog.json</code> z PC aplikace.
        </p>
        <p>
          <Link to="/import" className="button">
            Nahrát catalog.json
          </Link>
        </p>
        <OrphanVisits groups={orphans} />
      </section>
    );
  }

  return (
    <section>
      <header className="page-header">
        <h1>Katalog</h1>
        <p className="muted">
          {filtered.length === places.length
            ? `${places.length} ${czechCountWord(places.length, "místo", "místa", "míst")}`
            : `${filtered.length} z ${places.length} ${czechCountWord(places.length, "místa", "míst", "míst")}`}
          {version != null ? ` · verze ${version}` : ""}
          {orphans.length > 0 ? ` · ${orphans.length} mimo katalog` : ""}
        </p>
        <p className="journal-counts">
          <button
            type="button"
            className={filters.journal === "visited" ? "text-link active" : "text-link"}
            onClick={() => setJournal("visited")}
          >
            {visitedCount} navštíveno
          </button>
          <button
            type="button"
            className={filters.journal === "want_to_visit" ? "text-link active" : "text-link"}
            onClick={() => setJournal("want_to_visit")}
          >
            {wantCount} chci navštívit
          </button>
          <button
            type="button"
            className={filters.journal === "favorite" ? "text-link active" : "text-link"}
            onClick={() => setJournal("favorite")}
          >
            {favCount} oblíbené
          </button>
        </p>
        {badgeError ? (
          <p className="error" role="alert">
            {badgeError}
          </p>
        ) : null}
        <div className="segmented cols-2 catalog-view-toggle" role="group" aria-label="Zobrazení katalogu">
          <button type="button" className={view === "cards" ? "active" : ""} onClick={() => setCatalogView("cards")}>
            Karty
          </button>
          <button type="button" className={view === "list" ? "active" : ""} onClick={() => setCatalogView("list")}>
            Seznam
          </button>
        </div>
      </header>

      <OrphanVisits groups={orphans} />

      <form className="filters" onSubmit={(event) => event.preventDefault()}>
        <WorthToggle
          value={filters.worth !== false}
          onChange={setWorth}
          visitCount={facets.worth.visit}
          allCount={facets.worth.all}
        />
        {filters.worth !== false ? (
          <p className="muted small">
            Bez zaniklých, zbytků a málo podložených záznamů. Zapněte Vše, nebo zaškrtněte Zaniklé a zbytky.
          </p>
        ) : null}
        <label>
          Hledat
          <input
            type="search"
            value={queryDraft}
            onChange={(event) => setQueryDraft(event.target.value)}
            placeholder="Název, obec (od 3 písmen)…"
            autoComplete="off"
          />
        </label>
        <label>
          Řazení
          <select
            value={filters.sort ?? "name"}
            onChange={(event) => update({ sort: event.target.value as PlaceSort })}
          >
            {PLACE_SORT_OPTIONS.map((item) => (
              <option key={item.code} value={item.code}>
                {item.name_cs}
              </option>
            ))}
          </select>
        </label>
        <FilterDisclosure
          count={extraFilterCount([
            filters.type,
            filters.region,
            filters.district,
            filters.visitability,
            filters.journal,
            filters.unesco,
            filters.heritage,
            filters.condition,
            filters.gps,
            filters.hours,
            Boolean(filters.openMonth),
            filters.extra,
            filters.lost,
            filters.style,
          ])}
        >
        <label>
          Typ
          <select value={filters.type} onChange={(event) => update({ type: event.target.value as PlaceTypeCode | "" })}>
            <option value="">{withCount("Všechny", facets.types[""])}</option>
            {PLACE_TYPE_OPTIONS.map((item) => (
              <option key={item.code} value={item.code}>
                {withCount(item.name_cs, facets.types[item.code])}
              </option>
            ))}
          </select>
        </label>
        <label>
          Kraj
          <select value={filters.region} onChange={(event) => update({ region: event.target.value })}>
            <option value="">{withCount("Všechny", facets.regions[""])}</option>
            {regions.map((region) => (
              <option key={region} value={region}>
                {withCount(region, facets.regions[region])}
              </option>
            ))}
          </select>
        </label>
        <label>
          Okres
          <select value={filters.district} onChange={(event) => update({ district: event.target.value })}>
            <option value="">{withCount("Všechny", facets.districts[""])}</option>
            {districts.map((district) => (
              <option key={district} value={district}>
                {withCount(district, facets.districts[district])}
              </option>
            ))}
          </select>
        </label>
        <label>
          Přístupnost
          <select
            value={filters.visitability ?? ""}
            onChange={(event) => update({ visitability: event.target.value as PlaceFilters["visitability"] })}
          >
            <option value="">{withCount("Vše", facets.visitability[""])}</option>
            {VISITABILITY_FILTER_GROUPS.map((item) => (
              <option key={item.code} value={item.code}>
                {withCount(item.name_cs, facets.visitability[item.code])}
              </option>
            ))}
            {VISITABILITY_OPTIONS.map((item) => (
              <option key={item.code} value={item.code}>
                {withCount(item.name_cs, facets.visitability[item.code])}
              </option>
            ))}
          </select>
        </label>
        <label>
          Deník
          <select value={filters.journal} onChange={(event) => update({ journal: event.target.value as PlaceFilters["journal"] })}>
            <option value="">{withCount("Vše", facets.journal[""])}</option>
            <option value="visited">{withCount("Navštíveno", facets.journal.visited)}</option>
            <option value="not_visited">{withCount("Nenavštíveno", facets.journal.not_visited)}</option>
            <option value="want_to_visit">{withCount("Chci navštívit", facets.journal.want_to_visit)}</option>
            <option value="favorite">{withCount("Oblíbené", facets.journal.favorite)}</option>
          </select>
        </label>
        <label>
          UNESCO
          <select value={filters.unesco} onChange={(event) => update({ unesco: event.target.value as PlaceFilters["unesco"] })}>
            <option value="">{withCount("Vše", facets.unesco[""])}</option>
            <option value="yes">{withCount("UNESCO", facets.unesco.yes)}</option>
            <option value="no">{withCount("Bez UNESCO", facets.unesco.no)}</option>
          </select>
        </label>
        <label>
          Ochrana
          <select value={filters.heritage} onChange={(event) => update({ heritage: event.target.value })}>
            <option value="">{withCount("Vše", facets.heritage[""])}</option>
            {HERITAGE_OPTIONS.map((item) => (
              <option key={item.code} value={item.code}>
                {withCount(item.name_cs, facets.heritage[item.code])}
              </option>
            ))}
          </select>
        </label>
        <label>
          Stav
          <select
            value={filters.condition ?? ""}
            onChange={(event) => update({ condition: event.target.value as ConditionCode | "" })}
          >
            <option value="">{withCount("Vše", facets.condition[""])}</option>
            {CONDITION_OPTIONS.map((item) => (
              <option key={item.code} value={item.code}>
                {withCount(item.name_cs, facets.condition[item.code])}
              </option>
            ))}
          </select>
        </label>
        <label>
          GPS
          <select value={filters.gps} onChange={(event) => update({ gps: event.target.value as PlaceFilters["gps"] })}>
            <option value="">{withCount("Vše", facets.gps[""])}</option>
            <option value="with">{withCount("Se souřadnicemi", facets.gps.with)}</option>
            <option value="without">{withCount("Bez GPS", facets.gps.without)}</option>
          </select>
        </label>
        <label>
          Otevírací doba
          <select value={filters.hours ?? ""} onChange={(event) => update({ hours: event.target.value as PlaceFilters["hours"] })}>
            <option value="">{withCount("Vše", facets.hours[""])}</option>
            <option value="open">{withCount("Dnes otevřeno", facets.hours.open)}</option>
            <option value="season">{withCount("Sezóna teď", facets.hours.season)}</option>
          </select>
        </label>
        <label>
          Otevřeno v měsíci
          <select
            value={filters.openMonth || ""}
            onChange={(event) =>
              update({ openMonth: event.target.value ? Number(event.target.value) : "" })
            }
          >
            <option value="">Kdykoli</option>
            {MONTH_OPTIONS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.name_cs}
              </option>
            ))}
          </select>
        </label>
        <label>
          Na výletě
          <select
            value={filters.extra ?? ""}
            onChange={(event) => update({ extra: event.target.value as PlaceFilters["extra"] })}
          >
            <option value="">{withCount("Vše", facets.extra[""])}</option>
            {facets.extra.dogs ? <option value="dogs">{withCount("Se psem", facets.extra.dogs)}</option> : null}
            {facets.extra.free ? <option value="free">{withCount("Zdarma", facets.extra.free)}</option> : null}
            {facets.extra.toilets ? <option value="toilets">{withCount("Toalety", facets.extra.toilets)}</option> : null}
            {facets.extra.cafe ? <option value="cafe">{withCount("Občerstvení", facets.extra.cafe)}</option> : null}
            {facets.extra.playground ? (
              <option value="playground">{withCount("Hřiště", facets.extra.playground)}</option>
            ) : null}
          </select>
        </label>
        {styles.length > 0 ? (
        <label>
          Sloh
          <select value={filters.style ?? ""} onChange={(event) => update({ style: event.target.value })}>
            <option value="">Všechny</option>
            {styles.map((style) => (
              <option key={style} value={style}>
                {style}
              </option>
            ))}
          </select>
        </label>
        ) : null}
        <label>
          <input
            type="checkbox"
            checked={Boolean(filters.lost)}
            onChange={(event) => update({ lost: event.target.checked })}
          />{" "}
          Zaniklé a zbytky ({facets.lost.yes})
        </label>
        </FilterDisclosure>
        {filtersActive(filters) ? (
          <button
            type="button"
            className="ghost"
            onClick={() =>
              setSearchParams(paramsFromFilters({ ...EMPTY_FILTERS, worth: filters.worth !== false }, view), {
                replace: true,
              })
            }
          >
            Zrušit filtry
          </button>
        ) : null}
      </form>

      {filtered.length === 0 ? (
        <p className="muted">Nic neodpovídá filtrům.</p>
      ) : view === "cards" ? (
        <div className="place-cards">
          {visible.map((place) => (
            <PlaceCard
              key={place.id}
              place={place}
              to={`/place/${place.id}`}
              visited={visitedIds.has(place.id)}
              want={wantIds.has(place.id)}
              favorite={favIds.has(place.id)}
            />
          ))}
        </div>
      ) : (
        <ul className="place-list">
          {visible.map((place) => (
            <li key={place.id}>
              <Link to={`/place/${place.id}`} className="place-row">
                <span className="place-row-title">{place.name}</span>
                <span className="place-row-meta">
                  {formatTypes(place.types, { hideInName: place.name })}
                  {locationLine(place) ? ` · ${locationLine(place)}` : ""}
                  {hasGps(place) ? "" : " · bez GPS"}
                  {" "}
                  <HoursBadge place={place} />
                </span>
                <JournalChips
                  visited={visitedIds.has(place.id)}
                  want={wantIds.has(place.id)}
                  favorite={favIds.has(place.id)}
                />
              </Link>
            </li>
          ))}
        </ul>
      )}

      {visible.length < filtered.length ? (
        <p>
          <button type="button" className="ghost" onClick={() => setLimit((value) => value + PAGE_SIZE)}>
            {remaining >= 5 ? "Dalších" : "Další"} {remaining}{" "}
            {czechCountWord(remaining, "místo", "místa", "míst")}
          </button>
        </p>
      ) : null}
    </section>
  );
}
