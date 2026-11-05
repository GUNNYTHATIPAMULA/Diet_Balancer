import { useEffect, useRef, useState } from "react";
import { CheckCircle2, ChevronDown, Cpu, Loader2, Wifi } from "lucide-react";
import { devicesApi, pairingApi } from "../../api/devices";
import { errorMessage } from "../../api/client";
import { useInterval } from "../../hooks/useInterval";
import { relativeTime } from "../../utils/format";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { Input } from "../ui/Field";

/** Six separate digit boxes; typing or pasting fills them in order. */
export function CodeInput({ value, onChange, disabled, invalid }) {
  const refs = useRef([]);
  const digits = value.padEnd(6, " ").slice(0, 6).split("");
  const set = (i, ch) => {
    const next = digits.map((d, j) => (j === i ? ch : d)).join("").replace(/\s+$/, "");
    onChange(next.replace(/ /g, ""));
  };
  const onKey = (i, e) => {
    if (e.key === "Backspace" && digits[i] === " " && i > 0) { refs.current[i - 1]?.focus(); set(i - 1, " "); e.preventDefault(); }
    if (e.key === "ArrowLeft" && i > 0) refs.current[i - 1]?.focus();
    if (e.key === "ArrowRight" && i < 5) refs.current[i + 1]?.focus();
  };
  const onInput = (i, e) => {
    const typed = e.target.value.replace(/\D/g, "");
    if (!typed) return set(i, " ");
    if (typed.length > 1) { // paste
      onChange(typed.slice(0, 6));
      refs.current[Math.min(typed.length, 5)]?.focus();
      return undefined;
    }
    set(i, typed);
    if (i < 5) refs.current[i + 1]?.focus();
    return undefined;
  };
  return (
    <div className="flex justify-center gap-2" role="group" aria-label="Pairing code">
      {digits.map((d, i) => (
        <input key={i} ref={(el) => (refs.current[i] = el)} value={d.trim()} disabled={disabled}
          onChange={(e) => onInput(i, e)} onKeyDown={(e) => onKey(i, e)} onFocus={(e) => e.target.select()}
          inputMode="numeric" autoComplete="one-time-code" maxLength={6} aria-label={`Digit ${i + 1}`}
          aria-invalid={invalid ? "true" : undefined}
          className={`num h-14 w-11 rounded-2xl border bg-white text-center font-display text-2xl font-semibold text-ink focus:outline-none focus:ring-4 sm:w-12 ${
            invalid ? "border-alert focus:ring-alert-light" : "border-line focus:border-leaf focus:ring-sprout/60"} ${i === 2 ? "mr-2" : ""}`} />
      ))}
    </div>
  );
}

function Radar() {
  return (
    <div className="relative mx-auto my-3 grid h-28 w-28 place-items-center" aria-hidden>
      <span className="absolute inset-0 animate-radar rounded-full bg-sprout" />
      <span className="absolute inset-0 animate-radar rounded-full bg-sprout [animation-delay:1.1s]" />
      <span className="absolute inset-4 rounded-full bg-sprout-light" />
      <span className="relative grid h-14 w-14 place-items-center rounded-full bg-canopy text-white"><Wifi className="h-6 w-6" /></span>
    </div>
  );
}

