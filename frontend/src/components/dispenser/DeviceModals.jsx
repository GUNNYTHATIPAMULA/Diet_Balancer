import { useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
import { devicesApi } from "../../api/devices";
import { errorMessage, fieldErrors } from "../../api/client";
import { useToast } from "../../context/ToastContext";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { Input } from "../ui/Field";

export function CopyButton({ text, label = "Copy" }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch { /* clipboard blocked; text is still selectable */ }
  };
  return (
    <button type="button" onClick={copy} className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-canopy hover:bg-sprout-light">
      {copied ? <Check className="h-3.5 w-3.5" aria-hidden /> : <Copy className="h-3.5 w-3.5" aria-hidden />}{copied ? "Copied" : label}
    </button>
  );
}

const SETTING_FIELDS = [
  ["inflight_g", "Close early by", "g", "Food still falling after the gate closes."],
  ["slowdown_g", "Switch to pulses within", "g", "Short open/close pulses near the target."],
  ["pulse_open_ms", "Pulse open time", "ms"],
  ["pulse_settle_ms", "Settle between pulses", "ms"],
  ["tolerance_g", "Accept within", "g", "Result counts as complete within this margin."],
  ["max_duration_ms", "Maximum run time", "ms", "Hard stop for the whole operation."],
  ["no_flow_timeout_ms", "Stop if no flow for", "ms", "Detects an empty or jammed container."],
  ["stable_tolerance_g", "Stable reading band", "g"],
  ["stable_window_ms", "Stable for", "ms"],
  ["settle_timeout_ms", "Final settle limit", "ms"],
];

export function SettingsModal({ open, onClose, device, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState({});
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (open && device) { setForm(Object.fromEntries(Object.entries(device.dispense_settings).map(([k, v]) => [k, String(v)]))); setErrors({}); } }, [open, device]);

  const save = async () => {
    setSaving(true);
    try {
      await devicesApi.updateSettings(device.id, Object.fromEntries(Object.entries(form).map(([k, v]) => [k, k === "auto_tune_inflight" ? v === "true" || v === true : Number(v)])));
      toast.success("Dispensing settings saved. They apply to the next dispense.");
      onSaved();
      onClose();
    } catch (e) {
      setErrors(fieldErrors(e));
      toast.error(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} size="lg" title="Dispensing strategy"
      description="These defaults are untested starting points. Tune them with the bench procedure in hardware/esp32/README.md. The firmware enforces its own hard limits regardless."
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button loading={saving} onClick={save}>Save settings</Button></>}>
      <label className="mb-4 flex items-start gap-3 rounded-2xl bg-mist px-4 py-3 text-[15px]">
        <input type="checkbox" className="mt-1 h-4 w-4 accent-canopy" checked={form.auto_tune_inflight === "true" || form.auto_tune_inflight === true}
          onChange={(e) => setForm((f) => ({ ...f, auto_tune_inflight: String(e.target.checked) }))} />
        <span><span className="font-semibold">Learn from each dispense</span><br /><span className="text-sm text-slate">Adjusts how early each container closes, based on the measured overshoot. Improves accuracy over time.</span></span>
      </label>
      <div className="grid gap-4 sm:grid-cols-2">
        {SETTING_FIELDS.map(([key, label, unit, hint]) => (
          <Input key={key} label={label} type="number" suffix={unit} value={form[key] ?? ""} hint={hint} error={errors[key]}
            onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))} />
        ))}
      </div>
    </Modal>
  );
}
