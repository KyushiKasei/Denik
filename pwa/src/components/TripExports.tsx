import type { CatalogPlace } from "../catalog/types";
import {
  buildTripGpx,
  buildTripIcs,
  downloadTextFile,
  googleMapsMultiStopUrl,
  mapyCzMultiStopUrl,
  tripStopPlaces,
} from "../diary/tripExport";
import type { StoredTrip } from "../diary/types";

export function TripExports({
  trip,
  placesById,
}: {
  trip: StoredTrip;
  placesById: Map<string, CatalogPlace>;
}) {
  const places = tripStopPlaces(trip, placesById);
  const origin = trip.origin
    ? { latitude: trip.origin.latitude, longitude: trip.origin.longitude }
    : null;
  const mapy = mapyCzMultiStopUrl(origin, places);
  const google = googleMapsMultiStopUrl(origin, places);
  const stamp = (trip.planned_on || "vylet").replaceAll("-", "");

  return (
    <div className="trip-exports actions-row print-only-hide">
      <button
        type="button"
        className="ghost"
        onClick={() => downloadTextFile(`${stamp}-${trip.name}.ics`, "text/calendar", buildTripIcs(trip, placesById))}
      >
        Kalendář (ICS)
      </button>
      <button
        type="button"
        className="ghost"
        onClick={() => downloadTextFile(`${stamp}-${trip.name}.gpx`, "application/gpx+xml", buildTripGpx(trip, placesById))}
      >
        GPX
      </button>
      <button type="button" className="ghost" onClick={() => window.print()}>
        Tisk / list dne
      </button>
      {mapy ? (
        <a href={mapy} target="_blank" rel="noreferrer">
          Trasa Mapy.cz
        </a>
      ) : null}
      {google ? (
        <a href={google} target="_blank" rel="noreferrer">
          Trasa Google
        </a>
      ) : null}
    </div>
  );
}
