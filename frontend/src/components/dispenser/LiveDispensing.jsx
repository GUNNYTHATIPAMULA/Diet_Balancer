import { useEffect, useRef } from "react";
import { AlertOctagon, CheckCircle2, CircleDashed, Clock, Loader2, OctagonX, XCircle } from "lucide-react";
import { mealLabel } from "../../utils/constants";
import { AccuracyBadge, MacroLine } from "../../utils/nutrition";
import { Button } from "../ui/Button";

export const TERMINAL = ["completed", "failed", "cancelled", "expired"];
const PLAN_DONE = ["completed", "partial", "failed", "cancelled"];

const STATUS = {
  queued: [Clock, "text-slate-light", "Waiting its turn"],
  pending: [Loader2, "text-river animate-spin", "Waiting for the dispenser…"],
  acknowledged: [Loader2, "text-river animate-spin", "Reading the scale…"],
  dispensing: [Loader2, "text-river animate-spin", "Dispensing"],
  completed: [CheckCircle2, "text-leaf", "Done"],
  failed: [XCircle, "text-alert", "Didn’t finish"],
  cancelled: [OctagonX, "text-[#7A5A12]", "Stopped"],
  expired: [XCircle, "text-alert", "Not picked up"],
};

export function StatusPill({ status }) {
  const map = {
    completed: "bg-sprout-light text-canopy", failed: "bg-alert-light text-alert", cancelled: "bg-wheat-light text-[#6B4F10]",
    expired: "bg-mist text-slate", pending: "bg-river-light text-river", acknowledged: "bg-river-light text-river",
    dispensing: "bg-river-light text-river", queued: "bg-mist text-slate",
  };
  const Icon = TERMINAL.includes(status) ? null : CircleDashed;
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${map[status]}`}>{Icon && <Icon className="h-3 w-3" aria-hidden />}{status}</span>;
}

function Step({ step, onLogMeasured, busy }) {
  const c = step.command;
  const s = c?.status || "queued";
  const [Icon, cls, text] = STATUS[s];
  const active = ["pending", "acknowledged", "dispensing"].includes(s);
  const live = s === "dispensing" ? c.last_progress_weight_g : null;
  const measured = c?.dispensed_weight_g;
  const target = c?.target_weight_g ?? step.grams;
  const pct = target ? Math.min(((live ?? measured ?? 0) / target) * 100, 100) : 0;
  return (
    <li className={`rounded-2xl border px-4 py-3.5 ${active ? "border-river/40 bg-river-light/30" : "border-line bg-white"}`}>
      <div className="flex items-start gap-3">
        <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${cls}`} aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold">{step.food_name} <span className="text-sm font-normal text-slate">· {step.container_label}</span></p>
            {c && TERMINAL.includes(s) ? <AccuracyBadge command={c} /> : <span className="text-xs font-semibold text-slate">{text}</span>}
          </div>
          <dl className="num mt-2 grid grid-cols-3 gap-2 text-sm sm:max-w-md">
            <div><dt className="text-xs text-slate">Requested</dt><dd className="font-semibold">{target} g</dd></div>
            <div><dt className="text-xs text-slate">{TERMINAL.includes(s) ? "Measured" : "On the scale"}</dt>
              <dd className="font-semibold">{TERMINAL.includes(s) ? (measured != null ? `${measured} g` : "—") : live != null ? `${live} g` : "…"}</dd></div>
            <div><dt className="text-xs text-slate">Difference</dt>
              <dd className="font-semibold">{c?.difference_g != null ? `${c.difference_g > 0 ? "+" : ""}${c.difference_g} g` : "—"}</dd></div>
          </dl>
          {active && (
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-white sm:max-w-md" role="progressbar" aria-valuenow={Math.round(pct)} aria-label={`${step.food_name} progress`}>
              <div className="h-full rounded-full bg-leaf transition-[width] duration-500" style={{ width: `${pct}%` }} />
            </div>
          )}
          {s === "completed" && c.nutrition && <MacroLine n={c.nutrition} className="mt-2" />}
          {c?.error_message && s !== "completed" && <p className="mt-1.5 text-sm text-alert">{c.error_message}</p>}
          {c && ["failed", "cancelled"].includes(s) && measured > 0.5 && !c.meal_entry_id && c.food_item_id && onLogMeasured && (
            <Button size="sm" variant="soft" className="mt-2" loading={busy} onClick={() => onLogMeasured(c)}>Log measured {measured} g</Button>
          )}
        </div>
      </div>
    </li>
  );
}

