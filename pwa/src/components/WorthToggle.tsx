export function WorthToggle({
  value,
  onChange,
  visitCount,
  allCount,
}: {
  value: boolean;
  onChange: (next: boolean) => void;
  visitCount?: number;
  allCount?: number;
}) {
  return (
    <div className="segmented cols-2 worth-toggle" role="group" aria-label="Za návštěvu">
      <button type="button" className={value ? "active" : ""} onClick={() => onChange(true)}>
        Za návštěvu{visitCount != null ? ` (${visitCount})` : ""}
      </button>
      <button type="button" className={value ? "" : "active"} onClick={() => onChange(false)}>
        Vše{allCount != null ? ` (${allCount})` : ""}
      </button>
    </div>
  );
}
