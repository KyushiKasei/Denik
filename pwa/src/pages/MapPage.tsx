import { lazy, Suspense, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  facetCounts,
  parseGpsParam,
  parseHeritageParam,
  parseJournalParam,
  parseUnescoParam,
  uniqueSorted,
  withCount,
  type PlaceFilters,
  type VisitabilityFilter,
} from "../catalog/filterPlaces";
import { loadPlaces } from "../catalog/importCatalog";
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
import { AddToTripButton } from "../components/AddToTripButton";
import { JournalChips } from "../components/JournalChips";
import { RouteLinks } from "../components/RouteLinks";
import { useDiaryBadges } from "../diary/useDiaryBadges";
import { clampRadiusKm, DEFAULT_RADIUS_KM, haversineKm, MAX_RADIUS_KM, MIN_RADIUS_KM, RADIUS_STEP_KM } from "../geo/haversine";
import {
  formatGpsAccuracy,
  loadStoredMapView,
  originFromUrlParams,
  saveStoredMapView,
  urlHasCoords,
  urlHasRadius,
} from "../geo/mapOriginStore";
import { placesNearby } from "../geo/nearby";
import { geocodeNominatim, resolveOriginFromCatalog, suggestOrigins, type GeoOrigin } from "../geo/origin";
import { SEARCH_DEBOUNCE_MS } from "../text/fold";
import { mapTileStatus, mapTileStatusLabel } from "../geo/tileStatus";
import type { LiveGpsPosition } from "../components/NearbyMap";

const NearbyMap = lazy(async () => {
  const module = await import("../components/NearbyMap");
  return { default: module.NearbyMap };
});

function filtersFromParams(params: URLSearchParams): PlaceFilters {
  const type = params.get("type") ?? "";
  const knownType = PLACE_TYPE_OPTIONS.some((item) => item.code === type);
  const visitability = params.get("visitability") ?? "";
  const knownVisit =
    VISITABILITY_FILTER_GROUPS.some((item) => item.code === visitability) ||
    VISITABILITY_OPTIONS.some((item) => item.code === visitability);
  return {
    query: params.get("q") ?? "",
    type: knownType ? (type as PlaceTypeCode) : "",
    region: params.get("region") ?? "",
    district: params.get("district") ?? "",
    visitability: knownVisit ? (visitability as VisitabilityFilter) : "",
    journal: parseJournalParam(params.get("journal")),
    unesco: parseUnescoParam(params.get("unesco")),
    heritage: parseHeritageParam(params.get("heritage")),
    gps: parseGpsParam(params.get("gps")),
  };
}

function mapFiltersActive(filters: PlaceFilters): boolean {
  return Boolean(
    filters.type ||
      filters.region ||
      filters.district ||
      filters.visitability ||
      filters.journal ||
      filters.unesco ||
      filters.heritage ||
      filters.gps,
  );
}

