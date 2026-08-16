import type { ReactNode } from "react";

export function FilterDisclosure({ count, children }: { count: number; children: ReactNode }) {
  return (
    <details className="filter-extra">
      <summary>Filtry{count ? ` (${count})` : ""}</summary>
      <div className="filter-extra-grid">{children}</div>
    </details>
  );
}

export function extraFilterCount(values: Array<string | null | undefined | boolean>): number {
  return values.filter(Boolean).length;
}
