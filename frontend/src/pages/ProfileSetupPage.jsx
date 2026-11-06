import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check } from "lucide-react";
import { profileApi } from "../api/profile";
import { errorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { Logo } from "../components/Logo";
import { Button } from "../components/ui/Button";
import { Disclaimer } from "../components/Disclaimer";
import { TargetsBreakdown } from "../components/TargetsBreakdown";
import { BodySection, EMPTY_PROFILE, GoalSection, PreferenceSection, formToPayload, validateBody, validateGoal } from "../components/ProfileSections";

const STEPS = [
  { title: "Your body", text: "Used only to estimate how much energy you burn." },
  { title: "Activity and goal", text: "Sets your maintenance level and a sensible adjustment." },
  { title: "Food preferences", text: "Keeps suggestions within what you eat." },
  { title: "Your targets", text: "Here’s what we estimated. You can change any of it later." },
];

export default function ProfileSetupPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const { user, setUser } = useAuth();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(EMPTY_PROFILE);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(null);

  const set = (key, value) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => ({ ...e, [key]: undefined }));
  };

  const next = async () => {
    const validation = step === 0 ? validateBody(form) : step === 1 ? validateGoal(form) : {};
    if (Object.keys(validation).length) return setErrors(validation);
    if (step === 2) {
      setSaving(true);
      try {
        const result = await profileApi.save(formToPayload(form));
        setSaved(result);
        setUser({ ...user, has_profile: true });
        setStep(3);
      } catch (e) {
        toast.error(errorMessage(e));
      } finally {
        setSaving(false);
      }
      return;
    }
    setStep((s) => s + 1);
  };

  return (
    <div className="min-h-screen bg-mist px-4 py-8 sm:py-12">
      <div className="mx-auto max-w-2xl">
        <Logo />
        <ol className="mt-8 flex gap-2" aria-label="Setup progress">
          {STEPS.map((s, i) => (
            <li key={s.title} className="flex-1">
              <span className={`block h-1.5 rounded-full ${i <= step ? "bg-leaf" : "bg-line"}`} />
              <span className={`mt-2 hidden text-xs font-semibold sm:block ${i === step ? "text-canopy" : "text-slate-light"}`}>
                {i < step ? <Check className="mr-1 inline h-3 w-3" aria-hidden /> : null}{s.title}
              </span>
            </li>
          ))}
        </ol>

        <div className="panel mt-6 p-6 sm:p-8">
          <p className="text-sm font-semibold text-leaf">Step {step + 1} of {STEPS.length}</p>
          <h1 className="mt-1 text-[28px] font-semibold">{STEPS[step].title}</h1>
          <p className="mb-6 mt-1 text-slate">{STEPS[step].text}</p>

          {step === 0 && <BodySection form={form} set={set} errors={errors} />}
          {step === 1 && <GoalSection form={form} set={set} errors={errors} />}
          {step === 2 && <PreferenceSection form={form} set={set} />}
          {step === 3 && saved && <TargetsBreakdown targets={saved.targets} />}

          <div className="mt-8 flex items-center justify-between gap-3">
            {step > 0 && step < 3 ? <Button variant="ghost" onClick={() => setStep((s) => s - 1)}>Back</Button> : <span />}
            {step < 3 ? (
              <Button onClick={next} loading={saving}>{step === 2 ? "Calculate my targets" : "Continue"}</Button>
            ) : (
              <Button onClick={() => navigate("/", { replace: true })}>Go to my dashboard</Button>
            )}
          </div>
        </div>
        <Disclaimer className="mt-5" />
      </div>
    </div>
  );
}
