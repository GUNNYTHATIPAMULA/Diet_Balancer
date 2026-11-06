import { useCallback, useEffect, useRef, useState } from "react";
import { AlertOctagon, Cpu, Gauge, Plus, RotateCcw, Scale, Settings2, ShieldCheck, Wifi, WifiOff, Trash2 } from "lucide-react";
import { devicesApi, dispenserApi, mealPlansApi } from "../api/devices";
import { errorMessage } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { useInterval } from "../hooks/useInterval";
import { useToast } from "../context/ToastContext";
import { mealLabel } from "../utils/constants";
import { newIdempotencyKey, relativeTime, todayISO } from "../utils/format";
import { PageHeader } from "../components/PageHeader";
import { Button } from "../components/ui/Button";
import { Badge, EmptyState, ErrorState, PageSkeleton } from "../components/ui/Feedback";
import { ConfirmDialog } from "../components/ui/Modal";
import { CopyButton, SettingsModal } from "../components/dispenser/DeviceModals";
import { ConfigureContainerModal } from "../components/dispenser/ConfigureContainerModal";
import { ContainerCard } from "../components/dispenser/ContainerCard";
import { MealPlanner } from "../components/dispenser/MealPlanner";
import { LiveDispensing, StatusPill, TERMINAL } from "../components/dispenser/LiveDispensing";
import { AccuracyBadge, defaultMealType } from "../utils/nutrition";
import { PairDeviceModal } from "../components/dispenser/PairDeviceModal";

function signal(rssi) {
  if (rssi == null) return "Unknown";
  if (rssi >= -60) return `Strong (${rssi} dBm)`;
  if (rssi >= -72) return `Fair (${rssi} dBm)`;
  return `Weak (${rssi} dBm)`;
}

