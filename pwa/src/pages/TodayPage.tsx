import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { loadPlaces, peekPlaces } from "../catalog/importCatalog";
import { hasGps } from "../catalog/labels";
import type { CatalogPlace, StoredVisit } from "../catalog/types";
import { CzechRegionsMap } from "../components/CzechRegionsMap";
import { FirstRunCoach } from "../components/FirstRunCoach";
import { PlaceCard } from "../components/PlaceCard";
import { StampButton } from "../components/StampButton";
import { PhotoIntake } from "../components/PhotoIntake";
import { NearPlacePrompt } from "../components/NearPlacePrompt";
import { TripToday } from "../components/TripToday";
import { TODAY_MOODS, parseMoodParam, type TodayMood } from "../catalog/moods";
import { collectionStats, regionProgress } from "../diary/regions";
import { todayIsoDate } from "../diary/ids";
import { visitOnDate } from "../diary/stamp";
import { loadActiveTripId, loadTrips, loadVisits } from "../diary/store";
import type { StoredTrip } from "../diary/types";
import { discoverPool, lastActiveVisit, nearbyUnvisited, pickDiscoverToday } from "../diary/today";
import { formatVisitDate, uniqueVisitedPlaceIds, czechCountWord } from "../diary/timeline";
import { useDiaryBadges } from "../diary/useDiaryBadges";
import { DEFAULT_RADIUS_KM, haversineKm } from "../geo/haversine";
import { loadStoredMapView } from "../geo/mapOriginStore";

