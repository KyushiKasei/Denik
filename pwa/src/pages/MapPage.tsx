import { lazy, Suspense, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  facetCounts,
  filtersFromParams,
  uniqueSorted,
  withCount,
  type PlaceFilters,
} from "../catalog/filterPlaces";
import { loadPlaces, peekPlaces } from "../catalog/importCatalog";
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
import type { CatalogPlace } from "../catalog/types";
import { extraFilterCount, FilterDisclosure } from "../components/FilterDisclosure";
import { AddToTripButton } from "../components/AddToTripButton";
import { HoursBadge } from "../components/HoursBadge";
import { JournalChips } from "../components/JournalChips";
import { NearPlacePrompt } from "../components/NearPlacePrompt";
import { RouteLinks } from "../components/RouteLinks";
import { StampButton } from "../components/StampButton";
import { WorthToggle } from "../components/WorthToggle";
import { saveWorthFilter } from "../catalog/visitWorth";
import { useDiaryBadges } from "../diary/useDiaryBadges";
import { createTripFromPlaces } from "../diary/store";
import { todayIsoDate } from "../diary/ids";
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
import {
  clampCorridorKm,
  DEFAULT_CORRIDOR_KM,
  MAX_CORRIDOR_KM,
  MIN_CORRIDOR_KM,
  CORRIDOR_STEP_KM,
  placesAlongCorridor,
  placesInCorridor,
} from "../geo/corridor";
import { geocodeNominatim, resolveOriginFromCatalog, suggestOrigins, type GeoOrigin } from "../geo/origin";
import { SEARCH_DEBOUNCE_MS } from "../text/fold";
import { atlasActivePlaceId, atlasPlaces, atlasPlacesAt, atlasTimeCaption, atlasTimeline, parseUntilParam, timelineIndexForUntil, type AtlasCursor } from "../diary/atlas";
import { czechCountWord } from "../diary/timeline";
import { AtlasTimeControls } from "../components/AtlasTimeControls";
import { mapTileStatus, mapTileStatusLabel } from "../geo/tileStatus";
import type { LiveGpsPosition } from "../components/NearbyMap";

const NearbyMap = lazy(async () => {
  const module = await import("../components/NearbyMap");
  return { default: module.NearbyMap };
});
const AtlasMap = lazy(async () => {
  const module = await import("../components/AtlasMap");
  return { default: module.AtlasMap };
});

function mapFiltersActive(filters: PlaceFilters): boolean {
  return Boolean(
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
      filters.extra ||
      filters.lost ||
      filters.style,
  );
}

