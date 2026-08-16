export interface LatLon {
  latitude: number;
  longitude: number;
}

function validCoord(point: LatLon | null | undefined): point is LatLon {
  if (!point) {
    return false;
  }
  return (
    Number.isFinite(point.latitude) &&
    Number.isFinite(point.longitude) &&
    point.latitude >= -90 &&
    point.latitude <= 90 &&
    point.longitude >= -180 &&
    point.longitude <= 180
  );
}

/** Mapy.cz: start/end jako lon,lat (pořadí Seznamu). */
export function mapyCzDirectionsUrl(origin: LatLon | null, dest: LatLon): string | null {
  if (!validCoord(dest)) {
    return null;
  }
  const end = `${dest.longitude},${dest.latitude}`;
  if (validCoord(origin)) {
    return `https://mapy.cz/fnc/v1/route?start=${origin.longitude},${origin.latitude}&end=${end}`;
  }
  return `https://mapy.cz/fnc/v1/route?end=${end}`;
}

export function appleMapsDirectionsUrl(origin: LatLon | null, dest: LatLon, destName?: string): string | null {
  if (!validCoord(dest)) {
    return null;
  }
  const daddr = `${dest.latitude},${dest.longitude}`;
  const params = new URLSearchParams();
  if (validCoord(origin)) {
    params.set("saddr", `${origin.latitude},${origin.longitude}`);
  }
  params.set("daddr", daddr);
  if (destName?.trim()) {
    params.set("q", destName.trim());
  }
  return `https://maps.apple.com/?${params.toString()}`;
}

export function googleMapsDirectionsUrl(origin: LatLon | null, dest: LatLon): string | null {
  if (!validCoord(dest)) {
    return null;
  }
  const params = new URLSearchParams({ api: "1", destination: `${dest.latitude},${dest.longitude}` });
  if (validCoord(origin)) {
    params.set("origin", `${origin.latitude},${origin.longitude}`);
  }
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}
