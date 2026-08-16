import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  EMPTY_FILTERS,
  facetCounts,
  filterPlaces,
  parseGpsParam,
  parseHeritageParam,
  parseJournalParam,
  parseSortParam,
  parseUnescoParam,
  PLACE_SORT_OPTIONS,
  primeHaystacks,
  uniqueSorted,
  withCount,
  type JournalFilter,
  type PlaceFilters,
  type PlaceSort,
  type VisitabilityFilter,
} from "../catalog/filterPlaces";
import { loadCatalogMeta, loadPlaces } from "../catalog/importCatalog";
import {
  formatTypes,
  hasGps,
  HERITAGE_OPTIONS,
  locationLine,
  PLACE_TYPE_OPTIONS,
  VISITABILITY_FILTER_GROUPS,
  VISITABILITY_OPTIONS,
} from "../catalog/labels";
import type { CatalogPlace, PlaceTypeCode } from "../catalog/types";
import { extraFilterCount, FilterDisclosure } from "../components/FilterDisclosure";
import { JournalChips } from "../components/JournalChips";
import { OrphanVisits } from "../components/OrphanVisits";
import { useDiaryBadges } from "../diary/useDiaryBadges";

const PAGE_SIZE = 80;
const SEARCH_DEBOUNCE_MS = 300;

function knownVisitability(value: string): value is Exclude<VisitabilityFilter, ""> {
  return (
    VISITABILITY_FILTER_GROUPS.some((item) => item.code === value) ||
    VISITABILITY_OPTIONS.some((item) => item.code === value)
  );
}

function filtersFromParams(params: URLSearchParams): PlaceFilters {
  const type = params.get("type") ?? "";
  const known = PLACE_TYPE_OPTIONS.some((item) => item.code === type);
  const visitabilityRaw = params.get("visitability") ?? "";
  return {
    query: params.get("q") ?? "",
    type: known ? (type as PlaceTypeCode) : "",
    region: params.get("region") ?? "",
    district: params.get("district") ?? "",
    visitability: knownVisitability(visitabilityRaw) ? visitabilityRaw : "",
    journal: parseJournalParam(params.get("journal")),
    unesco: parseUnescoParam(params.get("unesco")),
    heritage: parseHeritageParam(params.get("heritage")),
    gps: parseGpsParam(params.get("gps")),
    sort: parseSortParam(params.get("sort")),
  };
}

function paramsFromFilters(filters: PlaceFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.query.trim()) params.set("q", filters.query.trim());
  if (filters.type) params.set("type", filters.type);
  if (filters.region) params.set("region", filters.region);
  if (filters.district) params.set("district", filters.district);
  if (filters.visitability) params.set("visitability", filters.visitability);
  if (filters.journal) params.set("journal", filters.journal);
  if (filters.unesco) params.set("unesco", filters.unesco);
  if (filters.heritage) params.set("heritage", filters.heritage);
  if (filters.gps) params.set("gps", filters.gps);
  if (filters.sort && filters.sort !== "name") params.set("sort", filters.sort);
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
      filters.gps ||
      (filters.sort && filters.sort !== "name"),
  );
}

export function CatalogPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = filtersFromParams(searchParams);
  const [places, setPlaces] = useState<CatalogPlace[] | null>(null);
  const [version, setVersion] = useState<number | null>(null);
  const [limit, setLimit] = useState(PAGE_SIZE);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [queryDraft, setQueryDraft] = useState(filters.query);
  const { visitedIds, wantIds, favIds, orphans } = useDiaryBadges({ orphans: true });

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
    filters.gps,
    filters.sort,
    queryDraft,
  ]);

  useEffect(() => {
    setQueryDraft(filters.query);
  }, [filters.query]);

  useEffect(() => {
    if (queryDraft === filters.query) {
      return;
    }
    const handle = window.setTimeout(() => {
      const next = { ...filtersFromParams(searchParams), query: queryDraft };
      setSearchParams(paramsFromFilters(next), { replace: true });
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  }, [queryDraft, filters.query, searchParams, setSearchParams]);

  const liveFilters = useMemo(() => ({ ...filters, query: queryDraft }), [filters, queryDraft]);

  const regions = useMemo(() => uniqueSorted((places ?? []).map((place) => place.location.region)), [places]);
  const districts = useMemo(() => {
    const source = (places ?? []).filter((place) => !filters.region || place.location.region === filters.region);
    return uniqueSorted(source.map((place) => place.location.district));
  }, [places, filters.region]);

  const filtered = useMemo(
    () => filterPlaces(places ?? [], liveFilters, { visitedIds, wantIds, favIds }),
    [places, liveFilters, visitedIds, wantIds, favIds],
  );
  const facets = useMemo(
    () => facetCounts(places ?? [], liveFilters, { visitedIds, wantIds, favIds }),
    [places, liveFilters, visitedIds, wantIds, favIds],
  );
  const visible = filtered.slice(0, limit);

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
    setSearchParams(paramsFromFilters(next), { replace: true });
  };

  const setJournal = (journal: JournalFilter) => {
    update({ journal: filters.journal === journal ? "" : journal });
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
            ? `${places.length} míst`
            : `${filtered.length} z ${places.length} míst`}
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
      </header>

      <OrphanVisits groups={orphans} />

      <form className="filters" onSubmit={(event) => event.preventDefault()}>
        <label>
          Hledat
          <input
            type="search"
            value={queryDraft}
            onChange={(event) => setQueryDraft(event.target.value)}
            placeholder="Název, obec…"
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
            filters.gps,
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
          GPS
          <select value={filters.gps} onChange={(event) => update({ gps: event.target.value as PlaceFilters["gps"] })}>
            <option value="">{withCount("Vše", facets.gps[""])}</option>
            <option value="with">{withCount("Se souřadnicemi", facets.gps.with)}</option>
            <option value="without">{withCount("Bez GPS", facets.gps.without)}</option>
          </select>
        </label>
        </FilterDisclosure>
        {filtersActive(filters) ? (
          <button type="button" className="ghost" onClick={() => setSearchParams(paramsFromFilters(EMPTY_FILTERS), { replace: true })}>
            Zrušit filtry
          </button>
        ) : null}
      </form>

      {filtered.length === 0 ? (
        <p className="muted">Nic neodpovídá filtrům.</p>
      ) : (
        <ul className="place-list">
          {visible.map((place) => (
            <li key={place.id}>
              <Link to={`/place/${place.id}`} className="place-row">
                <span className="place-row-title">{place.name}</span>
                <span className="place-row-meta">
                  {formatTypes(place.types)}
                  {locationLine(place) ? ` · ${locationLine(place)}` : ""}
                  {hasGps(place) ? "" : " · bez GPS"}
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
            Dalších {Math.min(PAGE_SIZE, filtered.length - visible.length)} míst
          </button>
        </p>
      ) : null}
    </section>
  );
}