export function MapPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = filtersFromParams(searchParams);
  const radiusKm = clampRadiusKm(searchParams.get("radius_km") ?? DEFAULT_RADIUS_KM);
  const [places, setPlaces] = useState<CatalogPlace[] | null>(null);
  const { visitedIds, wantIds, favIds } = useDiaryBadges();
  const [origin, setOrigin] = useState<GeoOrigin | null>(null);
  const [query, setQuery] = useState(filters.query);
  const [suggestQuery, setSuggestQuery] = useState(filters.query);
  const [gpsError, setGpsError] = useState<string | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [liveGps, setLiveGps] = useState<LiveGpsPosition | null>(null);
  const [panNonce, setPanNonce] = useState(0);
  const [offline, setOffline] = useState(() => typeof navigator !== "undefined" && navigator.onLine === false);
  const [tileError, setTileError] = useState(false);

  const latParam = searchParams.get("lat");
  const lonParam = searchParams.get("lon");
  const labelParam = searchParams.get("origin_label");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const rows = await loadPlaces();
        if (!cancelled) {
          setPlaces(rows);
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
    const stored = loadStoredMapView();
    if (!stored) {
      return;
    }
    const next = new URLSearchParams(searchParams);
    let changed = false;
    if (!urlHasCoords(searchParams)) {
      next.set("lat", String(stored.latitude));
      next.set("lon", String(stored.longitude));
      next.set("origin_label", stored.label);
      changed = true;
    }
    if (!urlHasRadius(searchParams)) {
      next.set("radius_km", String(stored.radiusKm));
      changed = true;
    }
    if (changed) {
      setSearchParams(next, { replace: true });
    }
    // Obnova jen při otevření záložky. Souřadnice v URL mají přednost.
  }, []);

  useEffect(() => {
    const next = originFromUrlParams(latParam, lonParam, labelParam);
    if (!next) {
      return;
    }
    setOrigin(next);
    setLookupError(null);
  }, [latParam, lonParam, labelParam]);

  useEffect(() => {
    if (!origin) {
      return;
    }
    saveStoredMapView({
      latitude: origin.latitude,
      longitude: origin.longitude,
      label: origin.label,
      source: origin.source,
      radiusKm,
    });
  }, [origin, radiusKm]);

  useEffect(() => {
    const sync = () => {
      setOffline(navigator.onLine === false);
      if (navigator.onLine) {
        setTileError(false);
      }
    };
    window.addEventListener("online", sync);
    window.addEventListener("offline", sync);
    return () => {
      window.removeEventListener("online", sync);
      window.removeEventListener("offline", sync);
    };
  }, []);

  const regions = useMemo(() => uniqueSorted((places ?? []).map((place) => place.location.region)), [places]);
  const districts = useMemo(() => {
    const source = (places ?? []).filter((place) => !filters.region || place.location.region === filters.region);
    return uniqueSorted(source.map((place) => place.location.district));
  }, [places, filters.region]);

  useEffect(() => {
    const handle = window.setTimeout(() => setSuggestQuery(query), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  }, [query]);

  const suggestions = useMemo(() => suggestOrigins(places ?? [], suggestQuery), [places, suggestQuery]);
  const nearby = useMemo(() => {
    if (!origin || !places) {
      return { hits: [], skippedNoGps: 0 };
    }
    return placesNearby(places, origin, radiusKm, filters, { visitedIds, wantIds, favIds });
  }, [origin, places, radiusKm, filters, visitedIds, wantIds, favIds]);
  const inRadius = useMemo(() => {
    if (!origin || !places) {
      return [];
    }
    const radius = clampRadiusKm(radiusKm);
    return places.filter((place) => {
      if (!hasGps(place) || place.location.latitude == null || place.location.longitude == null) {
        return false;
      }
      const km = haversineKm(origin.latitude, origin.longitude, place.location.latitude, place.location.longitude);
      return km != null && km <= radius;
    });
  }, [origin, places, radiusKm]);
  const facets = useMemo(
    () => facetCounts(inRadius, filters, { visitedIds, wantIds, favIds }),
    [inRadius, filters, visitedIds, wantIds, favIds],
  );

  const accuracyLabel = formatGpsAccuracy(liveGps?.accuracy);
  const tileStatus = mapTileStatus(!offline, tileError);
  const showTileNotice = tileStatus === "offline-miss";

  const patchParams = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(patch)) {
      if (value == null || value === "") {
        next.delete(key);
      } else {
        next.set(key, value);
      }
    }
    setSearchParams(next, { replace: true });
  };

  const applyOrigin = (next: GeoOrigin) => {
    setOrigin(next);
    setLookupError(null);
    setQuery(next.source === "nominatim" || next.source === "gps" ? next.label : query);
    patchParams({
      lat: String(next.latitude),
      lon: String(next.longitude),
      origin_label: next.label,
      q: next.source === "place" || next.source === "municipality" ? next.label : query.trim() || next.label,
    });
  };

  const applyGpsOrigin = (coords: LiveGpsPosition) => {
    applyOrigin({
      latitude: coords.latitude,
      longitude: coords.longitude,
      label: "Moje poloha",
      source: "gps",
    });
  };

  const readGps = (onOk: (coords: LiveGpsPosition) => void) => {
    if (!navigator.geolocation) {
      setGpsError("Prohlížeč GPS nenabízí.");
      return;
    }
    setGpsError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const coords: LiveGpsPosition = {
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: Number.isFinite(pos.coords.accuracy) ? pos.coords.accuracy : null,
        };
        setLiveGps(coords);
        onOk(coords);
      },
      () => setGpsError("Polohu se nepodařilo zjistit. Napište obec, nebo souřadnice."),
      { enableHighAccuracy: false, maximumAge: 15_000, timeout: 15_000 },
    );
  };

  const useGps = () => {
    readGps(applyGpsOrigin);
  };

  const recenter = () => {
    readGps((coords) => {
      applyGpsOrigin(coords);
      setPanNonce((value) => value + 1);
    });
  };

  const searchPlace = async (event: FormEvent) => {
    event.preventDefault();
    const term = query.trim();
    if (!term || !places) {
      return;
    }
    const fromCatalog = resolveOriginFromCatalog(places, term);
    if (fromCatalog) {
      applyOrigin(fromCatalog);
      return;
    }
    setBusy(true);
    const fromNominatim = await geocodeNominatim(term);
    setBusy(false);
    if (fromNominatim) {
      applyOrigin(fromNominatim);
      return;
    }
    setLookupError("Místo se nepodařilo najít. Zkuste jiný název.");
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
        <h1>Mapa</h1>
        <p>Nejdřív nahrajte <code>catalog.json</code>.</p>
        <p>
          <Link to="/import" className="button">
            Nahrát catalog.json
          </Link>
        </p>
      </section>
    );
  }

  return (
    <section className="nearby-page">
      <header className="page-header">
        <h1>Mapa</h1>
        <p className="muted">
          {origin
            ? `${nearby.hits.length} v ${radiusKm} km · přeskočeno bez GPS: ${nearby.skippedNoGps}`
            : "Tady jsem, nebo napište kde jste."}
          {accuracyLabel ? ` · přesnost ${accuracyLabel}` : ""}
        </p>
        <p className="muted small" role="status">
          {mapTileStatusLabel(tileStatus)}
        </p>
      </header>

      {showTileNotice ? (
        <p className="offline-notice" role="status">
          Seznam míst funguje i bez sítě. Tuhle část mapy v mezipaměti nemáte — offline balíček Česka tu není.
        </p>
      ) : null}

      <form className="filters nearby-controls" onSubmit={searchPlace}>
        <label>
          Kde jsem
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Obec nebo název (od 3 písmen)…"
            autoComplete="off"
          />
        </label>
        <div className="actions-row">
          <button type="button" className="ghost" onClick={useGps}>
            Tady jsem
          </button>
          <button type="button" className="ghost" onClick={recenter}>
            Vycentrovat
          </button>
          <button type="submit" disabled={busy}>
            {busy ? "Hledám…" : "Hledat"}
          </button>
        </div>
        {suggestions.length > 0 ? (
          <ul className="nearby-suggest">
            {suggestions.map((item) => (
              <li key={`${item.label}-${item.latitude}`}>
                <button type="button" className="text-link" onClick={() => applyOrigin(item)}>
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {gpsError ? (
          <p className="error" role="alert">
            {gpsError}
          </p>
        ) : null}
        {lookupError ? (
          <p className="error" role="alert">
            {lookupError}
          </p>
        ) : null}
        <label>
          {radiusKm} km
          <input
            type="range"
            min={MIN_RADIUS_KM}
            max={MAX_RADIUS_KM}
            step={RADIUS_STEP_KM}
            value={radiusKm}
            onChange={(event) => patchParams({ radius_km: event.target.value })}
          />
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
          ])}
        >
        <label>
          Typ
          <select
            value={filters.type}
            onChange={(event) => patchParams({ type: event.target.value || null })}
          >
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
          <select
            value={filters.region}
            onChange={(event) => patchParams({ region: event.target.value || null, district: null })}
          >
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
          <select
            value={filters.district}
            onChange={(event) => patchParams({ district: event.target.value || null })}
          >
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
            onChange={(event) => patchParams({ visitability: event.target.value || null })}
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
          <select
            value={filters.journal}
            onChange={(event) => patchParams({ journal: event.target.value || null })}
          >
            <option value="">{withCount("Vše", facets.journal[""])}</option>
            <option value="visited">{withCount("Navštíveno", facets.journal.visited)}</option>
            <option value="not_visited">{withCount("Nenavštíveno", facets.journal.not_visited)}</option>
            <option value="want_to_visit">{withCount("Chci navštívit", facets.journal.want_to_visit)}</option>
            <option value="favorite">{withCount("Oblíbené", facets.journal.favorite)}</option>
          </select>
        </label>
        <label>
          UNESCO
          <select value={filters.unesco} onChange={(event) => patchParams({ unesco: event.target.value || null })}>
            <option value="">{withCount("Vše", facets.unesco[""])}</option>
            <option value="yes">{withCount("UNESCO", facets.unesco.yes)}</option>
            <option value="no">{withCount("Bez UNESCO", facets.unesco.no)}</option>
          </select>
        </label>
        <label>
          Ochrana
          <select value={filters.heritage} onChange={(event) => patchParams({ heritage: event.target.value || null })}>
            <option value="">{withCount("Vše", facets.heritage[""])}</option>
            {HERITAGE_OPTIONS.map((item) => (
              <option key={item.code} value={item.code}>
                {withCount(item.name_cs, facets.heritage[item.code])}
              </option>
            ))}
          </select>
        </label>
        </FilterDisclosure>
        {mapFiltersActive(filters) ? (
          <button
            type="button"
            className="ghost"
            onClick={() =>
              setSearchParams(
                (() => {
                  const next = new URLSearchParams(searchParams);
                  next.delete("type");
                  next.delete("visitability");
                  next.delete("journal");
                  next.delete("unesco");
                  next.delete("heritage");
                  next.delete("gps");
                  next.delete("region");
                  next.delete("district");
                  return next;
                })(),
                { replace: true },
              )
            }
          >
            Zrušit filtry
          </button>
        ) : null}
      </form>

      {origin ? (
        <>
          <p className="map-legend">
            <span className="is-visited">
              <i /> navštíveno
            </span>
            <span className="is-want">
              <i /> chci navštívit
            </span>
            <span>
              <i /> ostatní
            </span>
          </p>
          <Suspense fallback={<p className="muted">Načítám mapu…</p>}>
          <NearbyMap
            origin={origin}
            radiusKm={radiusKm}
            hits={nearby.hits}
            visitedIds={visitedIds}
            wantIds={wantIds}
            liveGps={liveGps}
            panNonce={panNonce}
            onTileError={() => setTileError(true)}
          />
        </Suspense>
        </>
      ) : (
        <p className="muted">Mapa se ukáže po poloze nebo hledání.</p>
      )}

      {origin && nearby.hits.length === 0 ? (
        <p className="muted">V tomto okruhu nic není.</p>
      ) : null}

      {nearby.hits.length > 0 ? (
        <ul className="place-list">
          {nearby.hits.map((hit) => (
            <li key={hit.place.id}>
              <Link to={`/place/${hit.place.id}?from=map`} state={{ from: "map" }} className="place-row">
                <span className="place-row-title">
                  {hit.km.toFixed(1)} km · {hit.place.name}
                </span>
                <span className="place-row-meta">
                  {formatTypes(hit.place.types)}
                  {locationLine(hit.place) ? ` · ${locationLine(hit.place)}` : ""}
                </span>
                <JournalChips
                  visited={visitedIds.has(hit.place.id)}
                  want={wantIds.has(hit.place.id)}
                  favorite={favIds.has(hit.place.id)}
                />
              </Link>
              {hit.place.location.latitude != null && hit.place.location.longitude != null ? (
                <RouteLinks
                  dest={{ latitude: hit.place.location.latitude, longitude: hit.place.location.longitude }}
                  destName={hit.place.name}
                  origin={origin}
                  showHint={false}
                />
              ) : null}
              <AddToTripButton
                placeId={hit.place.id}
                origin={
                  origin
                    ? { latitude: origin.latitude, longitude: origin.longitude, label: origin.label }
                    : null
                }
              />
            </li>
          ))}
        </ul>
      ) : null}

      <p className="muted small">
        Vzdušná čára, ne silnice. Trasa se otevírá v Mapy.cz / Apple Maps. Dlaždice se ukládají jen z prohlížených
        výřezů, ne celá ČR.
      </p>
    </section>
  );
}