export function TodayPage() {
  const location = useLocation();
  const mood: TodayMood = parseMoodParam(new URLSearchParams(location.search).get("mood"));
  const [places, setPlaces] = useState<CatalogPlace[] | null>(() => peekPlaces());
  const [visits, setVisits] = useState<StoredVisit[] | null>(null);
  const [trip, setTrip] = useState<StoredTrip | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [skipIds, setSkipIds] = useState<Set<string>>(new Set());
  const { visitedIds, wantIds, favIds, todayIds, error: badgeError, reload } = useDiaryBadges();
  const alive = useRef(true);

  const reloadAll = async (allow?: () => boolean) => {
    const [catalog, visitRows, trips] = await Promise.all([loadPlaces(), loadVisits(), loadTrips()]);
    if (allow && !allow()) {
      return;
    }
    const activeId = loadActiveTripId();
    setPlaces(catalog);
    setVisits(visitRows);
    setTrip(trips.find((row) => row.id === activeId) ?? trips[0] ?? null);
    setLoadError(null);
    setRefreshError(null);
  };

  const afterStamp = () => {
    void reload();
    void reloadAll(() => alive.current).catch(() => {
      if (alive.current) {
        setRefreshError("Přehled se nepodařilo obnovit.");
      }
    });
  };

  useEffect(() => {
    alive.current = true;
    let cancelled = false;
    void (async () => {
      try {
        await reloadAll(() => !cancelled && alive.current);
      } catch {
        if (!cancelled && alive.current) {
          setLoadError("Dnešní přehled se nepodařilo načíst.");
        }
      }
    })();
    return () => {
      cancelled = true;
      alive.current = false;
    };
  }, [location.pathname]);

  useEffect(() => {
    if (location.hash !== "#kraje") {
      return;
    }
    document.getElementById("kraje")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [location.hash, places]);

  const [origin] = useState(() => loadStoredMapView());
  const today = todayIsoDate();
  const last = useMemo(() => lastActiveVisit(visits ?? []), [visits]);
  const lastPlace = last ? (places ?? []).find((place) => place.id === last.place_id) : undefined;
  const nearby = useMemo(
    () => nearbyUnvisited(places ?? [], origin, origin?.radiusKm ?? DEFAULT_RADIUS_KM, visits ?? [], 3, mood),
    [places, origin, visits, mood],
  );
  const regions = useMemo(() => regionProgress(places ?? [], visits ?? []), [places, visits]);
  const visitedRegionIds = useMemo(
    () => new Set(regions.filter((row) => row.unlocked).map((row) => row.region.id)),
    [regions],
  );
  const tripPlaceIds = useMemo(() => new Set(trip?.stops.map((stop) => stop.place_id) ?? []), [trip]);
  const discover = useMemo(
    () =>
        pickDiscoverToday(places ?? [], visits ?? [], origin, origin?.radiusKm ?? DEFAULT_RADIUS_KM, today, skipIds, {
          tripPlaceIds,
          visitedRegionIds,
          month: Number(today.slice(5, 7)),
        }, mood),
    [places, visits, origin, today, skipIds, tripPlaceIds, visitedRegionIds, mood],
  );
  const discoverKm =
    discover && origin && hasGps(discover)
      ? haversineKm(origin.latitude, origin.longitude, discover.location.latitude, discover.location.longitude)
      : null;
  const collections = useMemo(() => collectionStats(places ?? [], visits ?? []), [places, visits]);
  const uniqueCount = uniqueVisitedPlaceIds(visits ?? []).size;
  const poolSize = discoverPool(places ?? [], visits ?? [], origin, origin?.radiusKm ?? DEFAULT_RADIUS_KM, mood).length;

  const shuffleDiscover = () => {
    if (!discover) {
      return;
    }
    setSkipIds((current) => {
      const next = new Set(current);
      next.add(discover.id);
      if (next.size >= poolSize) {
        return new Set();
      }
      return next;
    });
  };

  if (loadError) {
    return (
      <p className="error" role="alert">
        {loadError}
      </p>
    );
  }

  if (places === null || visits === null) {
    return <p className="muted">Načítám dnešek…</p>;
  }

  if (places.length === 0) {
    return (
      <section className="empty-state">
        <h1>Dnes</h1>
        <p>Nejdřív nahrajte katalog z PC. Pak tu bude okolí, razítka a kraje.</p>
        <FirstRunCoach catalogLink />
        <p>
          <Link to="/import" className="text-link">
            Nastavení
          </Link>
        </p>
      </section>
    );
  }

  return (
    <section className="today-page">
      <header className="page-header">
        <h1>Dnes</h1>
        <p className="muted">
          {uniqueCount} {czechCountWord(uniqueCount, "místo", "místa", "míst")} v deníku
          {origin ? ` · okolí ${origin.label}` : ""}
        </p>
      </header>
      {refreshError ? (
        <p className="error" role="alert">
          {refreshError}
        </p>
      ) : null}
      {badgeError ? (
        <p className="error" role="alert">
          {badgeError}
        </p>
      ) : null}

      <div className="mood-chips" role="group" aria-label="Nálada dne">
        {TODAY_MOODS.map((item) => (
          <Link
            key={item.id || "all"}
            to={item.id ? `/?mood=${item.id}` : "/"}
            className={mood === item.id ? "chip chip-active" : "chip"}
          >
            {item.label}
          </Link>
        ))}
      </div>

      <NearPlacePrompt places={places} visits={visits} stampedTodayIds={todayIds} onStamped={afterStamp} />

      {last && lastPlace ? (
        <section className="today-block">
          <h2>Poslední návštěva</h2>
          <PlaceCard
            place={lastPlace}
            to={`/place/${lastPlace.id}?from=today`}
            eyebrow={formatVisitDate(last.visited_at)}
            visited
            want={wantIds.has(lastPlace.id)}
            favorite={favIds.has(lastPlace.id)}
          />
        </section>
      ) : (
        <section className="today-block">
          <h2>Poslední návštěva</h2>
          <p className="muted">Zatím žádná. Až budete na místě, dejte razítko Byl jsem tady.</p>
        </section>
      )}

      {discover ? (
        <section className="today-block">
          <h2>Objevte dnes</h2>
          <PlaceCard
            place={discover}
            to={`/place/${discover.id}?from=today`}
            visited={visitedIds.has(discover.id)}
            want={wantIds.has(discover.id)}
            favorite={favIds.has(discover.id)}
            metaExtra={discoverKm != null ? `${discoverKm.toFixed(1)} km` : undefined}
          />
          <div className="today-actions">
            <StampButton
              placeId={discover.id}
              alreadyToday={Boolean(visitOnDate(visits.filter((row) => row.place_id === discover.id), today))}
              onStamped={afterStamp}
            />
            <button type="button" className="ghost" onClick={shuffleDiscover}>
              Jiné místo
            </button>
          </div>
        </section>
      ) : null}

      <section className="today-block">
        <h2>Poblíž a nenavštívené</h2>
        {origin == null ? (
          <p className="muted">
            Na záložce <Link to="/map">Mapa</Link> nastavte polohu. Sem se doplní tři nejbližší místa, kde ještě
            nebylo razítko.
          </p>
        ) : nearby.length === 0 ? (
          <p className="muted">V okruhu {origin.radiusKm} km od {origin.label} už nic nezbývá — nebo chybí GPS.</p>
        ) : (
          <div className="place-cards">
            {nearby.map((hit) => (
              <PlaceCard
                key={hit.place.id}
                place={hit.place}
                to={`/place/${hit.place.id}?from=today`}
                want={wantIds.has(hit.place.id)}
                favorite={favIds.has(hit.place.id)}
                metaExtra={`${hit.km.toFixed(1)} km`}
              />
            ))}
          </div>
        )}
      </section>

      {trip ? (
        <TripToday
          trip={trip}
          placesById={new Map((places ?? []).map((place) => [place.id, place]))}
          visits={visits}
          today={today}
          here={origin}
          onStamped={afterStamp}
        />
      ) : null}

      {visits.some((visit) => visit.visited_at === today) || trip ? (
        <section className="today-block">
          <PhotoIntake places={places} />
        </section>
      ) : null}

      <CzechRegionsMap rows={regions} />

      <ul className="collection-stats" aria-label="Sbírky">
        {collections.map((row) => (
          <li key={row.id}>
            <strong>{row.title}</strong>
            <span className="muted">
              {row.visited}/{row.total || "—"}
            </span>
          </li>
        ))}
      </ul>

      <p className="muted small">
        <Link to="/catalog">Celý katalog</Link>
        {" · "}
        <Link to="/import">Nastavení</Link>
      </p>
    </section>
  );
}
