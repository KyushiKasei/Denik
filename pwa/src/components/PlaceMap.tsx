import { useEffect } from "react";
import { MapContainer, Marker, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { OSM_TILE_ATTRIBUTION, OSM_TILE_URL } from "../geo/tileStatus";
import "../map/leafletIcon";

interface PlaceMapProps {
  latitude: number;
  longitude: number;
  name: string;
}

function InvalidateSize() {
  const map = useMap();
  useEffect(() => {
    const timer = window.setTimeout(() => map.invalidateSize(), 80);
    return () => window.clearTimeout(timer);
  }, [map]);
  return null;
}

export function PlaceMap({ latitude, longitude, name }: PlaceMapProps) {
  return (
    <div className="place-map" aria-label={`Mapa: ${name}`}>
      <MapContainer
        key={`${latitude},${longitude}`}
        center={[latitude, longitude]}
        zoom={14}
        scrollWheelZoom={false}
        className="place-map-canvas"
      >
        <TileLayer
          attribution={OSM_TILE_ATTRIBUTION}
          url={OSM_TILE_URL}
          maxZoom={19}
        />
        <InvalidateSize />
        <Marker position={[latitude, longitude]} />
      </MapContainer>
    </div>
  );
}
