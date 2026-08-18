import type { CatalogPlace, VisitabilityCode } from "./types";

export type OpenState = "open" | "closed" | "unknown";
export type HoursFilter = "" | "open" | "season";

const DAY_INDEX: Record<string, number> = {
  su: 0,
  mo: 1,
  tu: 2,
  we: 3,
  th: 4,
  fr: 5,
  sa: 6,
};

const MONTH_INDEX: Record<string, number> = {
  jan: 1,
  feb: 2,
  mar: 3,
  apr: 4,
  may: 5,
  jun: 6,
  jul: 7,
  aug: 8,
  sep: 9,
  oct: 10,
  nov: 11,
  dec: 12,
};

const ALWAYS_CLOSED: ReadonlySet<VisitabilityCode> = new Set([
  "CLOSED",
  "EXTINCT",
  "PRIVATE",
  "TEMPORARILY_CLOSED",
]);

const OPEN_WITHOUT_HOURS: ReadonlySet<VisitabilityCode> = new Set(["FREE_ACCESS", "EXTERIOR_ONLY"]);

const WINTER_MONTHS = new Set([11, 12, 1, 2, 3]);

interface HoursRule {
  months: Set<number> | null;
  days: Set<number> | null;
  kind: "off" | "always" | "times";
  intervals: Array<{ start: number; end: number }>;
}

function stripComments(raw: string): string {
  return raw.replace(/"[^"]*"/g, " ").replace(/\s+/g, " ").trim();
}

function minutesFromClock(value: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value.trim());
  if (!match) {
    return null;
  }
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours > 24 || minutes > 59 || (hours === 24 && minutes !== 0)) {
    return null;
  }
  return hours * 60 + minutes;
}

function expandRange(from: number, to: number, modulo: number): number[] {
  const out: number[] = [];
  let cursor = from;
  out.push(cursor);
  while (cursor !== to) {
    cursor = (cursor + 1) % modulo;
    out.push(cursor);
    if (out.length > modulo) {
      break;
    }
  }
  return out;
}

function parseDays(token: string): Set<number> | null {
  const parts = token.split(",").map((item) => item.trim()).filter(Boolean);
  if (parts.length === 0) {
    return null;
  }
  const days = new Set<number>();
  for (const part of parts) {
    const range = part.split("-").map((item) => item.trim().toLowerCase());
    const start = DAY_INDEX[range[0] ?? ""];
    if (start == null) {
      return null;
    }
    if (range.length === 1) {
      days.add(start);
      continue;
    }
    const end = DAY_INDEX[range[1] ?? ""];
    if (end == null) {
      return null;
    }
    for (const day of expandRange(start, end, 7)) {
      days.add(day);
    }
  }
  return days;
}

function parseMonths(token: string): Set<number> | null {
  const range = token.split("-").map((item) => item.trim().toLowerCase());
  const start = MONTH_INDEX[range[0] ?? ""];
  if (start == null) {
    return null;
  }
  const months = new Set<number>();
  if (range.length === 1) {
    months.add(start);
    return months;
  }
  const end = MONTH_INDEX[range[1] ?? ""];
  if (end == null) {
    return null;
  }
  let cursor = start;
  months.add(cursor);
  while (cursor !== end) {
    cursor = cursor === 12 ? 1 : cursor + 1;
    months.add(cursor);
  }
  return months;
}

function parseIntervals(token: string): Array<{ start: number; end: number }> | "off" | "always" | null {
  const lower = token.trim().toLowerCase();
  if (!lower || lower === "off") {
    return "off";
  }
  if (lower === "24/7" || lower === "open") {
    return "always";
  }
  const intervals: Array<{ start: number; end: number }> = [];
  for (const part of token.split(",")) {
    const [fromRaw, toRaw] = part.split("-").map((item) => item.trim());
    const start = minutesFromClock(fromRaw ?? "");
    const end = minutesFromClock(toRaw ?? "");
    if (start == null || end == null) {
      return null;
    }
    intervals.push({ start, end });
  }
  return intervals.length > 0 ? intervals : null;
}

