import { useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
import { devicesApi } from "../../api/devices";
import { errorMessage, fieldErrors } from "../../api/client";
import { useToast } from "../../context/ToastContext";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { Input } from "../ui/Field";
import { FoodPicker } from "../FoodPicker";

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

const EMPTY = { slot_number: "", servo_channel: "", label: "", food: null, open_angle: "90", closed_angle: "0", capacity_g: "", estimated_remaining_g: "", is_enabled: true };

export function ContainerModal({ open, onClose, device, container, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const servoCount = device?.hardware_info?.servo_count;

  useEffect(() => {
    if (!open) return;
    setErrors({});
    if (container) {
      setForm({ ...container, food: container.food, capacity_g: container.capacity_g ?? "", estimated_remaining_g: container.estimated_remaining_g ?? "",
        open_angle: String(container.open_angle), closed_angle: String(container.closed_angle) });
    } else {
      const usedSlots = device.containers.map((c) => c.slot_number);
      const usedServos = device.containers.map((c) => c.servo_channel);
      const slot = [1, 2, 3, 4, 5, 6, 7, 8].find((n) => !usedSlots.includes(n)) ?? "";
      const servo = [0, 1, 2, 3, 4, 5, 6, 7].find((n) => !usedServos.includes(n)) ?? "";
      setForm({ ...EMPTY, slot_number: String(slot), servo_channel: String(servo), label: `Container ${slot}` });
    }
  }, [open, container, device]);

  const set = (k, v) => { setForm((f) => ({ ...f, [k]: v })); setErrors((e) => ({ ...e, [k]: undefined })); };

  const save = async () => {
    const body = {
      label: form.label.trim(), servo_channel: Number(form.servo_channel), open_angle: Number(form.open_angle), closed_angle: Number(form.closed_angle),
      capacity_g: form.capacity_g === "" ? null : Number(form.capacity_g),
      estimated_remaining_g: form.estimated_remaining_g === "" ? null : Number(form.estimated_remaining_g),
      is_enabled: form.is_enabled,
    };
    if (!body.label) return setErrors({ label: "Enter a label." });
    if (body.open_angle === body.closed_angle) return setErrors({ open_angle: "Open and closed angles must differ." });
    setSaving(true);
    try {
      if (container) {
        await devicesApi.updateContainer(device.id, container.id, { ...body, food_item_id: form.food?.id ?? null, clear_food: !form.food });
      } else {
        await devicesApi.addContainer(device.id, { ...body, slot_number: Number(form.slot_number), food_item_id: form.food?.id ?? null });
      }
      toast.success(`${body.label} saved.`);
      onSaved();
      onClose();
    } catch (e) {
      setErrors(fieldErrors(e));
      toast.error(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    setSaving(true);
    try {
      await devicesApi.removeContainer(device.id, container.id);
      toast.success(`${container.label} removed.`);
      onSaved();
      onClose();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} size="lg" title={container ? `Edit ${container.label}` : "Add a container"}
      description="Map a physical container to the servo that opens it, and to the food inside."
      footer={<>
        {container && <Button variant="danger-soft" className="mr-auto" onClick={remove} disabled={saving}>Remove</Button>}
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button loading={saving} onClick={save}>Save container</Button>
      </>}>
      <div className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-3">
          <Input label="Label" value={form.label} onChange={(e) => set("label", e.target.value)} error={errors.label} />
          <Input label="Slot number" type="number" min="1" max="16" value={form.slot_number} disabled={!!container} onChange={(e) => set("slot_number", e.target.value)} error={errors.slot_number} />
          <Input label="Servo channel" type="number" min="0" max="15" value={form.servo_channel} onChange={(e) => set("servo_channel", e.target.value)} error={errors.servo_channel}
            hint={servoCount ? `This dispenser reports ${servoCount} servo(s): 0 = GPIO 13, 1 = GPIO 14.` : "0 = GPIO 13, 1 = GPIO 14 in the default firmware."} />
        </div>
        <div>
          <p className="mb-1.5 text-sm font-semibold">Food in this container</p>
          {form.food ? (
            <div className="flex items-center justify-between rounded-2xl bg-sprout-light px-4 py-3">
              <p className="font-semibold">{form.food.name}</p>
              <Button size="sm" variant="ghost" onClick={() => set("food", null)}>Change</Button>
            </div>
          ) : <FoodPicker onSelect={(f) => set("food", f)} placeholder="Search e.g. rice raw, oats dry" />}
          <p className="mt-1.5 text-sm text-slate">Dispensers usually hold dry food, so pick the dry/raw entry (e.g. “Rolled oats (dry)”) for accurate nutrition.</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Open angle" type="number" min="0" max="180" suffix="°" value={form.open_angle} onChange={(e) => set("open_angle", e.target.value)} error={errors.open_angle} />
          <Input label="Closed angle" type="number" min="0" max="180" suffix="°" value={form.closed_angle} onChange={(e) => set("closed_angle", e.target.value)} error={errors.closed_angle} />
        </div>
        <p className="-mt-2 text-sm text-slate">Starting values only. Confirm the real open and closed positions with the firmware’s serial <code>servo</code> test before dispensing.</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Capacity (optional)" type="number" suffix="g" value={form.capacity_g} onChange={(e) => set("capacity_g", e.target.value)} />
          <Input label="Currently filled (optional)" type="number" suffix="g" value={form.estimated_remaining_g} onChange={(e) => set("estimated_remaining_g", e.target.value)}
            hint="Reduced automatically by each measured dispense." />
        </div>
        <label className="flex items-center gap-3 text-[15px]">
          <input type="checkbox" checked={form.is_enabled} onChange={(e) => set("is_enabled", e.target.checked)} className="h-4 w-4 rounded accent-canopy" />
          Enabled for dispensing
        </label>
      </div>
    </Modal>
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
      await devicesApi.updateSettings(device.id, Object.fromEntries(Object.entries(form).map(([k, v]) => [k, Number(v)])));
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
      <div className="grid gap-4 sm:grid-cols-2">
        {SETTING_FIELDS.map(([key, label, unit, hint]) => (
          <Input key={key} label={label} type="number" suffix={unit} value={form[key] ?? ""} hint={hint} error={errors[key]}
            onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))} />
        ))}
      </div>
    </Modal>
  );
}
