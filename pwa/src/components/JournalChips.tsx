export function JournalChips({
  visited,
  want,
  favorite,
}: {
  visited: boolean;
  want: boolean;
  favorite: boolean;
}) {
  if (!visited && !want && !favorite) {
    return null;
  }
  return (
    <span className="journal-chips">
      {visited ? <span className="chip chip-visited">navštíveno</span> : null}
      {want ? <span className="chip chip-want">chci</span> : null}
      {favorite ? <span className="chip chip-fav">oblíbené</span> : null}
    </span>
  );
}
