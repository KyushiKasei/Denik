import { loadDiaryMeta, loadVisits } from "./store";

const DAY_MS = 24 * 60 * 60 * 1000;
export const EXPORT_REMINDER_DAYS = 14;
export const EXPORT_REMINDER_NEW_VISITS = 5;
export const EXPORT_REMINDER_DISMISS_KEY = "pamatky.exportReminder.dismissed";

export interface ExportReminder {
  show: boolean;
  daysSinceExport: number | null;
  newVisits: number;
  neverExported: boolean;
  lastExportAt: string | null;
}

export interface ExportReminderDismiss {
  at: string;
  visitCount: number;
  lastExportAt: string | null;
}

function storage(): Storage | null {
  try {
    if (typeof localStorage === "undefined") {
      return null;
    }
    return localStorage;
  } catch {
    return null;
  }
}

export function loadReminderDismiss(): ExportReminderDismiss | null {
  const raw = storage()?.getItem(EXPORT_REMINDER_DISMISS_KEY);
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as ExportReminderDismiss;
    if (!parsed || typeof parsed.at !== "string" || typeof parsed.visitCount !== "number") {
      return null;
    }
    return {
      at: parsed.at,
      visitCount: parsed.visitCount,
      lastExportAt: parsed.lastExportAt ?? null,
    };
  } catch {
    return null;
  }
}

export function dismissExportReminder(visitCount: number, lastExportAt: string | null): void {
  const payload: ExportReminderDismiss = {
    at: new Date().toISOString(),
    visitCount,
    lastExportAt,
  };
  storage()?.setItem(EXPORT_REMINDER_DISMISS_KEY, JSON.stringify(payload));
}

export function clearExportReminderDismiss(): void {
  storage()?.removeItem(EXPORT_REMINDER_DISMISS_KEY);
}

export async function diaryExportReminder(): Promise<ExportReminder> {
  const [visits, meta] = await Promise.all([loadVisits(), loadDiaryMeta()]);
  const active = visits.filter((visit) => !visit.deleted_at);
  const lastExportAt = meta.last_export_at ?? null;
  if (active.length === 0) {
    return {
      show: false,
      daysSinceExport: null,
      newVisits: 0,
      neverExported: lastExportAt == null,
      lastExportAt,
    };
  }

  const now = Date.now();
  let info: ExportReminder;
  if (!lastExportAt) {
    const oldest = active.reduce((min, visit) => {
      const ms = Date.parse(visit.created_at.trim());
      return Number.isNaN(ms) ? min : Math.min(min, ms);
    }, now);
    const days = Math.floor((now - oldest) / DAY_MS);
    const show = active.length >= EXPORT_REMINDER_NEW_VISITS || days >= EXPORT_REMINDER_DAYS;
    info = { show, daysSinceExport: days, newVisits: active.length, neverExported: true, lastExportAt };
  } else {
    const exportedAt = Date.parse(lastExportAt.trim());
    const daysSinceExport = Number.isNaN(exportedAt) ? null : Math.floor((now - exportedAt) / DAY_MS);
    const newVisits = Math.max(0, active.length - meta.visits_at_last_export);
    const show =
      (daysSinceExport != null && daysSinceExport >= EXPORT_REMINDER_DAYS) || newVisits >= EXPORT_REMINDER_NEW_VISITS;
    info = { show, daysSinceExport, newVisits, neverExported: false, lastExportAt };
  }

  if (!info.show) {
    return info;
  }

  const dismissed = loadReminderDismiss();
  if (!dismissed) {
    return info;
  }
  if (dismissed.lastExportAt !== lastExportAt) {
    return info;
  }
  const visitsGrew = info.newVisits >= dismissed.visitCount + EXPORT_REMINDER_NEW_VISITS;
  const dismissedAt = Date.parse(dismissed.at.trim());
  const daysSinceDismiss = Number.isNaN(dismissedAt) ? 0 : Math.floor((Date.now() - dismissedAt) / DAY_MS);
  if (visitsGrew || daysSinceDismiss >= EXPORT_REMINDER_DAYS) {
    return info;
  }
  return { ...info, show: false };
}
