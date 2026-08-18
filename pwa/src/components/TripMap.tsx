import { useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Link } from "react-router-dom";
import type { CatalogPlace } from "../catalog/types";
import { OSM_TILE_ATTRIBUTION, OSM_TILE_URL } from "../geo/tileStatus";
import "../map/leafletIcon";
import { orderedStops } from "../diary/tripPlan";
import type { StoredTrip } from "../diary/types";

function FitStops({ points }: { points: Array<[number, number]> }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) {
      return;
    }
    const layout = () => {
      map.invalidateSize();
      if (points.length === 1 && points[0]) {
        map.setView(points[0], 12);
        return;
      }
      map.fitBounds(L.latLngBounds(points), { padding: [24, 24], maxZoom: 12 });
    };
    layout();
    const timer = window.setTimeout(layout, 80);
    return () => window.clearTimeout(timer);
  }, [map, points]);
  return null;
}

function stopIcon(index: number): L.DivIcon {
  return L.divIcon({
    className: "trip-stop-icon",
    html: `<span>${index + 1}</span>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });
}

export function TripMap({
  trip,
  placesById,
  onTileError,
}: {
  trip: StoredTrip;
  placesById: Map<string, CatalogPlace>;
  onTileError?: () => void;
}) {
  const points = useMemo(() => {
    const coords: Array<[number, number]> = [];
    if (trip.origin) {
      coords.push([trip.origin.latitude, trip.origin.longitude]);
    }
    for (const stop of orderedStops(trip)) {
      const place = placesById.get(stop.place_id);
      if (place?.location.latitude != null && place.location.longitude != null) {
        coords.push([place.location.latitude, place.location.longitude]);
      }
    }
    return coords;
  }, [trip, placesById]);

  if (points.length === 0) {
    return <p className="muted">Zastávky zatím nemají GPS — mapa se ukáže po doplnění souřadnic.</p>;
  }

  const center = points[0] ?? [49.8, 15.5];
  const line = points.length >= 2 ? points : [];

  return (
    <div className="nearby-map trip-map" aria-label="Mapa výletu">
      <MapContainer center={center} zoom={9} scrollWheelZoom className="nearby-map-canvas">
        <TileLayer
          attribution={OSM_TILE_ATTRIBUTION}
          url={OSM_TILE_URL}
          maxZoom={19}
          eventHandlers={{
            tileerror: () => onTileError?.(),
          }}
        />
        <FitStops points={points} />
        {line.length > 0 ? <Polyline positions={line} pathOptions={{ color: "#3d5a40", weight: 3 }} /> : null}
        {trip.origin ? (
          <CircleMarker
            center={[trip.origin.latitude, trip.origin.longitude]}
            radius={6}
            pathOptions={{ color: "#1d4ed8", fillColor: "#3b82f6", fillOpacity: 0.9 }}
          >
            <Popup>{trip.origin.label || "Start"}</Popup>
          </CircleMarker>
        ) : null}
        {orderedStops(trip).map((stop, index) => {
          const place = placesById.get(stop.place_id);
          if (!place || place.location.latitude == null || place.location.longitude == null) {
            return null;
          }
          return (
            <Marker
              key={`${stop.place_id}-${stop.sort_order}`}
              position={[place.location.latitude, place.location.longitude]}
              icon={stopIcon(index)}
            >
              <Popup>
                <div className="map-popup">
                  <Link to={`/place/${place.id}?from=diary`}>{index + 1}. {place.name}</Link>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}
