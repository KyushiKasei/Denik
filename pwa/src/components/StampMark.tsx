import { STAMP_PATHS, type StampKind } from "../diary/stampArt";

export function StampMark({
  kind,
  wax,
  title,
  size = 64,
  empty = false,
}: {
  kind: StampKind;
  wax: string;
  title?: string;
  size?: number;
  empty?: boolean;
}) {
  return (
    <svg
      className={`stamp-mark${empty ? " is-empty" : ""}`}
      viewBox="0 0 64 64"
      width={size}
      height={size}
      aria-hidden={title ? undefined : true}
      role={title ? "img" : undefined}
    >
      {title ? <title>{title}</title> : null}
      <circle cx="32" cy="32" r="30" fill="none" stroke={empty ? "currentColor" : wax} strokeWidth="2" strokeDasharray={empty ? "4 4" : undefined} />
      <path d={STAMP_PATHS[kind]} fill="none" stroke={empty ? "currentColor" : wax} strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
