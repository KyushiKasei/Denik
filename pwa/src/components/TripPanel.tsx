import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { CatalogPlace, PlaceNameSnapshot } from "../catalog/types";
import { locationLine } from "../catalog/labels";
import { RouteLinks } from "./RouteLinks";
import { todayIsoDate } from "../diary/ids";
import {
  createTrip,
  loadActiveTripId,
  loadTrips,
  moveTripStop,
  removeStopFromTrip,
  saveActiveTripId,
  softDeleteTrip,
  updateTrip,
} from "../diary/store";
import { consecutiveStopKm, orderedStops, tripAirKm } from "../diary/tripPlan";
import { formatVisitDate, resolvePlaceRef } from "../diary/timeline";
import type { StoredTrip } from "../diary/types";

export function TripPanel({
  placesById,
  snapshotsById,
}: {
  placesById: Map<string, CatalogPlace>;
  snapshotsById: Map<string, PlaceNameSnapshot>;
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get("trip");
  const [trips, setTrips] = useState<StoredTrip[] | null>(null);
  const [name, setName] = useState("Výlet");
  const [plannedOn, setPlannedOn] = useState(todayIsoDate());
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState(loadActiveTripId());

  const reload = async () => {
    setTrips(await loadTrips());
    setActiveId(loadActiveTripId());
  };

  useEffect(() => {
    void reload();
  }, []);

  const selected = useMemo(
    () => trips?.find((trip) => trip.id === selectedId) ?? null,
    [trips, selectedId],
  );

  const openTrip = (id: string | null) => {
    const params = new URLSearchParams(searchParams);
    params.set("sec", "trips");
    if (id) {
      params.set("trip", id);
    } else {
      params.delete("trip");
    }
    setSearchParams(params, { replace: true });
  };

  const onCreate = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      const trip = await createTrip({ name, planned_on: plannedOn || null });
      setActiveId(trip.id);
      await reload();
      openTrip(trip.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Výlet se nepodařilo založit.");
    }
  };

  if (trips === null) {
    return <p className="muted">Načítám výlety…</p>;
  }

  if (selected) {
    const stops = orderedStops(selected);
    const gaps = consecutiveStopKm(stops, placesById);
    const totalKm = tripAirKm(selected, placesById);
    return (
      <section className="trip-detail">
        <p className="back">
          <button type="button" className="text-link" onClick={() => openTrip(null)}>
            ← Výlety
          </button>
        </p>
        <h2>{selected.name}</h2>
        <p className="muted">
          {selected.planned_on ? formatVisitDate(selected.planned_on) : "bez data"}
          {totalKm != null ? ` · ${totalKm.toFixed(1)} km vzdušnou čarou` : ""}
          {activeId === selected.id ? " · aktivní" : ""}
        </p>
        {selected.notes ? <p>{selected.notes}</p> : null}
        <div className="actions-row">
          <button
            type="button"
            className="ghost"
            onClick={() => {
              saveActiveTripId(selected.id);
              setActiveId(selected.id);
            }}
          >
            Použít pro přidávání
          </button>
          <button
            type="button"
            className="ghost"
            onClick={async () => {
              if (!window.confirm("Smazat tento výlet? Záznam zůstane v deníku jako smazaný.")) {
                return;
              }
              await softDeleteTrip(selected.id);
              await reload();
              openTrip(null);
            }}
          >
            Smazat výlet
          </button>
        </div>
        {stops.length === 0 ? (
          <p className="muted">Zatím žádná zastávka. Přidejte místo z mapy tlačítkem Na výlet.</p>
        ) : (
          <ol className="trip-stops">
            {stops.map((stop, index) => {
              const ref = resolvePlaceRef(stop.place_id, placesById, snapshotsById);
              const place = placesById.get(stop.place_id);
              const gap = gaps[index];
              return (
                <li key={`${stop.place_id}-${stop.sort_order}`}>
                  <div className="place-row">
                    <span className="place-row-title">
                      {index + 1}. {ref.name}
                    </span>
                    <span className="place-row-meta">
                      {place ? locationLine(place) : ref.municipality || ""}
                      {ref.missingFromCatalog ? " · mimo katalog" : ""}
                    </span>
                    <div className="actions-row">
                      <Link to={`/place/${stop.place_id}?from=diary`} className="text-link">
                        Detail
                      </Link>
                      <button
                        type="button"
                        className="ghost"
                        disabled={index === 0}
                        onClick={async () => {
                          await moveTripStop(selected.id, stop.place_id, -1);
                          await reload();
                        }}
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        className="ghost"
                        disabled={index === stops.length - 1}
                        onClick={async () => {
                          await moveTripStop(selected.id, stop.place_id, 1);
                          await reload();
                        }}
                      >
                        ↓
                      </button>
                      <button
                        type="button"
                        className="ghost"
                        onClick={async () => {
                          await removeStopFromTrip(selected.id, stop.place_id);
                          await reload();
                        }}
                      >
                        Odebrat
                      </button>
                    </div>
                    {place?.location.latitude != null && place.location.longitude != null ? (
                      <RouteLinks
                        dest={{ latitude: place.location.latitude, longitude: place.location.longitude }}
                        destName={place.name}
                        origin={
                          selected.origin
                            ? {
                                latitude: selected.origin.latitude,
                                longitude: selected.origin.longitude,
                              }
                            : null
                        }
                        showHint={false}
                      />
                    ) : null}
                  </div>
                  {gap != null ? <p className="muted small">↓ {gap.toFixed(1)} km vzdušnou čarou</p> : null}
                </li>
              );
            })}
          </ol>
        )}
        <label>
          Poznámka k výletu
          <textarea
            rows={3}
            defaultValue={selected.notes ?? ""}
            onBlur={(event) => {
              const value = event.target.value.trim() || null;
              if (value === (selected.notes ?? null)) {
                return;
              }
              void updateTrip(selected.id, { notes: value }).then(() => reload());
            }}
          />
        </label>
      </section>
    );
  }

  return (
    <section>
      <form className="filters" onSubmit={(event) => void onCreate(event)}>
        <label>
          Název
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <label>
          Datum
          <input type="date" value={plannedOn} onChange={(event) => setPlannedOn(event.target.value)} />
        </label>
        <button type="submit">Nový výlet</button>
      </form>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      {trips.length === 0 ? (
        <p className="muted">Zatím žádný výlet. Založte ho tady, nebo přidejte místo z mapy.</p>
      ) : (
        <ul className="place-list">
          {trips.map((trip) => (
            <li key={trip.id}>
              <button type="button" className="place-row" onClick={() => openTrip(trip.id)}>
                <span className="place-row-title">{trip.name}</span>
                <span className="place-row-meta">
                  {trip.planned_on ? formatVisitDate(trip.planned_on) : "bez data"}
                  {` · ${trip.stops.length} zastávek`}
                  {activeId === trip.id ? " · aktivní" : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
