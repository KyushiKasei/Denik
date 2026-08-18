import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { CatalogPlace, PlaceNameSnapshot, StoredVisit } from "../catalog/types";
import { locationLine } from "../catalog/labels";
import { HoursBadge } from "./HoursBadge";
import { RouteLinks } from "./RouteLinks";
import { TripExports } from "./TripExports";
import { dateAtNoon, isClosedOnDate } from "../catalog/openingHours";
import { completeTrip, tripStatusLabel } from "../diary/completeTrip";
import { todayIsoDate } from "../diary/ids";
import {
  createTrip,
  loadActiveTripId,
  loadTrips,
  loadVisits,
  moveTripStop,
  removeStopFromTrip,
  saveActiveTripId,
  softDeleteTrip,
  updateTrip,
} from "../diary/store";
import { consecutiveStopKm, orderedStops, tripAirKm } from "../diary/tripPlan";
import { defaultTripName, formatVisitDate, resolvePlaceRef } from "../diary/timeline";
import type { StoredTrip } from "../diary/types";
import { WeekendPlanner } from "./WeekendPlanner";
import { TripMap } from "./TripMap";
import { reorderPlaceIds } from "../diary/weekendPlan";
import { useDiaryBadges } from "../diary/useDiaryBadges";

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
  const [name, setName] = useState(() => defaultTripName(todayIsoDate()));
  const [plannedOn, setPlannedOn] = useState(todayIsoDate());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [visits, setVisits] = useState<StoredVisit[]>([]);
  const [activeId, setActiveId] = useState(loadActiveTripId());
  const { wantIds } = useDiaryBadges();
  const alive = useRef(true);
  const busyLock = useRef(false);

  const reload = async (allow = () => true) => {
    const [nextTrips, nextVisits] = await Promise.all([loadTrips(), loadVisits()]);
    if (!allow()) {
      return;
    }
    setTrips(nextTrips);
    setVisits(nextVisits);
    setActiveId(loadActiveTripId());
  };

  useEffect(() => {
    alive.current = true;
    let cancelled = false;
    void (async () => {
      try {
        await reload(() => !cancelled);
      } catch {
        if (!cancelled) {
          setError("Výlety se nepodařilo načíst.");
        }
      }
    })();
    return () => {
      cancelled = true;
      alive.current = false;
    };
  }, []);

  const runAction = async (fn: () => Promise<void>, fallback: string) => {
    if (busyLock.current) {
      return;
    }
    busyLock.current = true;
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      if (alive.current) {
        setError(err instanceof Error ? err.message : fallback);
      }
    } finally {
      busyLock.current = false;
      if (alive.current) {
        setBusy(false);
      }
    }
  };

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
    if (busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const trip = await createTrip({ name, planned_on: plannedOn || null });
      setActiveId(trip.id);
      await reload();
      openTrip(trip.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Výlet se nepodařilo založit.");
    } finally {
      setBusy(false);
    }
  };

  if (trips === null) {
    if (error) {
      return (
        <p className="error" role="alert">
          {error}
        </p>
      );
    }
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
          {` · ${tripStatusLabel(selected.status)}`}
          {activeId === selected.id ? " · aktivní" : ""}
        </p>
        {selected.notes ? <p>{selected.notes}</p> : null}
        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : null}
        {stops.some((stop) => placesById.get(stop.place_id)?.location.latitude != null) ? (
          <TripMap trip={selected} placesById={placesById} />
        ) : null}
        <TripExports trip={selected} placesById={placesById} />
        <div className="actions-row print-only-hide">
          <button
            type="button"
            className="ghost"
            disabled={busy}
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
            disabled={busy}
            onClick={() => {
              void runAction(async () => {
                await completeTrip(selected, placesById, visits, todayIsoDate());
                await reload();
              }, "Výlet se nepodařilo uzavřít.");
            }}
          >
            {busy ? "Pracuji…" : "Uzavřít výlet"}
          </button>
          {stops.length >= 2 ? (
            <button
              type="button"
              className="ghost"
              disabled={busy}
              onClick={() => {
                void runAction(async () => {
                  const ordered = reorderPlaceIds(
                    stops.map((stop) => stop.place_id),
                    placesById,
                    selected.origin,
                  );
                  await updateTrip(selected.id, {
                    stops: ordered.map((place_id, sort_order) => ({
                      place_id,
                      sort_order,
                      note: stops.find((stop) => stop.place_id === place_id)?.note ?? null,
                    })),
                  });
                  await reload();
                }, "Pořadí se nepodařilo seřadit.");
              }}
            >
              Seřadit podle vzdálenosti
            </button>
          ) : null}
          <button
            type="button"
            className="ghost"
            disabled={busy}
            onClick={() => {
              void runAction(async () => {
                if (!window.confirm("Smazat tento výlet? Záznam zůstane v deníku jako smazaný.")) {
                  return;
                }
                await softDeleteTrip(selected.id);
                await reload();
                openTrip(null);
              }, "Výlet se nepodařilo smazat.");
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
              const when = selected.planned_on ? dateAtNoon(selected.planned_on) : new Date();
              const closed = place ? isClosedOnDate(place, when) : false;
              return (
                <li key={`${stop.place_id}-${stop.sort_order}`}>
                  <div className="place-row">
                    <span className="place-row-title">
                      {index + 1}. {ref.name}
                      {place ? <HoursBadge place={place} at={when} /> : null}
                    </span>
                    <span className="place-row-meta">
                      {place ? locationLine(place) : ref.municipality || ""}
                      {ref.missingFromCatalog ? " · mimo katalog" : ""}
                      {closed ? " · ten den zavřeno" : ""}
                    </span>
                    <div className="actions-row">
                      <Link to={`/place/${stop.place_id}?from=diary`} className="text-link">
                        Detail
                      </Link>
                      <button
                        type="button"
                        className="ghost"
                        disabled={busy || index === 0}
                        aria-label={`Posunout ${ref.name} nahoru`}
                        onClick={() => {
                          void runAction(async () => {
                            await moveTripStop(selected.id, stop.place_id, -1);
                            await reload();
                          }, "Pořadí se nepodařilo změnit.");
                        }}
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        className="ghost"
                        disabled={busy || index === stops.length - 1}
                        aria-label={`Posunout ${ref.name} dolů`}
                        onClick={() => {
                          void runAction(async () => {
                            await moveTripStop(selected.id, stop.place_id, 1);
                            await reload();
                          }, "Pořadí se nepodařilo změnit.");
                        }}
                      >
                        ↓
                      </button>
                      <button
                        type="button"
                        className="ghost"
                        disabled={busy}
                        onClick={() => {
                          void runAction(async () => {
                            await removeStopFromTrip(selected.id, stop.place_id);
                            await reload();
                          }, "Zastávku se nepodařilo odebrat.");
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
              void runAction(async () => {
                await updateTrip(selected.id, { notes: value });
                await reload();
              }, "Poznámku k výletu se nepodařilo uložit.");
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
        <button type="submit" disabled={busy}>
          {busy ? "Zakládám…" : "Nový výlet"}
        </button>
      </form>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <WeekendPlanner
        places={[...placesById.values()]}
        wantIds={wantIds}
        onCreated={(id) => {
          void reload().then(() => openTrip(id));
        }}
      />
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
                  {` · ${tripStatusLabel(trip.status)}`}
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
