import { useEffect, useRef } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Link } from "react-router-dom";
import { OSM_TILE_ATTRIBUTION, OSM_TILE_URL } from "../geo/tileStatus";
import "../map/leafletIcon";
import type { AtlasPlace } from "../diary/atlas";
import { WANT_WAX, waxColorForRegion } from "../diary/stampArt";
import { StampButton } from "./StampButton";

const CZECH_BOUNDS = L.latLngBounds([
  [48.55, 12.09],
  [51.06, 18.86],
]);

function markerColor(row: AtlasPlace): string {
  if (row.kind === "visited") {
    return waxColorForRegion(row.place.location.region);
  }
  if (row.kind === "want") {
    return WANT_WAX;
  }
  return "#6a6258";
}

function FitAtlas({ rows }: { rows: AtlasPlace[] }) {
  const map = useMap();
  useEffect(() => {
    const layout = () => {
      map.invalidateSize();
      const withGps = rows.filter(
        (row) => row.place.location.latitude != null && row.place.location.longitude != null,
      );
      if (withGps.length === 0) {
        map.fitBounds(CZECH_BOUNDS, { padding: [20, 20] });
        return;
      }
      const bounds = L.latLngBounds(
        withGps.map((row) => [row.place.location.latitude as number, row.place.location.longitude as number]),
      );
      map.fitBounds(bounds.pad(0.12), { padding: [20, 20], maxZoom: 11 });
    };
    layout();
    const timer = window.setTimeout(layout, 80);
    return () => window.clearTimeout(timer);
  }, [map, rows]);
  return null;
}

export function AtlasMap({
  rows,
  fitRows,
  activePlaceId,
  stampedTodayIds,
  onTileError,
  onVisitStamped,
}: {
  rows: AtlasPlace[];
  fitRows?: AtlasPlace[];
  activePlaceId?: string | null;
  stampedTodayIds: Set<string>;
  onTileError?: () => void;
  onVisitStamped?: () => void;
}) {
  const onTileErrorRef = useRef(onTileError);
  onTileErrorRef.current = onTileError;

  return (
    <div className="nearby-map atlas-map" aria-label="Atlas Česka">
      <MapContainer center={[49.8, 15.5]} zoom={7} scrollWheelZoom className="nearby-map-canvas">
        <TileLayer
          attribution={OSM_TILE_ATTRIBUTION}
          url={OSM_TILE_URL}
          maxZoom={19}
          eventHandlers={{
            tileerror: () => onTileErrorRef.current?.(),
          }}
        />
        <FitAtlas rows={fitRows ?? rows} />
        {rows.map((row) =>
          row.place.location.latitude != null && row.place.location.longitude != null ? (
            <CircleMarker
              key={row.place.id}
              center={[row.place.location.latitude, row.place.location.longitude]}
              radius={row.place.id === activePlaceId ? 11 : row.kind === "visited" ? 8 : 6}
              pathOptions={{
                color: markerColor(row),
                fillColor: markerColor(row),
                fillOpacity: row.kind === "other" ? 0.45 : 0.92,
                weight: row.place.id === activePlaceId ? 3 : row.kind === "visited" ? 2 : 1,
              }}
            >
              <Popup>
                <div className="map-popup">
                  <Link to={`/place/${row.place.id}?from=map`} state={{ from: "map" }}>
                    {row.place.name}
                  </Link>
                  <StampButton
                    placeId={row.place.id}
                    alreadyToday={stampedTodayIds.has(row.place.id)}
                    size="compact"
                    onStamped={() => onVisitStamped?.()}
                  />
                </div>
              </Popup>
            </CircleMarker>
          ) : null,
        )}
      </MapContainer>
    </div>
  );
}
