import { useEffect, useRef } from "react";
import { Circle, CircleMarker, MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Link } from "react-router-dom";
import type { NearbyHit } from "../geo/nearby";
import type { GeoOrigin } from "../geo/origin";
import "../map/leafletIcon";

export interface LiveGpsPosition {
  latitude: number;
  longitude: number;
  accuracy: number | null;
}

function FitView({ origin, radiusKm }: { origin: GeoOrigin; radiusKm: number }) {
  const map = useMap();
  useEffect(() => {
    const circle = L.circle([origin.latitude, origin.longitude], { radius: radiusKm * 1000 });
    map.fitBounds(circle.getBounds(), { padding: [20, 20] });
    const timer = window.setTimeout(() => map.invalidateSize(), 80);
    return () => window.clearTimeout(timer);
  }, [map, origin.latitude, origin.longitude, radiusKm]);
  return null;
}

function PanTo({ position, nonce }: { position: LiveGpsPosition | null; nonce: number }) {
  const map = useMap();
  useEffect(() => {
    if (nonce < 1 || !position) {
      return;
    }
    map.setView([position.latitude, position.longitude]);
  }, [map, position, nonce]);
  return null;
}

function markerColor(hit: NearbyHit, visitedIds: Set<string>, wantIds: Set<string>): string {
  if (visitedIds.has(hit.place.id)) {
    return "#3d5a40";
  }
  if (wantIds.has(hit.place.id)) {
    return "#c9a227";
  }
  return "#6a6258";
}

interface NearbyMapProps {
  origin: GeoOrigin;
  radiusKm: number;
  hits: NearbyHit[];
  visitedIds: Set<string>;
  wantIds: Set<string>;
  liveGps?: LiveGpsPosition | null;
  panNonce?: number;
  onTileError?: () => void;
}

export function NearbyMap({
  origin,
  radiusKm,
  hits,
  visitedIds,
  wantIds,
  liveGps = null,
  panNonce = 0,
  onTileError,
}: NearbyMapProps) {
  const onTileErrorRef = useRef(onTileError);
  onTileErrorRef.current = onTileError;

  return (
    <div className="nearby-map" aria-label="Mapa okolí">
      <MapContainer
        center={[origin.latitude, origin.longitude]}
        zoom={10}
        scrollWheelZoom
        className="nearby-map-canvas"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          eventHandlers={{
            tileerror: () => onTileErrorRef.current?.(),
          }}
        />
        <FitView origin={origin} radiusKm={radiusKm} />
        <PanTo position={liveGps} nonce={panNonce} />
        <Circle
          center={[origin.latitude, origin.longitude]}
          radius={radiusKm * 1000}
          pathOptions={{ color: "#3d5a40", fillOpacity: 0.08 }}
        />
        <Marker position={[origin.latitude, origin.longitude]}>
          <Popup>Tady · {origin.label}</Popup>
        </Marker>
        {liveGps ? (
          <>
            {liveGps.accuracy != null && liveGps.accuracy > 0 ? (
              <Circle
                center={[liveGps.latitude, liveGps.longitude]}
                radius={liveGps.accuracy}
                pathOptions={{ color: "#1d4ed8", fillOpacity: 0.08, weight: 1 }}
              />
            ) : null}
            <CircleMarker
              center={[liveGps.latitude, liveGps.longitude]}
              radius={6}
              pathOptions={{ color: "#1d4ed8", fillColor: "#3b82f6", fillOpacity: 0.95 }}
            >
              <Popup>Moje poloha</Popup>
            </CircleMarker>
          </>
        ) : null}
        {hits.map((hit) =>
          hit.place.location.latitude != null && hit.place.location.longitude != null ? (
            <CircleMarker
              key={hit.place.id}
              center={[hit.place.location.latitude, hit.place.location.longitude]}
              radius={7}
              pathOptions={{
                color: markerColor(hit, visitedIds, wantIds),
                fillColor: markerColor(hit, visitedIds, wantIds),
                fillOpacity: 0.9,
              }}
            >
              <Popup>
                <Link to={`/place/${hit.place.id}?from=map`} state={{ from: "map" }}>
                  {hit.place.name}
                </Link>
                <br />
                {hit.km.toFixed(1)} km
              </Popup>
            </CircleMarker>
          ) : null,
        )}
      </MapContainer>
    </div>
  );
}