function parseRule(raw: string): HoursRule | null {
  let text = stripComments(raw).replace(/:$/, "").trim();
  if (!text || /^ph\b/i.test(text)) {
    return null;
  }
  if (text.toLowerCase() === "24/7") {
    return { months: null, days: null, kind: "always", intervals: [] };
  }
  if (text.toLowerCase() === "off") {
    return { months: null, days: null, kind: "off", intervals: [] };
  }

  let months: Set<number> | null = null;
  const monthMatch = /^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(?:-(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))?\b/i.exec(
    text,
  );
  if (monthMatch) {
    months = parseMonths(monthMatch[0]);
    text = text.slice(monthMatch[0].length).replace(/^[:\s]+/, "").trim();
  }

  if (!text) {
    return { months, days: null, kind: "always", intervals: [] };
  }
  if (text.toLowerCase() === "off") {
    return { months, days: null, kind: "off", intervals: [] };
  }

  let days: Set<number> | null = null;
  const dayMatch = /^((?:mo|tu|we|th|fr|sa|su)(?:-(?:mo|tu|we|th|fr|sa|su))?(?:\s*,\s*(?:mo|tu|we|th|fr|sa|su)(?:-(?:mo|tu|we|th|fr|sa|su))?)*)\b/i.exec(
    text,
  );
  if (dayMatch) {
    days = parseDays(dayMatch[1] ?? "");
    text = text.slice(dayMatch[0].length).trim();
  }

  const intervals = parseIntervals(text || "00:00-24:00");
  if (intervals == null) {
    return null;
  }
  if (intervals === "off") {
    return { months, days, kind: "off", intervals: [] };
  }
  if (intervals === "always") {
    return { months, days, kind: "always", intervals: [] };
  }
  return { months, days, kind: "times", intervals };
}

export function parseOpeningHours(raw: string | null | undefined): HoursRule[] {
  const text = stripComments(raw ?? "");
  if (!text) {
    return [];
  }
  if (text.toLowerCase() === "24/7") {
    return [{ months: null, days: null, kind: "always", intervals: [] }];
  }
  const rules: HoursRule[] = [];
  for (const part of text.split(";")) {
    const rule = parseRule(part);
    if (rule) {
      rules.push(rule);
    }
  }
  return rules;
}

function ruleMatches(rule: HoursRule, at: Date): boolean {
  const month = at.getMonth() + 1;
  const day = at.getDay();
  if (rule.months && !rule.months.has(month)) {
    return false;
  }
  if (rule.days && !rule.days.has(day)) {
    return false;
  }
  return true;
}

function intervalOpen(intervals: Array<{ start: number; end: number }>, minutes: number): boolean {
  for (const slot of intervals) {
    if (slot.end > slot.start) {
      if (minutes >= slot.start && minutes < slot.end) {
        return true;
      }
    } else if (slot.end < slot.start) {
      if (minutes >= slot.start || minutes < slot.end) {
        return true;
      }
    }
  }
  return false;
}

export function evaluateOpeningHours(raw: string | null | undefined, at: Date): OpenState {
  const rules = parseOpeningHours(raw);
  if (rules.length === 0) {
    return "unknown";
  }
  let state: OpenState = "closed";
  const minutes = at.getHours() * 60 + at.getMinutes();
  for (const rule of rules) {
    if (!ruleMatches(rule, at)) {
      continue;
    }
    if (rule.kind === "off") {
      state = "closed";
      continue;
    }
    if (rule.kind === "always") {
      state = "open";
      continue;
    }
    state = intervalOpen(rule.intervals, minutes) ? "open" : "closed";
  }
  return state;
}

export function isSeasonallyClosed(raw: string | null | undefined, at: Date): boolean {
  const rules = parseOpeningHours(raw);
  if (rules.length === 0) {
    return false;
  }
  const month = at.getMonth() + 1;
  const monthRules = rules.filter((rule) => !rule.months || rule.months.has(month));
  if (monthRules.length === 0) {
    return true;
  }
  return monthRules.every((rule) => rule.kind === "off");
}

const GONE_CONDITIONS = new Set(["RUIN", "REMAINS", "EXTINCT"]);

export function placeOpenState(place: CatalogPlace, at: Date = new Date()): OpenState {
  if (ALWAYS_CLOSED.has(place.visitability)) {
    return "closed";
  }
  const hours = place.osm_opening_hours;
  if (hours) {
    return evaluateOpeningHours(hours, at);
  }
  if (GONE_CONDITIONS.has(place.condition)) {
    return "unknown";
  }
  if (OPEN_WITHOUT_HOURS.has(place.visitability)) {
    return "open";
  }
  return "unknown";
}

