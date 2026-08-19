import { useEffect, useRef, useState } from "react";
import {
  clearExportReminderDismiss,
  diaryExportReminder,
  dismissExportReminder,
  type ExportReminder as ExportReminderInfo,
} from "../diary/reminder";
import { downloadDiaryBundle } from "../diary/store";
import { czechCountWord } from "../diary/timeline";

export function ExportReminder({ onActiveChange }: { onActiveChange?: (active: boolean) => void }) {
  const [info, setInfo] = useState<ExportReminderInfo | null>(null);
  const [hidden, setHidden] = useState(false);
  const [busy, setBusy] = useState(false);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    void diaryExportReminder().then((value) => {
      if (alive.current) {
        setInfo(value);
      }
    });
    return () => {
      alive.current = false;
    };
  }, []);

  const active = !hidden && Boolean(info?.show);
  useEffect(() => {
    onActiveChange?.(active);
  }, [active, onActiveChange]);

  if (hidden || !info?.show) {
    return null;
  }

  const exportNow = async () => {
    if (busy) {
      return;
    }
    setBusy(true);
    try {
      await downloadDiaryBundle();
      clearExportReminderDismiss();
      if (alive.current) {
        setHidden(true);
      }
    } finally {
      if (alive.current) {
        setBusy(false);
      }
    }
  };

  const dismiss = () => {
    dismissExportReminder(info.newVisits, info.lastExportAt);
    setHidden(true);
  };

  return (
    <aside className="install-banner" role="status">
      <div>
        <strong>Záloha deníku</strong>
        <p>
          {info.neverExported
            ? `Deník ještě nebyl exportován (${info.newVisits} ${czechCountWord(info.newVisits, "návštěva", "návštěvy", "návštěv")}).`
            : info.daysSinceExport != null && info.daysSinceExport >= 14
              ? `Od posledního exportu uplynulo ${info.daysSinceExport} ${czechCountWord(info.daysSinceExport, "den", "dny", "dní")}.`
              : `Od posledního exportu přibylo ${info.newVisits} ${czechCountWord(info.newVisits, "návštěva", "návštěvy", "návštěv")}.`}{" "}
          Exportujte <code>diary.json</code> do Dropboxu nebo do souboru.
        </p>
      </div>
      <div className="install-actions">
        <button type="button" onClick={() => void exportNow()} disabled={busy}>
          {busy ? "Exportuji…" : "Exportovat"}
        </button>
        <button type="button" className="ghost" onClick={dismiss}>
          Teď ne
        </button>
      </div>
    </aside>
  );
}
