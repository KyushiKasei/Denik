import type { CatalogMeta } from "../catalog/importCatalog";
import type { DiaryMeta } from "../diary/types";

function shortDate(iso: string | null): string | null {
  if (!iso) {
    return null;
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) {
    return iso.slice(0, 10);
  }
  return `${Number(match[3])}. ${Number(match[2])}.`;
}

export function SyncStatus({ catalog, diary }: { catalog: CatalogMeta | null; diary: DiaryMeta | null }) {
  if (!catalog && !diary) {
    return null;
  }
  const catalogLabel =
    catalog?.catalog_version != null
      ? `katalog v${catalog.catalog_version}${shortDate(catalog.generated_at) ? ` · ${shortDate(catalog.generated_at)}` : ""}`
      : "katalog chybí";
  const diaryLabel = diary?.last_export_at
    ? `deník záloha ${shortDate(diary.last_export_at)}`
    : "deník zatím bez zálohy";

  return (
    <p className="sync-status muted small">
      {catalogLabel}
      {" · "}
      {diaryLabel}
    </p>
  );
}
