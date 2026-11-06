import { forwardRef, useId } from "react";

export function Field({ label, error, hint, children, htmlFor, className = "" }) {
  return (
    <div className={`space-y-1.5 ${className}`}>
      {label && (
        <label htmlFor={htmlFor} className="block text-sm font-semibold text-ink">
          {label}
        </label>
      )}
      {children}
      {error ? (
        <p className="text-sm text-alert" role="alert">{error}</p>
      ) : hint ? (
        <p className="text-sm text-slate">{hint}</p>
      ) : null}
    </div>
  );
}

export const Input = forwardRef(function Input({ label, error, hint, suffix, className = "", id, ...props }, ref) {
  const autoId = useId();
  const inputId = id || autoId;
  return (
    <Field label={label} error={error} hint={hint} htmlFor={inputId} className={className}>
      <div className="relative">
        <input ref={ref} id={inputId} aria-invalid={error ? "true" : undefined} className={`field-input ${suffix ? "pr-12" : ""}`} {...props} />
        {suffix && <span className="pointer-events-none absolute inset-y-0 right-3.5 flex items-center text-sm text-slate">{suffix}</span>}
      </div>
    </Field>
  );
});

export const Select = forwardRef(function Select({ label, error, hint, options, className = "", id, ...props }, ref) {
  const autoId = useId();
  const selectId = id || autoId;
  return (
    <Field label={label} error={error} hint={hint} htmlFor={selectId} className={className}>
      <select ref={ref} id={selectId} aria-invalid={error ? "true" : undefined} className="field-input appearance-none bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 20 20%22 fill=%22%235B6B60%22><path d=%22M5.5 7.5 10 12l4.5-4.5%22 stroke=%22%235B6B60%22 stroke-width=%221.6%22 fill=%22none%22/></svg>')] bg-[length:18px] bg-[right_0.8rem_center] bg-no-repeat pr-10" {...props}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </Field>
  );
});