export function isInOpenSeason(place: CatalogPlace, at: Date = new Date()): boolean {
  if (ALWAYS_CLOSED.has(place.visitability)) {
    return false;
  }
  if (place.osm_opening_hours) {
    const rules = parseOpeningHours(place.osm_opening_hours);
    const hasSeason = rules.some((rule) => rule.months != null);
    if (!hasSeason) {
      return false;
    }
    return !isSeasonallyClosed(place.osm_opening_hours, at);
  }
  if (place.visitability === "SEASONAL") {
    return !WINTER_MONTHS.has(at.getMonth() + 1);
  }
  return false;
}

export function isSeasonallyLikelyClosed(place: CatalogPlace, at: Date = new Date()): boolean {
  if (ALWAYS_CLOSED.has(place.visitability)) {
    return true;
  }
  if (place.osm_opening_hours) {
    return isSeasonallyClosed(place.osm_opening_hours, at);
  }
  if (place.visitability === "SEASONAL" && WINTER_MONTHS.has(at.getMonth() + 1)) {
    return true;
  }
  return false;
}

export const CLOSING_SOON_MINUTES = 90;

export const MONTH_OPTIONS: Array<{ value: number; name_cs: string }> = [
  { value: 1, name_cs: "leden" },
  { value: 2, name_cs: "únor" },
  { value: 3, name_cs: "březen" },
  { value: 4, name_cs: "duben" },
  { value: 5, name_cs: "květen" },
  { value: 6, name_cs: "červen" },
  { value: 7, name_cs: "červenec" },
  { value: 8, name_cs: "srpen" },
  { value: 9, name_cs: "září" },
  { value: 10, name_cs: "říjen" },
  { value: 11, name_cs: "listopad" },
  { value: 12, name_cs: "prosinec" },
];

const DAY_CS = ["ne", "po", "út", "st", "čt", "pá", "so"];
const MONTH_CS: Record<number, string> = {
  1: "led",
  2: "úno",
  3: "bře",
  4: "dub",
  5: "kvě",
  6: "čer",
  7: "čec",
  8: "srp",
  9: "zář",
  10: "říj",
  11: "lis",
  12: "pro",
};

export function dateAtNoon(isoDate: string): Date {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate.trim());
  if (!match) {
    return new Date();
  }
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12, 0, 0);
}

export function evaluateOpeningHoursOnDay(raw: string | null | undefined, at: Date): OpenState {
  const rules = parseOpeningHours(raw);
  if (rules.length === 0) {
    return "unknown";
  }
  let state: OpenState = "closed";
  for (const rule of rules) {
    if (!ruleMatches(rule, at)) {
      continue;
    }
    if (rule.kind === "off") {
      state = "closed";
      continue;
    }
    state = "open";
  }
  return state;
}

export function dayOpenState(place: CatalogPlace, at: Date = new Date()): OpenState {
  if (ALWAYS_CLOSED.has(place.visitability)) {
    return "closed";
  }
  if (place.osm_opening_hours) {
    return evaluateOpeningHoursOnDay(place.osm_opening_hours, at);
  }
  if (OPEN_WITHOUT_HOURS.has(place.visitability)) {
    return "open";
  }
  if (place.visitability === "SEASONAL" && WINTER_MONTHS.has(at.getMonth() + 1)) {
    return "closed";
  }
  return "unknown";
}

export function isClosedOnDate(place: CatalogPlace, at: Date): boolean {
  return dayOpenState(place, at) === "closed";
}

function intervalContains(intervals: Array<{ start: number; end: number }>, minutes: number): number | null {
  for (const slot of intervals) {
    if (slot.end > slot.start) {
      if (minutes >= slot.start && minutes < slot.end) {
        return slot.end;
      }
    } else if (slot.end < slot.start) {
      if (minutes >= slot.start || minutes < slot.end) {
        return slot.end;
      }
    }
  }
  return null;
}

export function minutesUntilClose(raw: string | null | undefined, at: Date): number | null {
  const rules = parseOpeningHours(raw);
  if (rules.length === 0) {
    return null;
  }
  const minutes = at.getHours() * 60 + at.getMinutes();
  let end: number | null = null;
  for (const rule of rules) {
    if (!ruleMatches(rule, at)) {
      continue;
    }
    if (rule.kind === "off") {
      end = null;
      continue;
    }
    if (rule.kind === "always") {
      end = null;
      continue;
    }
    end = intervalContains(rule.intervals, minutes);
  }
  if (end == null) {
    return null;
  }
  let delta = end - minutes;
  if (delta < 0) {
    delta += 24 * 60;
  }
  return delta;
}

