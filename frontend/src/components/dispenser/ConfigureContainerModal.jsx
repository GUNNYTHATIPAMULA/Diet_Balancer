import { useEffect, useRef, useState } from "react";
import { BadgeCheck, ChevronDown, ImagePlus, Search, Trash2 } from "lucide-react";
import { devicesApi, containersApi } from "../../api/devices";
import { lookupApi } from "../../api/foods";
import { errorMessage } from "../../api/client";
import { useDebounce } from "../../hooks/useDebounce";
import { useToast } from "../../context/ToastContext";
import { ALLERGENS } from "../../utils/constants";
import { CategoryTags, mediaUrl } from "../../utils/nutrition";
import { resizeImage } from "../../utils/image";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { Input, Select } from "../ui/Field";
import { Badge } from "../ui/Feedback";

const DIET_OPTIONS = [
  { value: "unknown", label: "Not sure" },
  { value: "vegan", label: "Vegan" },
  { value: "vegetarian", label: "Vegetarian (may contain dairy)" },
  { value: "eggetarian", label: "Contains egg" },
  { value: "non_vegetarian", label: "Non-vegetarian" },
];

function Per100({ c }) {
  return (
    <dl className="num grid grid-cols-5 gap-1 text-center">
      {[["kcal", c.calories_per_100g, "text-canopy"], ["Protein", c.protein_per_100g, "text-river"], ["Carbs", c.carbs_per_100g, "text-wheat"],
        ["Fat", c.fat_per_100g, "text-beet"], ["Fiber", c.fiber_per_100g, "text-leaf"]].map(([k, v, cls]) => (
        <div key={k} className="rounded-xl bg-mist px-1 py-1.5">
          <dd className={`font-display text-[15px] font-semibold ${cls}`}>{k === "kcal" ? Math.round(v) : Number(v).toFixed(1)}</dd>
          <dt className="text-[11px] text-slate">{k === "kcal" ? "kcal" : `g ${k.toLowerCase()}`}</dt>
        </div>
      ))}
    </dl>
  );
}