/** Live view for a meal plan being served, or a single serve. */
export function LiveDispensing({ plan, command, busy, onStopMeal, onCancelCommand, onEmergencyStop, onLogMeasured, onDismiss }) {
  const ref = useRef(null);
  const operationId = plan?.id || command?.id;
  // Bring the live view on screen when a new serve starts (the Serve button may be far below).
  useEffect(() => {
    if (!operationId || !ref.current?.scrollIntoView) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    ref.current.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }, [operationId]);
  const steps = plan ? plan.items : command ? [{ food_name: command.food_name || "Scale", container_label: command.container_label || "", grams: command.target_weight_g, command }] : [];
  if (!steps.length) return null;
  const isTare = !plan && command?.command_type === "tare";
  const finished = plan ? PLAN_DONE.includes(plan.status) : TERMINAL.includes(command.status);
  const running = steps.find((s) => s.command && ["pending", "acknowledged", "dispensing"].includes(s.command.status));
  const done = steps.filter((s) => s.command?.status === "completed").length;

  const title = isTare ? "Zeroing the scale"
    : plan ? (finished ? { completed: "Meal served", partial: "Meal partly served", failed: "Meal not served", cancelled: "Meal stopped" }[plan.status]
      : `Serving your ${mealLabel(plan.meal_type).toLowerCase()}`)
      : finished ? (command.status === "completed" ? "Served" : "Serve didn’t finish") : `Serving ${command.food_name}`;
  const measured = plan?.measured_totals || (command?.status === "completed" ? command.nutrition : null);

  return (
    <section ref={ref} className={`panel scroll-mt-20 overflow-hidden ${finished ? "" : "ring-2 ring-river/30"}`} aria-live="polite" aria-labelledby="live-title">
      <div className="flex flex-col gap-3 border-b border-line p-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 id="live-title" className="text-xl font-semibold">{title}</h2>
          <p className="text-sm text-slate">
            {isTare ? (finished ? "The scale now reads zero." : "Keep the bowl still…")
              : plan ? `${done} of ${steps.length} food${steps.length > 1 ? "s" : ""} served. Only measured amounts are logged.`
                : "The dispenser measures what is actually served; that’s what gets logged."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {!finished && <Button variant="danger" icon={AlertOctagon} onClick={onEmergencyStop}>Emergency stop</Button>}
          {!finished && plan && <Button variant="secondary" loading={busy} onClick={onStopMeal}>Stop meal</Button>}
          {!finished && !plan && <Button variant="secondary" loading={busy} onClick={onCancelCommand}>{command.status === "pending" ? "Cancel" : "Stop"}</Button>}
          {finished && <Button variant="ghost" onClick={onDismiss}>Dismiss</Button>}
        </div>
      </div>
      {!isTare && (
        <ul className="space-y-2.5 p-6">
          {steps.map((s, i) => <Step key={s.command?.id || i} step={s} busy={busy} onLogMeasured={onLogMeasured} />)}
        </ul>
      )}
      {finished && measured && !isTare && (
        <div className="border-t border-line bg-sprout-light/50 px-6 py-4">
          <p className="text-sm font-semibold text-canopy">Added to your food log (from measured weights)</p>
          <dl className="num mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[["Calories", measured.calories, "kcal"], ["Protein", measured.protein_g, "g"], ["Carbs", measured.carbs_g, "g"], ["Fat", measured.fat_g, "g"]].map(([k, v, u]) => (
              <div key={k}><dt className="text-xs text-slate">{k}</dt><dd className="font-display text-xl font-semibold">{Math.round(v)} <span className="text-sm font-medium text-slate">{u}</span></dd></div>
            ))}
          </dl>
        </div>
      )}
      {!finished && running == null && plan && <p className="px-6 pb-5 text-sm text-slate">Preparing the next food…</p>}
    </section>
  );
}