export function MapPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = filtersFromParams(searchParams);
  const atlasMode = searchParams.get("view") === "atlas";
  const radiusKm = clampRadiusKm(searchParams.get("radius_km") ?? DEFAULT_RADIUS_KM);
  const [places, setPlaces] = useState<CatalogPlace[] | null>(() => peekPlaces());
  const { visitedIds, wantIds, favIds, todayIds, visits, error: badgeError, reload } = useDiaryBadges();
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
  const [atlasCursor, setAtlasCursor] = useState<AtlasCursor | null>(null);
  const [atlasPlaying, setAtlasPlaying] = useState(false);
  const [destQuery, setDestQuery] = useState("");
  const [destSuggestQuery, setDestSuggestQuery] = useState("");
  const [originSuggestOpen, setOriginSuggestOpen] = useState(false);
  const [destSuggestOpen, setDestSuggestOpen] = useState(false);
  const [destLookupError, setDestLookupError] = useState<string | null>(null);
  const [destBusy, setDestBusy] = useState(false);
  const [corridorSaveError, setCorridorSaveError] = useState<string | null>(null);

  const latParam = searchParams.get("lat");
  const lonParam = searchParams.get("lon");
  const labelParam = searchParams.get("origin_label");
  const destLatParam = searchParams.get("dest_lat");
  const destLonParam = searchParams.get("dest_lon");
  const destLabelParam = searchParams.get("dest_label");
  const dest = originFromUrlParams(destLatParam, destLonParam, destLabelParam);
  const corridorKm = clampCorridorKm(searchParams.get("corridor_km") ?? DEFAULT_CORRIDOR_KM);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

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

  useEffect(() => {
    const handle = window.setTimeout(() => setSuggestQuery(query), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  }, [query]);

  const suggestions = useMemo(() => suggestOrigins(places ?? [], suggestQuery), [places, suggestQuery]);
  const destSuggestions = useMemo(() => suggestOrigins(places ?? [], destSuggestQuery), [places, destSuggestQuery]);
  const showOriginSuggest = originSuggestOpen && suggestions.length > 0;
  const showDestSuggest = destSuggestOpen && destSuggestions.length > 0;
  useEffect(() => {
    const handle = window.setTimeout(() => setDestSuggestQuery(destQuery), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  }, [destQuery]);

  useEffect(() => {
    if (!showOriginSuggest && !showDestSuggest) {
      return;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOriginSuggestOpen(false);
        setDestSuggestOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [showOriginSuggest, showDestSuggest]);
  // `q` na mapě je hledání startu/cíle, ne filtr názvu v katalogu.
  const catalogFilters: PlaceFilters = { ...filters, query: "" };
  const nearby = useMemo(() => {
    if (!origin || !places) {
      return { hits: [], skippedNoGps: 0, hitsTotal: 0 };
    }
    const diary = { visitedIds, wantIds, favIds };
    if (dest) {
      return placesAlongCorridor(places, origin, dest, corridorKm, catalogFilters, diary);
    }
    return placesNearby(places, origin, radiusKm, catalogFilters, diary);
  }, [origin, dest, places, radiusKm, corridorKm, catalogFilters, visitedIds, wantIds, favIds]);
  const atlasRows = useMemo(() => {
    if (!places) {
      return [];
    }
    return atlasPlaces(places, catalogFilters, { visitedIds, wantIds, favIds }, { includeUnvisited: Boolean(filters.lost) });
  }, [places, catalogFilters, filters.lost, visitedIds, wantIds, favIds]);
  const untilParam = parseUntilParam(searchParams.get("until"));
  const atlasEvents = useMemo(() => {
    const allowed = new Set(atlasRows.map((row) => row.place.id));
    return atlasTimeline(visits, places ?? []).filter((event) => allowed.has(event.placeId));
  }, [visits, places, atlasRows]);
  const atlasTimeCursor: AtlasCursor = atlasCursor ?? timelineIndexForUntil(atlasEvents, untilParam);
  const visibleAtlasRows = useMemo(
    () => atlasPlacesAt(atlasRows, atlasEvents, atlasTimeCursor),
    [atlasRows, atlasEvents, atlasTimeCursor],
  );
  const atlasActiveId = atlasActivePlaceId(atlasEvents, atlasTimeCursor);
  const inRadius = useMemo(() => {
    if (!origin || !places) {
      return [];
    }
    if (dest) {
      return placesInCorridor(places, origin, dest, corridorKm);
    }
    const radius = clampRadiusKm(radiusKm);
    return places.filter((place) => {
      if (!hasGps(place) || place.location.latitude == null || place.location.longitude == null) {
        return false;
      }
      const km = haversineKm(origin.latitude, origin.longitude, place.location.latitude, place.location.longitude);
      return km != null && km <= radius;
    });
  }, [origin, dest, places, radiusKm, corridorKm]);
  const facetSource = atlasMode ? (places ?? []).filter(hasGps) : inRadius;
  const facets = useMemo(
    () => facetCounts(facetSource, catalogFilters, { visitedIds, wantIds, favIds }),
    [facetSource, catalogFilters, visitedIds, wantIds, favIds],
  );
  const regions = useMemo(() => uniqueSorted(facetSource.map((place) => place.location.region)), [facetSource]);
  const districts = useMemo(() => {
    const source = facetSource.filter((place) => !filters.region || place.location.region === filters.region);
    return uniqueSorted(source.map((place) => place.location.district));
  }, [facetSource, filters.region]);

  const accuracyLabel = formatGpsAccuracy(liveGps?.accuracy);
  const tileStatus = mapTileStatus(!offline, tileError);
  const showTileNotice = tileStatus === "offline-miss";

  useEffect(() => {
    setAtlasCursor(null);
  }, [untilParam]);

  useEffect(() => {
    if (!atlasMode) {
      setAtlasPlaying(false);
    }
  }, [atlasMode]);

  useEffect(() => {
    if (!atlasPlaying || !atlasMode) {
      return;
    }
    const handle = window.setInterval(() => {
      setAtlasCursor((prev) => {
        const current = prev ?? timelineIndexForUntil(atlasEvents, untilParam);
        if (current === "today") {
          setAtlasPlaying(false);
          return "today";
        }
        if (current < 0) {
          return 0;
        }
        if (current >= atlasEvents.length - 1) {
          setAtlasPlaying(false);
          return "today";
        }
        return current + 1;
      });
    }, 500);
    return () => window.clearInterval(handle);
  }, [atlasPlaying, atlasMode, atlasEvents, untilParam]);

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

  const setAtlasTime = (next: AtlasCursor) => {
    setAtlasPlaying(false);
    setAtlasCursor(next);
    if (next === "today" && untilParam) {
      patchParams({ until: null });
    }
  };

  const toggleAtlasPlay = () => {
    if (atlasPlaying) {
      setAtlasPlaying(false);
      return;
    }
    setAtlasCursor((prev) => {
      const current = prev ?? atlasTimeCursor;
      if (current === "today" || (typeof current === "number" && current >= atlasEvents.length - 1)) {
        return 0;
      }
      return current;
    });
    setAtlasPlaying(true);
  };

  useEffect(() => {
    if (!atlasPlaying || atlasTimeCursor !== "today") {
      return;
    }
    setAtlasPlaying(false);
    if (untilParam) {
      patchParams({ until: null });
    }
  }, [atlasPlaying, atlasTimeCursor, untilParam]);

  const applyDest = (next: GeoOrigin) => {
    setDestLookupError(null);
    setDestQuery(next.label);
    setDestSuggestOpen(false);
    patchParams({
      dest_lat: String(next.latitude),
      dest_lon: String(next.longitude),
      dest_label: next.label,
    });
  };

  const lookupDest = async () => {
    const term = destQuery.trim();
    if (!term || !places) {
      return;
    }
    setDestSuggestOpen(false);
    const fromCatalog = resolveOriginFromCatalog(places, term);
    if (fromCatalog) {
      applyDest(fromCatalog);
      return;
    }
    setDestBusy(true);
    try {
      const fromNominatim = await geocodeNominatim(term);
      if (!alive.current) {
        return;
      }
      if (fromNominatim) {
        applyDest(fromNominatim);
        return;
      }
      setDestLookupError("Cíl se nepodařilo najít.");
    } finally {
      if (alive.current) {
        setDestBusy(false);
      }
    }
  };

  const applyOrigin = (next: GeoOrigin) => {
    setOrigin(next);
    setLookupError(null);
    setOriginSuggestOpen(false);
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
        if (!alive.current) {
          return;
        }
        const coords: LiveGpsPosition = {
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: Number.isFinite(pos.coords.accuracy) ? pos.coords.accuracy : null,
        };
        setLiveGps(coords);
        onOk(coords);
      },
      () => {
        if (alive.current) {
          setGpsError("Polohu se nepodařilo zjistit. Napište obec, nebo souřadnice.");
        }
      },
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
    setOriginSuggestOpen(false);
    const fromCatalog = resolveOriginFromCatalog(places, term);
    if (fromCatalog) {
      applyOrigin(fromCatalog);
      return;
    }
    setBusy(true);
    try {
      const fromNominatim = await geocodeNominatim(term);
      if (!alive.current) {
        return;
      }
      if (fromNominatim) {
        applyOrigin(fromNominatim);
        return;
      }
      setLookupError("Místo se nepodařilo najít. Zkuste jiný název.");
    } finally {
      if (alive.current) {
        setBusy(false);
      }
    }
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
          {atlasMode
            ? `${visibleAtlasRows.length} ${czechCountWord(visibleAtlasRows.length, "značka", "značky", "značek")} · ${atlasTimeCursor === "today" ? "razítka a chci navštívit" : atlasTimeCaption(atlasEvents, atlasTimeCursor)}${filters.region ? ` · ${filters.region}` : ""}`
            : origin
              ? dest
                ? `${nearby.hitsTotal > nearby.hits.length ? `nejbližších ${nearby.hits.length} z ${nearby.hitsTotal}` : String(nearby.hits.length)} při cestě (${corridorKm} km od čáry) · přeskočeno bez GPS: ${nearby.skippedNoGps}`
                : `${nearby.hitsTotal > nearby.hits.length ? `nejbližších ${nearby.hits.length} z ${nearby.hitsTotal}` : String(nearby.hits.length)} v ${radiusKm} km · přeskočeno bez GPS: ${nearby.skippedNoGps}`
              : "Tady jsem, nebo napište kde jste."}
          {accuracyLabel ? ` · přesnost ${accuracyLabel}` : ""}
        </p>
        <div className="segmented cols-3 catalog-view-toggle" role="group" aria-label="Režim mapy">
          <button type="button" className={atlasMode ? undefined : "active"} onClick={() => patchParams({ view: null, until: null, lost: null })}>
            Poblíž
          </button>
          <button type="button" className={atlasMode && !filters.lost ? "active" : undefined} onClick={() => patchParams({ view: "atlas", lost: null })}>
            Atlas
          </button>
          <button
            type="button"
            className={atlasMode && filters.lost ? "active" : undefined}
            onClick={() => patchParams({ view: "atlas", lost: "yes" })}
          >
            Zaniklé
          </button>
        </div>
        <p className="muted small" role="status">
          {mapTileStatusLabel(tileStatus)}
        </p>
      </header>

      {badgeError ? (
        <p className="error" role="alert">
          {badgeError}
        </p>
      ) : null}

      {showTileNotice ? (
        <p className="offline-notice" role="status">
          Seznam míst funguje i bez sítě. Tuhle část mapy v mezipaměti nemáte — offline balíček Česka tu není.
        </p>
      ) : null}

      {!atlasMode ? (
        <NearPlacePrompt
          places={places}
          visits={visits}
          stampedTodayIds={todayIds}
          onStamped={() => void reload()}
        />
      ) : null}

      <form className="filters nearby-controls" onSubmit={searchPlace}>
        <WorthToggle
          value={filters.worth !== false}
          onChange={(worth) => {
            saveWorthFilter(worth);
            patchParams({ worth: worth ? null : "all" });
          }}
          visitCount={facets.worth.visit}
          allCount={facets.worth.all}
        />
        <label className="nearby-search-field">
          Kde jsem
          <span className="nearby-search-row">
            <input
              type="search"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setOriginSuggestOpen(true);
              }}
              onFocus={() => setOriginSuggestOpen(true)}
              placeholder="Obec nebo název (od 3 písmen)…"
              autoComplete="off"
            />
            <button type="submit" disabled={busy}>
              {busy ? "Hledám…" : "Hledat"}
            </button>
          </span>
        </label>
        <div className="actions-row">
          <button type="button" className="ghost" onClick={useGps}>
            Tady jsem
          </button>
          <button type="button" className="ghost" onClick={recenter}>
            Vycentrovat
          </button>
        </div>
        {showOriginSuggest ? (
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
          Cíl cesty
          <input
            type="search"
            value={destQuery}
            onChange={(event) => {
              setDestQuery(event.target.value);
              setDestSuggestOpen(true);
            }}
            onFocus={() => setDestSuggestOpen(true)}
            placeholder="Praha, Brno…"
            autoComplete="off"
          />
        </label>
        <div className="actions-row">
          <button type="button" className="ghost" onClick={() => void lookupDest()}>
            {destBusy ? "Hledám cíl…" : "Při cestě"}
          </button>
          {dest ? (
            <button
              type="button"
              className="ghost"
              onClick={() => {
                setDestQuery("");
                patchParams({ dest_lat: null, dest_lon: null, dest_label: null });
              }}
            >
              Zrušit koridor
            </button>
          ) : null}
        </div>
        {showDestSuggest ? (
          <ul className="nearby-suggest">
            {destSuggestions.map((item) => (
              <li key={`dest-${item.label}-${item.latitude}`}>
                <button type="button" className="text-link" onClick={() => applyDest(item)}>
                  Cíl: {item.label}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {destLookupError ? (
          <p className="error" role="alert">
            {destLookupError}
          </p>
        ) : null}
        {dest ? (
          <label>
            {corridorKm} km od čáry
            <input
              type="range"
              min={MIN_CORRIDOR_KM}
              max={MAX_CORRIDOR_KM}
              step={CORRIDOR_STEP_KM}
              value={corridorKm}
              onChange={(event) => patchParams({ corridor_km: event.target.value })}
            />
          </label>
        ) : null}
        {dest && nearby.hits.length > 0 ? (
          <div className="actions-row">
            <button
              type="button"
              className="ghost"
              onClick={() => {
                void (async () => {
                  setCorridorSaveError(null);
                  try {
                    const trip = await createTripFromPlaces({
                      name: dest.label ? `Cesta: ${dest.label}` : "Při cestě",
                      planned_on: todayIsoDate(),
                      origin: origin
                        ? { latitude: origin.latitude, longitude: origin.longitude, label: origin.label }
                        : null,
                      placeIds: nearby.hits.map((hit) => hit.place.id),
                    });
                    navigate(`/diary?sec=trips&trip=${trip.id}`);
                  } catch (err) {
                    setCorridorSaveError(err instanceof Error ? err.message : "Výlet se nepodařilo uložit.");
                  }
                })();
              }}
            >
              Uložit zastávky jako výlet
            </button>
          </div>
        ) : null}
        {corridorSaveError ? (
          <p className="error" role="alert">
            {corridorSaveError}
          </p>
        ) : null}
        {dest ? null : (
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
        )}
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
            filters.hours,
            filters.extra,
            filters.lost,
            filters.style,
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
        <label>
          Otevírací doba
          <select value={filters.hours ?? ""} onChange={(event) => patchParams({ hours: event.target.value || null })}>
            <option value="">{withCount("Vše", facets.hours[""])}</option>
            <option value="open">{withCount("Dnes otevřeno", facets.hours.open)}</option>
            <option value="season">{withCount("Sezóna teď", facets.hours.season)}</option>
          </select>
        </label>
        <label>
          Stav
          <select
            value={filters.condition ?? ""}
            onChange={(event) => patchParams({ condition: event.target.value || null })}
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
          Na výletě
          <select value={filters.extra ?? ""} onChange={(event) => patchParams({ extra: event.target.value || null })}>
            <option value="">{withCount("Vše", facets.extra[""])}</option>
            <option value="dogs">{withCount("Se psem", facets.extra.dogs)}</option>
            <option value="free">{withCount("Zdarma", facets.extra.free)}</option>
            <option value="toilets">{withCount("Toalety", facets.extra.toilets)}</option>
            <option value="cafe">{withCount("Občerstvení", facets.extra.cafe)}</option>
            <option value="playground">{withCount("Hřiště", facets.extra.playground)}</option>
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
                  next.delete("condition");
                  next.delete("gps");
                  next.delete("hours");
                  next.delete("extra");
                  next.delete("lost");
                  next.delete("style");
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

      {atlasMode ? (
        <>
          <p className="map-legend">
            <span className="is-visited">
              <i /> razítko
            </span>
            {atlasTimeCursor === "today" ? (
              <span className="is-want">
                <i /> chci navštívit
              </span>
            ) : null}
            {filters.region && atlasTimeCursor === "today" ? (
              <span>
                <i /> ostatní v kraji
              </span>
            ) : null}
          </p>
          <AtlasTimeControls
            timeline={atlasEvents}
            cursor={atlasTimeCursor}
            playing={atlasPlaying}
            onCursor={setAtlasTime}
            onPlayToggle={toggleAtlasPlay}
          />
          <Suspense fallback={<p className="muted">Načítám atlas…</p>}>
            <AtlasMap
              rows={visibleAtlasRows}
              fitRows={atlasRows}
              activePlaceId={atlasActiveId}
              stampedTodayIds={todayIds}
              onTileError={() => setTileError(true)}
              onVisitStamped={() => void reload()}
            />
          </Suspense>
        </>
      ) : origin ? (
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
            dest={dest}
            onTileError={() => setTileError(true)}
            stampedTodayIds={todayIds}
            onVisitStamped={() => void reload()}
          />
        </Suspense>
        </>
      ) : (
        <p className="muted">Mapa se ukáže po poloze nebo hledání.</p>
      )}

      {!atlasMode && origin && nearby.hits.length === 0 ? (
        <p className="muted">V tomto okruhu nic není.</p>
      ) : null}

      {!atlasMode && nearby.hits.length > 0 ? (
        <ul className="place-list">
          {nearby.hits.map((hit) => (
            <li key={hit.place.id}>
              <Link to={`/place/${hit.place.id}?from=map`} state={{ from: "map" }} className="place-row">
                <span className="place-row-title">
                  {hit.km.toFixed(1)} km · {hit.place.name}
                </span>
                <span className="place-row-meta">
                  {formatTypes(hit.place.types, { hideInName: hit.place.name })}
                  {locationLine(hit.place) ? ` · ${locationLine(hit.place)}` : ""}
                  {" "}
                  <HoursBadge place={hit.place} />
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
              <div className="place-row-actions">
                <StampButton
                  placeId={hit.place.id}
                  alreadyToday={todayIds.has(hit.place.id)}
                  size="compact"
                  onStamped={() => void reload()}
                />
                <AddToTripButton
                  placeId={hit.place.id}
                  origin={
                    origin
                      ? { latitude: origin.latitude, longitude: origin.longitude, label: origin.label }
                      : null
                  }
                />
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      <p className="muted small">
        Vzdušná čára, ne silnice. Koridor je buffer od úsečky start–cíl. Trasa se otevírá v Mapy.cz / Apple Maps.
      </p>
    </section>
  );
}
