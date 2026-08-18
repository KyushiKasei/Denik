import type { CatalogPlace } from "./types";
import { hasAmenity } from "./labels";
import { isRuin } from "./ruins";

export type TodayMood = "" | "ruins" | "lookouts" | "indoors" | "heritage";

export const TODAY_MOODS: Array<{ id: TodayMood; label: string }> = [
  { id: "", label: "Vše" },
  { id: "ruins", label: "Zříceniny" },
  { id: "lookouts", label: "Venku s dětmi" },
  { id: "indoors", label: "Interiéry" },
  { id: "heritage", label: "UNESCO / NKP" },
];

const INDOORS_TYPES = new Set(["CASTLE", "CHATEAU", "PALACE", "MANOR"]);
const KIDS_OUTDOOR = new Set(["LOOKOUT_TOWER", "ZOO", "CAVE"]);

export function placeMatchesMood(place: CatalogPlace, mood: TodayMood): boolean {
  if (!mood) {
    return true;
  }
  if (mood === "ruins") {
    return isRuin(place);
  }
  if (mood === "lookouts") {
    return place.types.some((code) => KIDS_OUTDOOR.has(code));
  }
  if (mood === "indoors") {
    return (
      place.types.some((code) => INDOORS_TYPES.has(code)) &&
      !isRuin(place) &&
      place.visitability !== "FREE_ACCESS" &&
      place.condition !== "EXTINCT"
    );
  }
  if (mood === "heritage") {
    return place.unesco || place.heritage_status === "NKP";
  }
  return true;
}

export function parseMoodParam(raw: string | null | undefined): TodayMood {
  const text = String(raw ?? "").trim().toLowerCase();
  if (text === "ruins" || text === "lookouts" || text === "indoors" || text === "heritage") {
    return text;
  }
  return "";
}

/** Filtr zázemí / psa na mapě a v katalogu. */
export type PlaceExtraFilter = "" | "dogs" | "free" | "toilets" | "cafe" | "playground";

export function placeMatchesExtra(place: CatalogPlace, extra: PlaceExtraFilter): boolean {
  if (!extra) {
    return true;
  }
  if (extra === "dogs") {
    const dogs = (place.dogs || "").trim().toLowerCase();
    return dogs === "yes" || dogs === "leashed" || dogs === "outside";
  }
  if (extra === "free") {
    return (place.fee || "").trim().toLowerCase() === "no" || place.visitability === "FREE_ACCESS";
  }
  if (extra === "toilets" || extra === "cafe" || extra === "playground") {
    return hasAmenity(place, extra);
  }
  return true;
}

export function parseExtraParam(raw: string | null | undefined): PlaceExtraFilter {
  const text = String(raw ?? "").trim().toLowerCase();
  if (text === "dogs" || text === "free" || text === "toilets" || text === "cafe" || text === "playground") {
    return text;
  }
  return "";
}
