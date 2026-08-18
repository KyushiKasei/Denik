import type { CatalogPlace } from "../catalog/types";

export function similarPlaces(
  place: CatalogPlace,
  catalog: CatalogPlace[],
  visits: { place_id: string; deleted_at: string | null }[],
  limit = 5,
): CatalogPlace[] {
  const visited = new Set(visits.filter((visit) => !visit.deleted_at).map((visit) => visit.place_id));
  const typeSet = new Set(place.types);
  const scored: Array<{ place: CatalogPlace; score: number }> = [];
  for (const other of catalog) {
    if (other.id === place.id || visited.has(other.id)) {
      continue;
    }
    let score = 0;
    let sharedTypes = 0;
    for (const code of other.types) {
      if (typeSet.has(code)) {
        sharedTypes += 1;
        score += 3;
      }
    }
    if (sharedTypes === 0) {
      continue;
    }
    if (place.location.region && other.location.region === place.location.region) {
      score += 2;
    }
    const style = (place.architectural_style || "").trim().toLocaleLowerCase("cs");
    const otherStyle = (other.architectural_style || "").trim().toLocaleLowerCase("cs");
    if (style && otherStyle && style === otherStyle) {
      score += 2;
    }
    if (
      place.inception_year != null &&
      other.inception_year != null &&
      Math.abs(place.inception_year - other.inception_year) <= 120
    ) {
      score += 1;
    }
    if (place.heritage_status === "NKP" && other.heritage_status === "NKP") {
      score += 1;
    }
    if (place.unesco && other.unesco) {
      score += 1;
    }
    if (score <= 0) {
      continue;
    }
    scored.push({ place: other, score });
  }
  scored.sort(
    (a, b) => b.score - a.score || a.place.name.localeCompare(b.place.name, "cs"),
  );
  return scored.slice(0, limit).map((row) => row.place);
}