function CandidateCard({ c, selected, onSelect }) {
  return (
    <button type="button" onClick={onSelect} aria-pressed={selected}
      className={`w-full rounded-2xl border p-3.5 text-left transition-colors ${selected ? "border-leaf bg-sprout-light/60 ring-1 ring-leaf" : "border-line bg-white hover:border-leaf/40"}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-ink">{c.name}</p>
          <p className="text-xs text-slate">per 100 g{c.dispenser_friendly ? " · dry/raw: suits a dispenser" : ""}</p>
        </div>
        {c.source === "usda_fdc" ? <Badge tone="blue"><BadgeCheck className="h-3 w-3" aria-hidden />USDA verified</Badge>
          : c.is_custom ? <Badge tone="neutral">Your food</Badge> : <Badge tone="amber">Reference value</Badge>}
      </div>
      <div className="mt-2.5"><CategoryTags categories={c.categories} /></div>
      <div className="mt-2.5"><Per100 c={c} /></div>
    </button>
  );
}

/** Configure a container: hardware mapping + the food inside (identified, confirmed) + optional photo. */
export function ConfigureContainerModal({ open, onClose, device, container, onSaved }) {
  const toast = useToast();
  const [step, setStep] = useState("food"); // food | confirm
  const [label, setLabel] = useState("");
  const [query, setQuery] = useState("");
  const q = useDebounce(query.trim(), 350);
  const [result, setResult] = useState(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [picked, setPicked] = useState(null);
  const [dietType, setDietType] = useState("unknown");
  const [allergens, setAllergens] = useState([]);
  const [photo, setPhoto] = useState(null);       // data URL of a new photo
  const [removePhoto, setRemovePhoto] = useState(false);
  const [hw, setHw] = useState({ slot_number: "", servo_channel: "", open_angle: "70", closed_angle: "0", is_enabled: true });
  const [hwOpen, setHwOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const fileRef = useRef(null);
  const isNew = !container;

  useEffect(() => {
    if (!open) return;
    setStep("food"); setResult(null); setPicked(null); setSearchError(""); setPhoto(null); setRemovePhoto(false);
    setDietType("unknown"); setAllergens([]);
    if (container) {
      setLabel(container.label);
      setQuery(container.food?.name || "");
      setHw({ slot_number: String(container.slot_number), servo_channel: String(container.servo_channel),
        open_angle: String(container.open_angle), closed_angle: String(container.closed_angle), is_enabled: container.is_enabled });
      setHwOpen(false);
    } else {
      const usedSlots = device.containers.map((c) => c.slot_number);
      const usedServos = device.containers.map((c) => c.servo_channel);
      const slot = [1, 2, 3, 4, 5, 6, 7, 8].find((n) => !usedSlots.includes(n)) ?? 1;
      const servo = [0, 1, 2, 3, 4, 5, 6, 7].find((n) => !usedServos.includes(n)) ?? 0;
      setLabel(`Container ${slot}`);
      setQuery("");
      setHw({ slot_number: String(slot), servo_channel: String(servo), open_angle: "70", closed_angle: "0", is_enabled: true });
      setHwOpen(true);
    }
  }, [open, container, device]);

  useEffect(() => {
    if (!open || q.length < 2) { setResult(null); return undefined; }
    let cancelled = false;
    setSearching(true);
    setSearchError("");
    lookupApi.identify(q)
      .then((r) => {
        if (cancelled) return;
        setResult(r);
        // Keep the current food selected when editing; otherwise suggest the best match.
        const current = container?.food && r.candidates.find((c) => c.food_id === container.food.id);
        setPicked(current || r.candidates[0] || null);
      })
      .catch((e) => !cancelled && setSearchError(errorMessage(e)))
      .finally(() => !cancelled && setSearching(false));
    return () => { cancelled = true; };
  }, [q, open, container]);

  const choosePhoto = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      setPhoto(await resizeImage(file));
      setRemovePhoto(false);
    } catch (err) {
      toast.error(err.message);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      const hwBody = { label: label.trim() || `Container ${hw.slot_number}`, servo_channel: Number(hw.servo_channel),
        open_angle: Number(hw.open_angle), closed_angle: Number(hw.closed_angle), is_enabled: hw.is_enabled };
      if (hwBody.open_angle === hwBody.closed_angle) throw new Error("Open and closed angles must be different.");
      let target = container;
      if (isNew) {
        target = await devicesApi.addContainer(device.id, { ...hwBody, slot_number: Number(hw.slot_number) });
      } else {
        target = await devicesApi.updateContainer(device.id, container.id, hwBody);
      }
      let foodId = picked.food_id;
      if (picked.source === "usda_fdc") {
        foodId = (await lookupApi.importFood(picked.external_id, dietType, allergens)).id;
      }
      if (isNew || foodId !== container.food?.id) {
        target = await containersApi.assignFood(device.id, target.id, foodId, hwBody.label);
      }
      if (photo) target = await containersApi.setImage(device.id, target.id, photo);
      else if (removePhoto && container?.image_url) target = await containersApi.removeImage(device.id, target.id);
      toast.success(`${target.label} now holds ${target.food.name}.`);
      onSaved();
      onClose();
    } catch (e) {
      toast.error(e.response ? errorMessage(e) : e.message);
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

  const currentImage = photo || (!removePhoto && mediaUrl(container?.image_url));
  const servoCount = device?.hardware_info?.servo_count;

  return (
    <Modal open={open} onClose={onClose} size="lg"
      title={step === "confirm" ? "Confirm container" : isNew ? "Configure a new container" : `Configure ${container.label}`}
      description={step === "confirm" ? "Check this before saving. Nutrition comes from the food database, not from you."
        : "Type the food that's inside. We'll identify it and look up its nutrition."}
      footer={step === "food" ? (
        <>
          {!isNew && <Button variant="danger-soft" className="mr-auto" icon={Trash2} onClick={remove} disabled={saving}>Remove</Button>}
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={!picked} onClick={() => setStep("confirm")}>Continue</Button>
        </>
      ) : (
        <>
          <Button variant="ghost" onClick={() => setStep("food")}>Back</Button>
          <Button loading={saving} onClick={save}>Confirm and save</Button>
        </>
      )}>
      {step === "food" && (
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
            <Input label="Container name" value={label} maxLength={60} onChange={(e) => setLabel(e.target.value)} />
            <div>
              <p className="mb-1.5 text-sm font-semibold">Photo <span className="font-normal text-slate">(optional)</span></p>
              <div className="flex items-center gap-2">
                <button type="button" onClick={() => fileRef.current?.click()}
                  className="grid h-[46px] w-[46px] place-items-center overflow-hidden rounded-xl border border-dashed border-line bg-mist text-slate hover:border-leaf"
                  aria-label={currentImage ? "Change photo" : "Add photo"}>
                  {currentImage ? <img src={currentImage} alt="" className="h-full w-full object-cover" /> : <ImagePlus className="h-5 w-5" />}
                </button>
                {currentImage && <Button size="sm" variant="ghost" onClick={() => { setPhoto(null); setRemovePhoto(true); }}>Remove</Button>}
                <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={choosePhoto} />
              </div>
            </div>
          </div>

          <div>
            <label htmlFor="food-name" className="mb-1.5 block text-sm font-semibold">What food is in this container?</label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate" aria-hidden />
              <input id="food-name" className="field-input pl-10" placeholder="e.g. rice, oats, almonds, anda"
                value={query} onChange={(e) => setQuery(e.target.value)} autoFocus={isNew} />
            </div>
            <p className="mt-1.5 text-sm text-slate">Just the name. You never need to enter calories or macros.</p>
          </div>

          {searching && <p className="text-sm text-slate">Identifying “{q}”…</p>}
          {searchError && <p className="text-sm text-alert">{searchError}</p>}
          {result?.external_error && <p className="text-sm text-[#7A5A12]">{result.external_error} Showing the built-in catalogue.</p>}
          {result && !searching && result.candidates.length === 0 && (
            <p className="rounded-2xl bg-mist px-4 py-3 text-sm text-slate">
              No match for “{q}”. Try another name (for example “rice” or “badam”), or add it as a custom food in the Food Tracker first.
            </p>
          )}
          {result?.candidates?.length > 0 && (
            <div className="space-y-2.5" role="group" aria-label="Matching foods">
              <p className="text-sm font-semibold">Choose the exact food</p>
              <div className="max-h-[42vh] space-y-2.5 overflow-y-auto pr-1">
                {result.candidates.map((c) => (
                  <CandidateCard key={c.food_id || c.external_id} c={c}
                    selected={picked && (picked.food_id || picked.external_id) === (c.food_id || c.external_id)}
                    onSelect={() => setPicked(c)} />
                ))}
              </div>
            </div>
          )}

          <div className="rounded-2xl border border-line">
            <button type="button" onClick={() => setHwOpen((v) => !v)} aria-expanded={hwOpen}
              className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold">
              Servo settings (hardware)
              <ChevronDown className={`h-4 w-4 transition-transform ${hwOpen ? "rotate-180" : ""}`} aria-hidden />
            </button>
            {hwOpen && (
              <div className="space-y-4 border-t border-line px-4 py-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input label="Slot number" type="number" min="1" max="16" value={hw.slot_number} disabled={!isNew}
                    onChange={(e) => setHw((h) => ({ ...h, slot_number: e.target.value }))} />
                  <Input label="Servo channel" type="number" min="0" max="15" value={hw.servo_channel}
                    hint={servoCount ? `This dispenser has ${servoCount} servo(s): 0 = GPIO 13, 1 = GPIO 14.` : "0 = GPIO 13, 1 = GPIO 14"}
                    onChange={(e) => setHw((h) => ({ ...h, servo_channel: e.target.value }))} />
                  <Input label="Open angle" type="number" min="0" max="180" suffix="°" value={hw.open_angle}
                    onChange={(e) => setHw((h) => ({ ...h, open_angle: e.target.value }))} />
                  <Input label="Closed angle" type="number" min="0" max="180" suffix="°" value={hw.closed_angle}
                    onChange={(e) => setHw((h) => ({ ...h, closed_angle: e.target.value }))} />
                </div>
                <p className="text-sm text-slate">Find the real positions with the serial command <code>servo 0 0</code> / <code>servo 0 70</code> before dispensing.</p>
                <label className="flex items-center gap-3 text-[15px]">
                  <input type="checkbox" checked={hw.is_enabled} onChange={(e) => setHw((h) => ({ ...h, is_enabled: e.target.checked }))} className="h-4 w-4 accent-canopy" />
                  Enabled for dispensing
                </label>
              </div>
            )}
          </div>
        </div>
      )}

      {step === "confirm" && picked && (
        <div className="space-y-4">
          <div className="flex items-center gap-4 rounded-2xl bg-mist p-4">
            {currentImage ? <img src={currentImage} alt="" className="h-16 w-16 rounded-2xl object-cover" />
              : <div className="grid h-16 w-16 place-items-center rounded-2xl bg-white font-display text-xl font-semibold text-canopy">{hw.slot_number}</div>}
            <div>
              <p className="text-sm text-slate">{label || `Container ${hw.slot_number}`} · servo {hw.servo_channel}</p>
              <p className="font-display text-xl font-semibold">{picked.name}</p>
              <div className="mt-1.5"><CategoryTags categories={picked.categories} /></div>
            </div>
          </div>
          <Per100 c={picked} />
          <ul className="space-y-1 text-sm text-slate">
            {picked.classification_reasons.map((r) => <li key={r}>• {r}</li>)}
          </ul>
          <p className="text-xs text-slate">Source: {picked.data_source}</p>
          {picked.source === "usda_fdc" && (
            <div className="space-y-3 rounded-2xl border border-line p-4">
              <p className="text-sm font-semibold">A couple of details the database doesn’t include</p>
              <Select label="Diet type" options={DIET_OPTIONS} value={dietType} onChange={(e) => setDietType(e.target.value)}
                hint="Used so meal suggestions respect vegetarian/vegan preferences." />
              <div>
                <p className="mb-2 text-sm font-semibold">Contains allergens</p>
                <div className="flex flex-wrap gap-2">
                  {ALLERGENS.map((a) => {
                    const on = allergens.includes(a.value);
                    return (
                      <button key={a.value} type="button" aria-pressed={on}
                        onClick={() => setAllergens(on ? allergens.filter((x) => x !== a.value) : [...allergens, a.value])}
                        className={`rounded-full px-3 py-1 text-sm font-medium ring-1 ${on ? "bg-sprout-light text-canopy ring-leaf" : "bg-white text-slate ring-line"}`}>{a.label}</button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
