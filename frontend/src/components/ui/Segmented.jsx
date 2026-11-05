export function Segmented({ options, value, onChange, label, size = "md" }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-2xl bg-white p-1 shadow-card ring-1 ring-line/70">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button key={o.value} role="radio" aria-checked={active} onClick={() => onChange(o.value)}
            className={`rounded-xl font-semibold transition-colors ${size === "sm" ? "px-3 py-1.5 text-sm" : "px-4 py-2 text-sm"} ${active ? "bg-canopy text-white" : "text-slate hover:text-ink"}`}>
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/** Large selectable cards used in the setup wizard and profile forms. */
export function ChoiceCards({ options, value, onChange, name, columns = "sm:grid-cols-2", multiple = false }) {
  const isActive = (v) => (multiple ? value.includes(v) : value === v);
  const toggle = (v) => {
    if (!multiple) return onChange(v);
    onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  };
  return (
    <div role={multiple ? "group" : "radiogroup"} aria-label={name} className={`grid gap-2.5 ${columns}`}>
      {options.map((o) => {
        const active = isActive(o.value);
        return (
          <button key={o.value} type="button" role={multiple ? "checkbox" : "radio"} aria-checked={active} onClick={() => toggle(o.value)}
            className={`rounded-2xl border px-4 py-3 text-left transition-colors ${active ? "border-leaf bg-sprout-light ring-1 ring-leaf" : "border-line bg-white hover:border-leaf/40"}`}>
            <span className="block text-[15px] font-semibold text-ink">{o.label}</span>
            {o.hint && <span className="mt-0.5 block text-sm text-slate">{o.hint}</span>}
          </button>
        );
      })}
    </div>
  );
}