export function PairDeviceModal({ open, onClose, onPaired }) {
  const [step, setStep] = useState("search"); // search | code | done
  const [nearby, setNearby] = useState([]);
  const [searchError, setSearchError] = useState("");
  const [target, setTarget] = useState(null);
  const [code, setCode] = useState("");
  const [name, setName] = useState("Kitchen dispenser");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [paired, setPaired] = useState(null);
  const [online, setOnline] = useState(false);

  useEffect(() => {
    if (!open) return;
    setStep("search"); setNearby([]); setTarget(null); setCode(""); setError(""); setPaired(null); setOnline(false); setSearchError("");
  }, [open]);

  const scan = async () => {
    try {
      setNearby(await pairingApi.nearby());
      setSearchError("");
    } catch (e) {
      setSearchError(errorMessage(e));
    }
  };
  useEffect(() => { if (open && step === "search") scan(); }, [open, step]);
  useInterval(scan, open && step === "search" ? 3000 : null);

  // After pairing, wait for the dispenser to fetch its credentials and come online.
  useInterval(async () => {
    try {
      const d = await devicesApi.get(paired.device.id);
      if (d.is_online && d.is_registered) { setOnline(true); onPaired?.(d); }
    } catch { /* keep waiting */ }
  }, open && step === "done" && paired && !online ? 2000 : null);

  const connect = async () => {
    if (!/^\d{6}$/.test(code)) return setError("Enter all 6 digits shown on the dispenser’s screen.");
    setBusy(true);
    setError("");
    try {
      const result = await pairingApi.claim(code, name.trim() || "Kitchen dispenser");
      setPaired(result);
      setStep("done");
      onPaired?.(result.device);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const chooseDevice = (d) => {
    setTarget(d);
    setName(d?.suggested_name || "Kitchen dispenser");
    setCode("");
    setError("");
    setStep("code");
  };

  return (
    <Modal open={open} onClose={onClose} title={step === "done" ? "Dispenser connected" : "Connect a dispenser"} size="md"
      footer={
        step === "code" ? <><Button variant="ghost" onClick={() => setStep("search")}>Back</Button><Button loading={busy} onClick={connect}>Connect</Button></>
          : step === "done" ? <Button onClick={onClose}>{online ? "Done" : "Close"}</Button>
            : <Button variant="ghost" onClick={() => chooseDevice(null)}>I have a code</Button>
      }>
      {step === "search" && (
        <div className="space-y-5 pb-2">
          <div className="text-center">
            <Radar />
            <p className="mt-4 font-semibold">Looking for dispensers on your network…</p>
            <p className="mt-1 text-sm text-slate">Power on the dispenser. Its screen shows a 6-digit code when it’s ready to connect.</p>
          </div>
          {searchError && <p className="text-center text-sm text-alert">{searchError}</p>}
          {nearby.length > 0 && (
            <ul className="space-y-2" aria-label="Dispensers found nearby">
              {nearby.map((d) => (
                <li key={d.session_id} className="flex items-center gap-3 rounded-2xl border border-leaf/40 bg-sprout-light/60 px-4 py-3">
                  <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-white text-canopy"><Cpu className="h-5 w-5" aria-hidden /></span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold">{d.display_name}</p>
                    <p className="text-xs text-slate">
                      {d.already_yours ? "Your dispenser · reconnect" : "Found nearby"} · seen {relativeTime(d.last_seen_at)}
                      {d.hardware_info?.calibrated === false && " · scale not calibrated"}
                    </p>
                  </div>
                  <Button size="sm" onClick={() => chooseDevice(d)}>Connect</Button>
                </li>
              ))}
            </ul>
          )}
          <details className="group rounded-2xl bg-mist px-4 py-3 text-sm">
            <summary className="flex cursor-pointer list-none items-center justify-between font-semibold text-ink">
              Dispenser not showing up?
              <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" aria-hidden />
            </summary>
            <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-slate">
              <li>If its screen says <span className="font-semibold text-ink">Wi-Fi setup</span>, join the Wi-Fi network it shows (DietBalancer-…) with your phone, using the password on the screen. A setup page opens; choose your home Wi-Fi.</li>
              <li>Make sure this phone or computer is on the same Wi-Fi as the dispenser.</li>
              <li>If the screen says <span className="font-semibold text-ink">Server not found</span>, open its setup page and type this server’s address.</li>
              <li>If the screen already shows a code, choose <span className="font-semibold text-ink">I have a code</span> below.</li>
            </ol>
          </details>
        </div>
      )}

      {step === "code" && (
        <div className="space-y-6 pb-2">
          <p className="text-center text-[15px] text-slate">
            Enter the code shown on {target ? <span className="font-semibold text-ink">{target.display_name}</span> : "the dispenser’s screen"}.
            It proves you’re next to it.
          </p>
          <CodeInput value={code} onChange={(v) => { setCode(v); setError(""); }} disabled={busy} invalid={!!error} />
          {error && <p className="text-center text-sm text-alert" role="alert">{error}</p>}
          {!target?.already_yours && (
            <Input label="Name" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
          )}
          {target?.already_yours && <p className="text-center text-sm text-slate">This reconnects your existing dispenser and keeps its containers and history.</p>}
        </div>
      )}

      {step === "done" && paired && (
        <div className="space-y-4 py-4 text-center">
          {online ? (
            <CheckCircle2 className="mx-auto h-14 w-14 text-leaf" aria-hidden />
          ) : (
            <Loader2 className="mx-auto h-12 w-12 animate-spin text-leaf" aria-hidden />
          )}
          <p className="font-display text-xl font-semibold">{paired.device.name}</p>
          <p className="text-[15px] text-slate">
            {online ? "Online and ready. Next, tell it which container holds which food." : "Finishing setup on the dispenser… this takes a few seconds."}
          </p>
        </div>
      )}
    </Modal>
  );
}
