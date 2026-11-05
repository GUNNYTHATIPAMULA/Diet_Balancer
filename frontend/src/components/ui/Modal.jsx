import { useEffect, useRef } from "react";
import { X } from "lucide-react";

export function Modal({ open, onClose, title, description, children, footer, size = "md" }) {
  const panelRef = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement;
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const first = panelRef.current?.querySelector("input, select, textarea, button:not([data-close])");
    (first || panelRef.current)?.focus();
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      previous?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;
  const width = { sm: "max-w-md", md: "max-w-lg", lg: "max-w-2xl" }[size];
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/40 p-0 sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={panelRef} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title}
        className={`flex max-h-[92vh] w-full ${width} flex-col rounded-t-3xl bg-white shadow-lift outline-none sm:rounded-3xl`}>
        <div className="flex items-start justify-between gap-4 px-6 pb-2 pt-5">
          <div>
            <h2 className="text-xl font-semibold">{title}</h2>
            {description && <p className="mt-1 text-sm text-slate">{description}</p>}
          </div>
          <button data-close onClick={onClose} className="rounded-xl p-1.5 text-slate hover:bg-mist hover:text-ink" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-3">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-6 py-4">{footer}</div>}
      </div>
    </div>
  );
}

export function ConfirmDialog({ open, title, message, confirmLabel, tone = "danger", loading, onConfirm, onCancel }) {
  return (
    <Modal open={open} onClose={onCancel} title={title} size="sm"
      footer={
        <>
          <button className="h-10 rounded-xl px-4 text-sm font-semibold text-slate hover:bg-mist" onClick={onCancel}>Keep it</button>
          <button disabled={loading} onClick={onConfirm}
            className={`h-10 rounded-xl px-4 text-sm font-semibold text-white disabled:opacity-60 ${tone === "danger" ? "bg-alert" : "bg-canopy"}`}>
            {confirmLabel}
          </button>
        </>
      }>
      <p className="text-[15px] text-slate">{message}</p>
    </Modal>
  );
}
