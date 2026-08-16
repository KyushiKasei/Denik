import { MapContainer, Marker, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "../map/leafletIcon";

interface PlaceMapProps {
  latitude: number;
  longitude: number;
  name: string;
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
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Marker position={[latitude, longitude]} />
      </MapContainer>
    </div>
  );
}
