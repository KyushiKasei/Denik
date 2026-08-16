import { useEffect, useState } from "react";
import {
  clearExportReminderDismiss,
  diaryExportReminder,
  dismissExportReminder,
  type ExportReminder as ExportReminderInfo,
} from "../diary/reminder";
import { downloadDiaryFile, exportDiary } from "../diary/store";

export function ExportReminder({ onActiveChange }: { onActiveChange?: (active: boolean) => void }) {
  const [info, setInfo] = useState<ExportReminderInfo | null>(null);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    void diaryExportReminder().then(setInfo);
  }, []);

  const active = !hidden && Boolean(info?.show);
  useEffect(() => {
    onActiveChange?.(active);
  }, [active, onActiveChange]);

  if (hidden || !info?.show) {
    return null;
  }

  const exportNow = async () => {
    const diary = await exportDiary();
    await downloadDiaryFile(diary);
    clearExportReminderDismiss();
    setHidden(true);
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
            ? `Deník ještě nebyl exportován (${info.newVisits} návštěv).`
            : info.daysSinceExport != null && info.daysSinceExport >= 14
              ? `Od posledního exportu uplynulo ${info.daysSinceExport} dní.`
              : `Od posledního exportu přibylo ${info.newVisits} návštěv.`}{" "}
          Exportujte <code>diary.json</code> do Dropboxu nebo do souboru.
        </p>
      </div>
      <div className="install-actions">
        <button type="button" onClick={() => void exportNow()}>
          Exportovat
        </button>
        <button type="button" className="ghost" onClick={dismiss}>
          Teď ne
        </button>
      </div>
    </aside>
  );
}
