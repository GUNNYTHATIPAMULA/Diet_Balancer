import { CheckCircle2, CircleDashed, Loader2, OctagonX, XCircle } from "lucide-react";
import { mealLabel } from "../../utils/constants";
import { Button } from "../ui/Button";

export const TERMINAL = ["completed", "failed", "cancelled", "expired"];
const STEPS = [
  { key: "pending", label: "Sent" },
  { key: "acknowledged", label: "Accepted" },
  { key: "dispensing", label: "Dispensing" },
  { key: "done", label: "Weighed" },
];
const ORDER = { pending: 0, acknowledged: 1, dispensing: 2, completed: 3, failed: 3, cancelled: 3, expired: 3 };

const MESSAGES = {
  pending: "Waiting for the dispenser to pick up the request…",
  acknowledged: "The dispenser accepted the request and is reading the scale.",
  dispensing: "Dispensing. The gate closes when the scale reaches the target.",
  completed: "Done. The amount below was measured by the load cell.",
  failed: "The dispense did not finish.",
  cancelled: "Stopped.",
  expired: "The dispenser didn’t pick up the request in time. Nothing was dispensed.",
};

export function OperationPanel({ command, onCancel, onLogMeasured, onDismiss, busy }) {
  if (!command) return null;
  const s = command.status;
  const step = ORDER[s];
  const terminal = TERMINAL.includes(s);
  const isTare = command.command_type === "tare";
  const live = s === "dispensing" ? command.last_progress_weight_g : null;
  const measured = command.dispensed_weight_g;
  const target = command.target_weight_g;
  const pct = target ? Math.min(((live ?? measured ?? 0) / target) * 100, 100) : 0;
  const Icon = s === "completed" ? CheckCircle2 : s === "failed" || s === "expired" ? XCircle : s === "cancelled" ? OctagonX : Loader2;
  const tone = s === "completed" ? "text-leaf" : terminal ? "text-alert" : "text-river";

  return (
    <section className="panel overflow-hidden" aria-live="polite">
      <div className="flex flex-col gap-5 p-6 sm:flex-row sm:items-start">
        <Icon className={`h-8 w-8 shrink-0 ${tone} ${terminal ? "" : "animate-spin"}`} aria-hidden />
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-semibold">
            {isTare ? "Zeroing the scale" : `${command.food_name || "Food"} from ${command.container_label || "container"}`}
          </h2>
          <p className="text-[15px] text-slate">{command.cancel_requested && !terminal ? "Stop requested. Waiting for the dispenser to close and report the weight…" : MESSAGES[s]}</p>
          {command.error_message && terminal && s !== "completed" && <p className="mt-1 text-sm text-alert">{command.error_message}</p>}

          {!isTare && (
            <>
              <ol className="mt-5 grid grid-cols-4 gap-2" aria-label="Progress">
                {STEPS.map((st, i) => {
                  const done = i < step || (i === step && terminal && s === "completed");
                  const current = i === step && !terminal;
                  return (
                    <li key={st.key} className="text-xs font-semibold">
                      <span className={`mb-1.5 block h-1.5 rounded-full ${done ? "bg-leaf" : current ? "bg-river animate-pulse" : terminal && i === 3 ? "bg-alert" : "bg-line"}`} />
                      <span className={done || current ? "text-ink" : "text-slate-light"}>{st.label}</span>
                    </li>
                  );
                })}
              </ol>
              <dl className="mt-5 grid grid-cols-2 gap-3 sm:max-w-md">
                <div className="rounded-2xl bg-mist px-4 py-3">
                  <dt className="text-sm text-slate">Requested</dt>
                  <dd className="num font-display text-2xl font-semibold">{target} g</dd>
                </div>
                <div className={`rounded-2xl px-4 py-3 ${s === "completed" ? "bg-sprout-light" : "bg-mist"}`}>
                  <dt className="text-sm text-slate">{terminal ? "Measured" : "On the scale"}</dt>
                  <dd className="num font-display text-2xl font-semibold">{terminal ? (measured != null ? `${measured} g` : "—") : live != null ? `${live} g` : "…"}</dd>
                </div>
              </dl>
              {!terminal && (
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-mist sm:max-w-md">
                  <div className="h-full rounded-full bg-leaf transition-[width] duration-500" style={{ width: `${pct}%` }} />
                </div>
              )}
              {s === "completed" && (
                <p className="mt-3 text-sm text-slate">
                  {command.meal_entry_id ? `Added ${measured} g to ${mealLabel(command.meal_type).toLowerCase()} in your food log.` : "Not added to your log (logging was off)."}
                </p>
              )}
            </>
          )}
          {isTare && s === "completed" && <p className="mt-2 text-sm text-slate">The scale now reads zero with the bowl in place.</p>}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2 sm:flex-col">
          {!terminal && <Button variant="danger-soft" loading={busy} onClick={onCancel}>{s === "pending" ? "Cancel" : "Stop now"}</Button>}
          {terminal && ["failed", "cancelled"].includes(s) && measured > 0.5 && !command.meal_entry_id && command.food_item_id && (
            <Button variant="soft" loading={busy} onClick={onLogMeasured}>Log measured {measured} g</Button>
          )}
          {terminal && <Button variant="ghost" onClick={onDismiss}>Dismiss</Button>}
        </div>
      </div>
    </section>
  );
}

export function StatusPill({ status }) {
  const map = {
    completed: "bg-sprout-light text-canopy", failed: "bg-alert-light text-alert", cancelled: "bg-wheat-light text-[#6B4F10]",
    expired: "bg-mist text-slate", pending: "bg-river-light text-river", acknowledged: "bg-river-light text-river", dispensing: "bg-river-light text-river",
  };
  const Icon = TERMINAL.includes(status) ? null : CircleDashed;
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${map[status]}`}>{Icon && <Icon className="h-3 w-3" aria-hidden />}{status}</span>;
}