export function hoursBadgeLabel(
  state: OpenState,
  extra?: { minutesUntilClose?: number | null },
): string | null {
  if (state === "open") {
    const remaining = extra?.minutesUntilClose;
    if (remaining != null && remaining <= CLOSING_SOON_MINUTES) {
      if (remaining <= 0) {
        return "zavírá teď";
      }
      return `zavírá za ${remaining} min`;
    }
    return "otevřeno";
  }
  if (state === "closed") {
    return "zavřeno";
  }
  return null;
}

function formatClock(minutes: number): string {
  const wrapped = ((minutes % (24 * 60)) + 24 * 60) % (24 * 60);
  const hours = Math.floor(wrapped / 60);
  const mins = wrapped % 60;
  return mins === 0 ? `${hours}:00` : `${hours}:${String(mins).padStart(2, "0")}`;
}

function formatDaySet(days: Set<number> | null): string {
  if (!days || days.size === 0 || days.size === 7) {
    return "denně";
  }
  const ordered = [...days].sort((a, b) => a - b);
  const consecutive =
    ordered.length > 1 && ordered.every((day, index) => index === 0 || day === (ordered[index - 1] ?? 0) + 1);
  if (consecutive) {
    return `${DAY_CS[ordered[0] ?? 0]}–${DAY_CS[ordered[ordered.length - 1] ?? 0]}`;
  }
  return ordered.map((day) => DAY_CS[day]).join(", ");
}

function formatMonthSet(months: Set<number> | null): string | null {
  if (!months || months.size === 0 || months.size === 12) {
    return null;
  }
  const present = months;
  const starts = [...present].filter((month) => !present.has(month === 1 ? 12 : month - 1));
  const ends = [...present].filter((month) => !present.has(month === 12 ? 1 : month + 1));
  if (starts.length === 1 && ends.length === 1) {
    const start = starts[0] ?? 1;
    const end = ends[0] ?? 12;
    if (start === end) {
      return MONTH_CS[start];
    }
    return `${MONTH_CS[start]}–${MONTH_CS[end]}`;
  }
  return [...present]
    .sort((a, b) => a - b)
    .map((month) => MONTH_CS[month])
    .join(", ");
}

function formatRule(rule: HoursRule): string {
  const month = formatMonthSet(rule.months);
  const days = formatDaySet(rule.days);
  let body = days;
  if (rule.kind === "off") {
    body = `${days} zavřeno`;
  } else if (rule.kind === "always") {
    body = days === "denně" ? "nonstop" : `${days} nonstop`;
  } else {
    const times = rule.intervals.map((slot) => `${formatClock(slot.start)}–${formatClock(slot.end)}`).join(", ");
    body = `${days} ${times}`;
  }
  return month ? `${month}: ${body}` : body;
}

export function formatOpeningHours(raw: string | null | undefined): string | null {
  const rules = parseOpeningHours(raw);
  if (rules.length === 0) {
    const text = stripComments(raw ?? "");
    return text || null;
  }
  return rules.map(formatRule).join(" · ");
}

export function hoursLineForPlace(place: CatalogPlace, at: Date = new Date()): string | null {
  const readable = formatOpeningHours(place.osm_opening_hours);
  const last = (place.last_entry || "").trim();
  const duration =
    place.visit_duration_minutes != null && place.visit_duration_minutes > 0
      ? `prohlídka ~${place.visit_duration_minutes} min`
      : null;
  const parts = [readable];
  if (last) {
    parts.push(`poslední vstup ${last}`);
  }
  if (duration) {
    parts.push(duration);
  }
  if (at && place.osm_opening_hours && placeOpenState(place, at) === "open") {
    const remaining = minutesUntilClose(place.osm_opening_hours, at);
    if (remaining != null && remaining <= CLOSING_SOON_MINUTES && remaining > 0) {
      parts.push(`zavírá za ${remaining} min`);
    }
  }
  const line = parts.filter(Boolean).join(" · ");
  return line || null;
}

export function parseHoursParam(raw: string | null | undefined): HoursFilter {
  if (raw == null) {
    return "";
  }
  const text = String(raw).trim().toLowerCase();
  if (text === "open" || text === "season") {
    return text;
  }
  return "";
}

export function parseOpenMonthParam(raw: string | null | undefined): number | "" {
  const value = Number(raw);
  if (Number.isInteger(value) && value >= 1 && value <= 12) {
    return value;
  }
  return "";
}
