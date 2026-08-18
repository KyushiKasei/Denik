import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { downloadDiaryFile, exportDiary } from "../diary/store";
import { isStoragePersisted, persistStorage } from "../storage/persist";

interface FirstRunCoachProps {
  catalogLink?: boolean;
}

export function FirstRunCoach({ catalogLink = false }: FirstRunCoachProps) {
  const [persisted, setPersisted] = useState<boolean | null>(null);
  const [exportBusy, setExportBusy] = useState(false);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    void isStoragePersisted().then((value) => {
      if (alive.current) {
        setPersisted(value);
      }
    });
    return () => {
      alive.current = false;
    };
  }, []);

  const requestPersist = async () => {
    const value = await persistStorage();
    if (alive.current) {
      setPersisted(value);
    }
  };

  const exportNow = async () => {
    if (exportBusy) {
      return;
    }
    setExportBusy(true);
    try {
      const file = await exportDiary();
      await downloadDiaryFile(file);
    } finally {
      if (alive.current) {
        setExportBusy(false);
      }
    }
  };

  return (
    <section className="first-run" aria-label="První spuštění">
      <h2>Začněte ve třech krocích</h2>
      <ol className="coach-steps">
        <li>
          <strong>1. Nahrát catalog.json</strong>
          <p>
            Z PC aplikace exportujte katalog a nahrajte ho sem. Bez něj je seznam prázdný — z Netlify se nestahuje.
          </p>
          {catalogLink ? (
            <p>
              <Link to="/import" className="button">
                Nahrát catalog.json
              </Link>
            </p>
          ) : null}
        </li>
        <li>
          <strong>2. Přidat na plochu</strong>
          <p>
            Na iPhonu otevřete tuto stránku v Safari a zvolte Sdílet → Přidat na plochu. V Chrome se může objevit výzva
            k instalaci. Aplikace pak lépe udrží katalog i bez sítě.
          </p>
          <p className="muted small">
            {persisted === true
              ? "Prohlížeč slíbil trvalé uložení."
              : persisted === false
                ? "Úložiště zatím není trvalé. Přidejte aplikaci na plochu a zkuste to znovu."
                : "Tento prohlížeč trvalé uložení nehlásí."}
          </p>
          <p>
            <button type="button" className="ghost" onClick={() => void requestPersist()}>
              Požádat o trvalé uložení
            </button>
          </p>
        </li>
        <li>
          <strong>3. Zálohovat deník</strong>
          <p>
            Návštěvy žijí jen v tomto telefonu, dokud nevyexportujete <code>diary.json</code>.
          </p>
          <p>
            <button type="button" className="ghost" onClick={() => void exportNow()} disabled={exportBusy}>
              {exportBusy ? "Exportuji…" : "Exportovat diary.json"}
            </button>
          </p>
        </li>
      </ol>
    </section>
  );
}
