export function PeopleInput({
  value,
  onChange,
  names,
  id = "people-suggest",
}: {
  value: string;
  onChange: (value: string) => void;
  names: string[];
  id?: string;
}) {
  return (
    <>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Jana, Petr"
        list={names.length ? id : undefined}
        autoComplete="off"
      />
      {names.length > 0 ? (
        <datalist id={id}>
          {names.map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
      ) : null}
    </>
  );
}
