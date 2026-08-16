import { useEffect, useState } from "react";
import { loadCatalogMeta, type CatalogMeta } from "../catalog/importCatalog";
import { FirstRunCoach } from "../components/FirstRunCoach";
import { downloadDiaryFile, exportDiary, loadDiaryMeta } from "../diary/store";
import type { DiaryMeta } from "../diary/types";
import { isStoragePersisted, persistStorage } from "../storage/persist";

export function AboutPage() {
  const [meta, setMeta] = useState<CatalogMeta | null>(null);
  const [diaryMeta, setDiaryMeta] = useState<DiaryMeta | null>(null);
  const [persisted, setPersisted] = useState<boolean | null>(null);

  useEffect(() => {
    void (async () => {
      const [catalogMeta, stored, diary] = await Promise.all([
        loadCatalogMeta(),
        isStoragePersisted(),
        loadDiaryMeta(),
      ]);
      setMeta(catalogMeta);
      setPersisted(stored);
      setDiaryMeta(diary);
    })();
  }, []);

  const requestPersist = async () => {
    const result = await persistStorage();
    setPersisted(result);
  };

  return (
    <section>
      <header className="page-header">
        <h1>Info</h1>
        <p className="muted">Prázdná schránka aplikace. Katalog se sem z Netlify nestahuje — nahraje se souborem.</p>
      </header>

      {meta && meta.catalog_version == null ? <FirstRunCoach catalogLink /> : null}

      <h2>Katalog v telefonu</h2>
      {meta?.catalog_version != null ? (
        <ul>
          <li>verze: {meta.catalog_version}</li>
          {meta.generated_at ? <li>export z PC: {meta.generated_at}</li> : null}
          {meta.imported_at ? <li>nahráno sem: {meta.imported_at}</li> : null}
        </ul>
      ) : (
        <p>Katalog ještě není nahraný.</p>
      )}

      <h2>Deník</h2>
      <p>
        Návštěvy, seznam „chci navštívit“ a oblíbené jsou na záložce Deník. Žijí jen v tomto telefonu, dokud
        nevyexportujete <code>diary.json</code>. Připomínka se objeví po 14 dnech nebo po 5 nových návštěvách.
      </p>
      {diaryMeta?.last_export_at ? <p className="muted">Poslední export: {diaryMeta.last_export_at}</p> : null}
      <p>
        <button
          type="button"
          className="ghost"
          onClick={() =>
            void (async () => {
              const diary = await exportDiary();
              await downloadDiaryFile(diary);
              setDiaryMeta(await loadDiaryMeta());
            })()
          }
        >
          Exportovat diary.json
        </button>
      </p>

      <h2>Přidat na plochu</h2>
      <p>
        Na iPhonu otevřete tuto stránku v Safari a zvolte Sdílet → Přidat na plochu. V Chrome se může objevit výzva
        k instalaci.
      </p>

      <h2>Uložení dat</h2>
      <p>
        {persisted === true
          ? "Prohlížeč slíbil trvalé uložení (IndexedDB by se neměla jen tak smazat)."
          : persisted === false
            ? "Úložiště zatím není trvalé. Přidejte aplikaci na plochu a zkuste to znovu."
            : "Tento prohlížeč trvalé uložení nehlásí."}
      </p>
      <p>
        <button type="button" className="ghost" onClick={() => void requestPersist()}>
          Požádat o trvalé uložení
        </button>
      </p>

      <h2>Offline</h2>
      <p>
        Aplikace, katalog a deník fungují bez sítě. Mapa ukládá jen OSM dlaždice z výřezů, které jste už prohlíželi
        (omezená mezipaměť, desítky MB). Celé Česko jako offline balíček tu není. Fotky z Commons potřebují připojení,
        pokud už nejsou v mezipaměti.
      </p>
      <p className="muted small">
        Odznaky na záložce Deník se počítají z návštěv v telefonu a do <code>diary.json</code> se neexportují.
      </p>

      {meta?.attribution ? (
        <>
          <h2>Zdroje dat</h2>
          <ul>
            <li>{meta.attribution.wikidata}</li>
            <li>{meta.attribution.npu_opendata}</li>
            <li>{meta.attribution.osm}</li>
            <li>{meta.attribution.commons}</li>
          </ul>
        </>
      ) : null}
    </section>
  );
}
