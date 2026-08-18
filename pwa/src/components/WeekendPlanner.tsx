import { useMemo, useState } from "react";
import type { CatalogPlace } from "../catalog/types";
import { uniqueSorted } from "../catalog/filterPlaces";
import { HoursBadge } from "./HoursBadge";
import { createTripFromPlaces } from "../diary/store";
import { todayIsoDate } from "../diary/ids";
import { dateAtNoon } from "../catalog/openingHours";
import {
  clampWeekendStops,
  suggestWeekendPlaces,
  WEEKEND_DEFAULT_RADIUS_KM,
  WEEKEND_DEFAULT_STOPS,
  WEEKEND_MAX_STOPS,
  WEEKEND_MIN_STOPS,
  weekendCandidates,
  weekendClosedSkipped,
} from "../diary/weekendPlan";
import { loadStoredMapView } from "../geo/mapOriginStore";
import { DEFAULT_RADIUS_KM, MAX_RADIUS_KM, MIN_RADIUS_KM, RADIUS_STEP_KM } from "../geo/haversine";
import type { TripOrigin } from "../diary/types";

export function WeekendPlanner({
  places,
  wantIds,
  onCreated,
}: {
  places: CatalogPlace[];
  wantIds: Set<string>;
  onCreated: (tripId: string) => void;
}) {
  const stored = loadStoredMapView();
  const [stopCount, setStopCount] = useState(WEEKEND_DEFAULT_STOPS);
  const [radiusKm, setRadiusKm] = useState(stored?.radiusKm || WEEKEND_DEFAULT_RADIUS_KM);
  const [region, setRegion] = useState("");
  const [plannedOn, setPlannedOn] = useState(todayIsoDate());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const origin = stored
    ? { latitude: stored.latitude, longitude: stored.longitude, label: stored.label }
    : null;
  const regions = useMemo(() => uniqueSorted(places.map((place) => place.location.region)), [places]);
  const preview = useMemo(
    () =>
      suggestWeekendPlaces({
        places,
        wantIds,
        origin,
        region: region || undefined,
        radiusKm,
        stopCount,
        plannedOn,
      }),
    [places, wantIds, origin, region, radiusKm, stopCount, plannedOn],
  );
  const pool = weekendCandidates({
    places,
    wantIds,
    origin,
    region: region || undefined,
    radiusKm,
    stopCount,
    plannedOn,
  });
  const skipped = weekendClosedSkipped({
    places,
    wantIds,
    origin,
    region: region || undefined,
    radiusKm,
    stopCount,
    plannedOn,
  });
  const when = dateAtNoon(plannedOn);

  const create = async () => {
    if (busy) {
      return;
    }
    if (preview.length < WEEKEND_MIN_STOPS) {
      setError("V okruhu jsou méně než dvě otevřená místa z „chci navštívit“. Přidejte hvězdičky, nebo zvětšete okruh.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const tripOrigin: TripOrigin | null = origin
        ? { latitude: origin.latitude, longitude: origin.longitude, label: origin.label }
        : null;
      const trip = await createTripFromPlaces({
        name: "Víkend",
        planned_on: plannedOn || todayIsoDate(),
        origin: tripOrigin,
        placeIds: preview.map((place) => place.id),
      });
      onCreated(trip.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Výlet se nepodařilo založit.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="weekend-planner">
      <h3>Víkend z „chci navštívit“</h3>
      <p className="muted small">
        {origin
          ? `Od ${origin.label}, vzdušnou čarou, jen místa otevřená v plánovaný den.`
          : "Nejdřív nastavte polohu na záložce Mapa — bez ní se berou místa v kraji abecedně."}
      </p>
      <div className="filters">
        <label>
          Den
          <input type="date" value={plannedOn} onChange={(event) => setPlannedOn(event.target.value)} />
        </label>
        <label>
          Zastávek
          <input
            type="range"
            min={WEEKEND_MIN_STOPS}
            max={WEEKEND_MAX_STOPS}
            value={stopCount}
            onChange={(event) => setStopCount(clampWeekendStops(event.target.value))}
          />
          <span className="muted small">{stopCount}</span>
        </label>
        <label>
          {radiusKm} km
          <input
            type="range"
            min={MIN_RADIUS_KM}
            max={MAX_RADIUS_KM}
            step={RADIUS_STEP_KM}
            value={radiusKm}
            onChange={(event) => setRadiusKm(Number(event.target.value) || DEFAULT_RADIUS_KM)}
          />
        </label>
        <label>
          Kraj
          <select value={region} onChange={(event) => setRegion(event.target.value)}>
            <option value="">Kdekoli</option>
            {regions.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {skipped.length > 0 ? (
        <p className="muted small">Vyřazeno kvůli zavření: {skipped.map((place) => place.name).join(", ")}.</p>
      ) : null}
      {wantIds.size === 0 ? (
        <p className="muted">Nejdřív označte místa jako Chci navštívit.</p>
      ) : preview.length === 0 ? (
        <p className="muted">V tomhle okruhu nic otevřeného z wishlistu není ({pool.length} kandidátů).</p>
      ) : (
        <ol className="trip-stops">
          {preview.map((place, index) => (
            <li key={place.id}>
              {index + 1}. {place.name}
              {place.location.municipality ? ` · ${place.location.municipality}` : ""}
              <HoursBadge place={place} at={when} />
            </li>
          ))}
        </ol>
      )}
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <button type="button" onClick={() => void create()} disabled={busy || preview.length < WEEKEND_MIN_STOPS}>
        {busy ? "Zakládám…" : "Založit výlet"}
      </button>
    </section>
  );
}