export default function DispenserPage() {
  const toast = useToast();
  const devices = useAsync(() => devicesApi.list(), []);
  const [selectedId, setSelectedId] = useState(null);
  const [command, setCommand] = useState(null);
  const [plan, setPlan] = useState(null);
  const [mealKey, setMealKey] = useState(0);  // refreshes "left today" after something is logged
  const mealDefault = defaultMealType();
  const [busy, setBusy] = useState(false);
  const [modals, setModals] = useState({ add: false, container: null, settings: false, remove: false, stop: false });
  const pendingKey = useRef(null);

  const list = devices.data || [];
  const device = list.find((d) => d.id === selectedId) || list[0];
  const history = useAsync(() => (device ? dispenserApi.list(device.id, 8) : Promise.resolve([])), [device?.id]);
  const events = useAsync(() => (device ? devicesApi.events(device.id, 8) : Promise.resolve([])), [device?.id]);

  const refreshAll = useCallback(() => {
    devices.reload({ silent: true });
    history.reload({ silent: true });
    events.reload({ silent: true });
  }, [devices, history, events]);

  // Pick up a command that was already running (e.g. after a page refresh).
  useEffect(() => {
    if (device?.active_command_id && (!command || command.id !== device.active_command_id)) {
      dispenserApi.get(device.active_command_id).then((c) => {
        if (c.meal_plan_id) {
          if (!plan || plan.id !== c.meal_plan_id) mealPlansApi.get(c.meal_plan_id).then(setPlan).catch(() => {});
        } else setCommand(c);
      }).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [device?.active_command_id]);

  useInterval(() => devices.reload({ silent: true }), 5000);
  const active = command && !TERMINAL.includes(command.status);
  const planActive = plan && ["proposed", "serving"].includes(plan.status);
  useInterval(async () => {
    try {
      const next = await mealPlansApi.get(plan.id);
      setPlan(next);
      if (!["proposed", "serving"].includes(next.status)) {
        refreshAll();
        setMealKey((k) => k + 1);
        if (next.status === "completed") toast.success("Meal served. Measured amounts were added to your log.");
        else toast.error(next.status === "partial" ? "Meal partly served. Check the details below." : `Meal ${next.status}.`);
      }
    } catch { /* transient; next tick retries */ }
  }, planActive ? 1000 : null);
  useInterval(async () => {
    try {
      const next = await dispenserApi.get(command.id);
      setCommand(next);
      if (TERMINAL.includes(next.status)) {
        refreshAll();
        setMealKey((k) => k + 1);
        if (next.status === "completed" && next.command_type === "dispense") toast.success(`Dispensed ${next.dispensed_weight_g} g (measured).`);
        else if (next.status !== "completed") toast.error(next.error_message || `Dispense ${next.status}.`);
      }
    } catch { /* transient; next tick retries */ }
  }, active ? 1000 : null);

  const send = async (body) => {
    // Reuse the key if the previous attempt failed on the network, so a retry can't double-dispense.
    if (!pendingKey.current) pendingKey.current = newIdempotencyKey();
    setBusy(true);
    try {
      const created = await dispenserApi.create(body, pendingKey.current);
      pendingKey.current = null;
      setPlan(null);
      setCommand(created);
      devices.reload({ silent: true });
    } catch (e) {
      if (e.response) pendingKey.current = null; // server answered; a new click is a new request
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const dispense = (container, grams, meal) =>
    send({ device_id: device.id, command_type: "dispense", container_id: container.id, target_weight_g: grams, meal_type: meal, consumed_on: todayISO(), log_to_meals: true });
  const tare = () => send({ device_id: device.id, command_type: "tare" });

  const cancel = async () => {
    setBusy(true);
    try { setCommand(await dispenserApi.cancel(command.id)); } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  const logMeasured = async (cmd) => {
    setBusy(true);
    try {
      const updated = await dispenserApi.logMeasured(cmd.id);
      if (plan) setPlan(await mealPlansApi.get(plan.id)); else setCommand(updated);
      setMealKey((k) => k + 1);
      toast.success("Measured amount added to your log.");
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  const stopMeal = async () => {
    setBusy(true);
    try { setPlan(await mealPlansApi.stop(plan.id)); } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  const emergencyStop = async () => {
    setBusy(true);
    try {
      await devicesApi.emergencyStop(device.id, "Stopped from the web app");
      toast.info("Emergency stop sent. New requests are blocked until you reset it.");
      setModals((m) => ({ ...m, stop: false }));
      refreshAll();
      if (command) dispenserApi.get(command.id).then(setCommand).catch(() => {});
      if (plan) mealPlansApi.get(plan.id).then(setPlan).catch(() => {});
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  const resetStop = async () => {
    try { await devicesApi.resetEmergencyStop(device.id); toast.success("Emergency stop cleared."); refreshAll(); } catch (e) { toast.error(errorMessage(e)); }
  };
  const removeDevice = async () => {
    try {
      await devicesApi.remove(device.id);
      toast.success(`${device.name} removed.`);
      setModals((m) => ({ ...m, remove: false }));
      setSelectedId(null);
      setCommand(null);
      devices.reload();
    } catch (e) { toast.error(errorMessage(e)); setModals((m) => ({ ...m, remove: false })); }
  };

  if (devices.loading && !devices.data) return <PageSkeleton />;
  if (devices.error && !devices.data) return <ErrorState message={errorMessage(devices.error)} onRetry={devices.reload} />;

  const addModal = <PairDeviceModal open={modals.add} onClose={() => setModals((m) => ({ ...m, add: false }))} onPaired={(d) => { setSelectedId(d.id); devices.reload({ silent: true }); }} />;

  if (!device) {
    return (
      <div>
        {/* The pairing dialog is the FIRST child in both layouts so React keeps it mounted
            (and keeps its "connected" step) when the page switches to the device view. */}
        {addModal}
        <PageHeader title="Smart Dispenser" subtitle="Weigh and log food straight from your ESP32 dispenser." />
        <div className="panel">
          <EmptyState icon={Cpu} title="Connect your dispenser" action={<Button icon={Wifi} onClick={() => setModals((m) => ({ ...m, add: true }))}>Connect a dispenser</Button>}>
            Power it on and keep this device on the same Wi-Fi. When the dispenser’s screen shows a 6-digit code, enter it here. No code editing needed.
          </EmptyState>
        </div>
      </div>
    );
  }

  const hw = device.hardware_info || {};
  const stopped = device.emergency_stop_active;
  const disabledReason = stopped ? "Emergency stop is active."
    : !device.is_registered ? "Waiting for the dispenser to connect for the first time."
    : !device.is_online ? "Dispenser is offline."
    : hw.hx711_ready === false ? "The scale isn’t responding."
    : hw.calibrated === false ? "The scale isn’t calibrated."
    : active || planActive ? "The dispenser is busy serving." : null;

  return (
    <div className="space-y-6">
      {addModal}
      <PageHeader title="Smart Dispenser" subtitle="Every logged amount is the weight the load cell measured, not the amount requested."
        actions={<>
          {list.length > 1 && (
            <select className="field-input w-auto py-2" value={device.id} onChange={(e) => { setSelectedId(e.target.value); setCommand(null); }} aria-label="Choose dispenser">
              {list.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          )}
          <Button variant="secondary" icon={Wifi} onClick={() => setModals((m) => ({ ...m, add: true }))}>Connect a dispenser</Button>
        </>} />

      {stopped && (
        <div className="flex flex-col gap-3 rounded-3xl border border-alert/30 bg-alert-light p-5 sm:flex-row sm:items-center" role="alert">
          <AlertOctagon className="h-6 w-6 shrink-0 text-alert" aria-hidden />
          <p className="flex-1 text-[15px] text-ink"><span className="font-semibold">Emergency stop is active.</span> The dispenser keeps every gate closed and refuses new requests. Check the hardware before resetting.</p>
          <Button variant="secondary" icon={RotateCcw} onClick={resetStop}>Reset emergency stop</Button>
        </div>
      )}

      {/* Device status */}
      <section className="panel p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
          <div className="flex flex-1 items-start gap-4">
            <span className={`grid h-14 w-14 shrink-0 place-items-center rounded-2xl ${device.is_online ? "bg-sprout-light text-canopy" : "bg-mist text-slate"}`}><Cpu className="h-7 w-7" aria-hidden /></span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-xl font-semibold">{device.name}</h2>
                <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${device.is_online ? "bg-sprout-light text-canopy" : "bg-mist text-slate"}`}>
                  <span className={`h-2 w-2 rounded-full ${device.is_online ? "animate-pulse-dot bg-leaf" : "bg-slate-light"}`} aria-hidden />
                  {device.is_online ? "Online" : device.is_registered ? "Offline" : "Never connected"}
                </span>
                {device.device_state && device.is_online && <Badge tone="neutral" className="capitalize">{device.device_state}</Badge>}
              </div>
              <p className="mt-1 flex flex-wrap items-center gap-1 text-sm text-slate">
                ID <code className="truncate rounded bg-mist px-1.5 py-0.5 text-xs text-ink">{device.id}</code><CopyButton text={device.id} />
              </p>
              <p className="text-sm text-slate">Last heartbeat {relativeTime(device.last_heartbeat_at)}{device.hardware_id ? ` · hardware ${device.hardware_id}` : ""}</p>
            </div>
          </div>
          <div className="flex items-center gap-4 rounded-2xl bg-mist px-5 py-4">
            <Scale className="h-6 w-6 text-slate" aria-hidden />
            <div>
              <p className="text-sm text-slate">On the scale</p>
              <p className="num font-display text-3xl font-semibold">{device.is_online && device.last_weight_g != null ? `${device.last_weight_g} g` : "—"}</p>
            </div>
            <Button size="sm" variant="secondary" onClick={tare} disabled={!!disabledReason} loading={busy && !command}>Zero</Button>
          </div>
        </div>
        <dl className="mt-6 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          {[
            [device.is_online ? Wifi : WifiOff, "Wi-Fi", device.ip_address ? `${device.ip_address} · ${signal(device.wifi_rssi)}` : "Not reported"],
            [Cpu, "Firmware", device.firmware_version || "Not reported"],
            [Scale, "Load cell", hw.hx711_ready == null ? "Not reported" : hw.hx711_ready ? (hw.calibrated ? "Ready, calibrated" : "Ready, NOT calibrated") : "Not responding"],
            [ShieldCheck, "Servos / display", hw.servo_count == null ? "Not reported" : `${hw.servo_count} servos · OLED ${hw.oled_ready ? "OK" : "not found"}`],
          ].map(([Icon, k, v]) => (
            <div key={k} className="flex items-start gap-2.5 rounded-2xl border border-line px-4 py-3">
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-slate" aria-hidden />
              <div><dt className="text-slate">{k}</dt><dd className="font-semibold text-ink">{v}</dd></div>
            </div>
          ))}
        </dl>
        <div className="mt-5 flex flex-wrap gap-2">
          <Button variant="danger" icon={AlertOctagon} disabled={stopped} onClick={() => setModals((m) => ({ ...m, stop: true }))}>Emergency stop</Button>
          <Button variant="secondary" icon={Settings2} onClick={() => setModals((m) => ({ ...m, settings: true }))}>Dispensing strategy</Button>
          <Button variant="ghost" icon={Trash2} onClick={() => setModals((m) => ({ ...m, remove: true }))}>Remove</Button>
        </div>
      </section>

      {(plan && plan.status !== "proposed") || command ? (
        <LiveDispensing plan={plan && plan.status !== "proposed" ? plan : null} command={plan ? null : command} busy={busy}
          onStopMeal={stopMeal} onCancelCommand={cancel} onLogMeasured={logMeasured}
          onEmergencyStop={() => setModals((m) => ({ ...m, stop: true }))}
          onDismiss={() => { setPlan(null); setCommand(null); }} />
      ) : null}

      {device.containers.some((c) => c.food) && (
        <MealPlanner device={device} defaultMeal={mealDefault} disabledReason={disabledReason} refreshKey={mealKey}
          onServed={(p) => { setCommand(null); setPlan(p); devices.reload({ silent: true }); }} />
      )}

      {/* Containers */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xl font-semibold">Containers</h2>
          <Button size="sm" variant="soft" icon={Plus} onClick={() => setModals((m) => ({ ...m, container: "new" }))}>Configure new container</Button>
        </div>
        {device.containers.length === 0 ? (
          <div className="panel"><EmptyState icon={Gauge} title="Set up your first container" action={<Button icon={Plus} onClick={() => setModals((m) => ({ ...m, container: "new" }))}>Configure container</Button>}>
            Just type the food that’s inside (for example “rice” or “almonds”). The app identifies it and looks up its nutrition, then you choose which servo opens it.
          </EmptyState></div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {device.containers.map((c) => (
              <ContainerCard key={c.id} container={c} busy={busy} defaultMeal={mealDefault} disabledReason={disabledReason}
                onServe={dispense} onConfigure={(x) => setModals((m) => ({ ...m, container: x }))} />
            ))}
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="panel p-6">
          <h2 className="mb-4 text-lg font-semibold">Recent dispenses</h2>
          {history.data?.length ? (
            <ul className="divide-y divide-line">
              {history.data.map((h) => (
                <li key={h.id} className="flex items-center gap-3 py-2.5 text-sm">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold">{h.command_type === "tare" ? "Zero scale" : `${h.food_name || "Food"} · ${h.container_label || ""}`}</p>
                    <p className="num text-xs text-slate">{new Date(h.created_at).toLocaleString()}{h.command_type === "dispense" && ` · ${mealLabel(h.meal_type)}`}</p>
                  </div>
                  {h.command_type === "dispense" && (
                    <span className="num text-right text-xs text-slate">asked {h.target_weight_g} g<br /><span className="font-semibold text-ink">got {h.dispensed_weight_g ?? "—"}{h.dispensed_weight_g != null && " g"}</span></span>
                  )}
                  {h.accuracy ? <AccuracyBadge command={h} /> : <StatusPill status={h.status} />}
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-slate">No dispense requests yet.</p>}
        </section>
        <section className="panel p-6">
          <h2 className="mb-4 text-lg font-semibold">Device events</h2>
          {events.data?.length ? (
            <ul className="space-y-2.5">
              {events.data.map((e) => (
                <li key={e.id} className="flex gap-3 text-sm">
                  <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${e.severity === "error" ? "bg-alert" : e.severity === "warning" ? "bg-wheat" : "bg-leaf"}`} aria-hidden />
                  <div className="min-w-0">
                    <p className="text-ink">{e.message}</p>
                    <p className="text-xs text-slate">{relativeTime(e.created_at)}</p>
                  </div>
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-slate">No events yet.</p>}
        </section>
      </div>

      <ConfigureContainerModal open={!!modals.container} device={device} container={modals.container === "new" ? null : modals.container}
        onClose={() => setModals((m) => ({ ...m, container: null }))} onSaved={() => devices.reload({ silent: true })} />
      <SettingsModal open={modals.settings} device={device} onClose={() => setModals((m) => ({ ...m, settings: false }))} onSaved={() => devices.reload({ silent: true })} />
      <ConfirmDialog open={modals.stop} title="Trigger emergency stop?" confirmLabel="Stop dispenser" loading={busy}
        message="Queued requests are cancelled, a running dispense closes its gate as soon as the device hears this, and new requests are blocked until you reset. If food is spilling right now, also unplug the dispenser."
        onConfirm={emergencyStop} onCancel={() => setModals((m) => ({ ...m, stop: false }))} />
      <ConfirmDialog open={modals.remove} title={`Remove ${device.name}?`} confirmLabel="Remove dispenser"
        message="It is disconnected from your account and its containers and history are deleted. The dispenser goes back to showing a pairing code, so it can be connected again. Food already logged stays in your log."
        onConfirm={removeDevice} onCancel={() => setModals((m) => ({ ...m, remove: false }))} />
    </div>
  );
}
