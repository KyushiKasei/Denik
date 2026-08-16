import { Link } from "react-router-dom";
import { appleMapsDirectionsUrl, googleMapsDirectionsUrl, mapyCzDirectionsUrl, type LatLon } from "../geo/directions";

interface RouteLinksProps {
  dest: LatLon;
  destName?: string;
  origin: LatLon | null;
  promptMap?: boolean;
  showHint?: boolean;
}

export function RouteLinks({ dest, destName, origin, promptMap = false, showHint = true }: RouteLinksProps) {
  const mapy = mapyCzDirectionsUrl(origin, dest);
  const apple = appleMapsDirectionsUrl(origin, dest, destName);
  const google = googleMapsDirectionsUrl(origin, dest);
  if (!mapy && !apple && !google) {
    return null;
  }
  return (
    <div className="route-links">
      <p className="map-links nearby-row-links route-links-row">
        {mapy ? (
          <a href={mapy} target="_blank" rel="noreferrer">
            Trasa Mapy.cz
          </a>
        ) : null}
        {apple ? (
          <a href={apple} target="_blank" rel="noreferrer">
            Apple Maps
          </a>
        ) : null}
        {google ? (
          <a href={google} target="_blank" rel="noreferrer">
            Google Maps
          </a>
        ) : null}
      </p>
      {showHint ? <p className="muted small">Trasa vede v Mapy.cz / Apple Maps, ne v této aplikaci.</p> : null}
      {!origin && promptMap ? (
        <p className="muted small">
          Pro výchozí bod nastavte polohu na <Link to="/map">Mapě</Link>, nebo otevřete jen cíl.
        </p>
      ) : null}
    </div>
  );
}

