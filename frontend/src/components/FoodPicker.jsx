import { useEffect, useId, useState } from "react";
import { Search, Loader2 } from "lucide-react";
import { foodsApi } from "../api/foods";
import { errorMessage } from "../api/client";
import { useDebounce } from "../hooks/useDebounce";
import { Badge } from "./ui/Feedback";

/** Accessible search-as-you-type food selector. */
export function FoodPicker({ onSelect, autoFocus = false, placeholder = "Search rice, dal, paneer…" }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [active, setActive] = useState(0);
  const debounced = useDebounce(query.trim(), 220);
  const listId = useId();

  useEffect(() => {
    if (!debounced) {
      setResults([]);
      setStatus("idle");
      return undefined;
    }
    let cancelled = false;
    setStatus("loading");
    foodsApi.search(debounced, 12)
      .then((r) => {
        if (cancelled) return;
        setResults(r.items);
        setActive(0);
        setStatus("done");
      })
      .catch((e) => {
        if (cancelled) return;
        setError(errorMessage(e));
        setStatus("error");
      });
    return () => { cancelled = true; };
  }, [debounced]);

  const choose = (food) => {
    onSelect(food);
    setQuery("");
    setResults([]);
    setStatus("idle");
  };

  const onKeyDown = (e) => {
    if (!results.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    if (e.key === "Enter") { e.preventDefault(); choose(results[active]); }
  };

  return (
    <div className="relative">
      <label htmlFor={`${listId}-input`} className="sr-only">Search foods</label>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate" aria-hidden />
        <input id={`${listId}-input`} role="combobox" aria-expanded={results.length > 0} aria-controls={listId}
          aria-activedescendant={results[active] ? `${listId}-${results[active].id}` : undefined}
          autoFocus={autoFocus} value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={onKeyDown}
          placeholder={placeholder} autoComplete="off" className="field-input pl-10" />
        {status === "loading" && <Loader2 className="absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-slate" aria-hidden />}
      </div>
      {status === "error" && <p className="mt-2 text-sm text-alert">{error}</p>}
      {status === "done" && results.length === 0 && (
        <p className="mt-2 text-sm text-slate">No foods match “{debounced}”. You can add it as a custom food in the Food library.</p>
      )}
      {results.length > 0 && (
        <ul id={listId} role="listbox" className="mt-2 max-h-72 overflow-y-auto rounded-2xl border border-line bg-white p-1.5 shadow-card">
          {results.map((f, i) => (
            <li key={f.id} id={`${listId}-${f.id}`} role="option" aria-selected={i === active}
              onMouseEnter={() => setActive(i)} onMouseDown={(e) => { e.preventDefault(); choose(f); }}
              className={`flex cursor-pointer items-center justify-between gap-3 rounded-xl px-3 py-2.5 ${i === active ? "bg-sprout-light" : ""}`}>
              <span>
                <span className="block text-[15px] font-medium text-ink">{f.name}</span>
                <span className="text-xs text-slate">{f.category} · {f.serving_unit} ≈ {f.serving_size_g} g</span>
              </span>
              <span className="flex shrink-0 items-center gap-2">
                {f.is_custom && <Badge tone="blue">Custom</Badge>}
                <span className="num text-sm text-slate"><span className="font-semibold text-ink">{Math.round(f.calories_per_100g)}</span> kcal/100 g</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
