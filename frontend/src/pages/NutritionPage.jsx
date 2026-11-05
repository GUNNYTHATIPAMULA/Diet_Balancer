import { useState } from "react";
import { Link } from "react-router-dom";
import { profileApi } from "../api/profile";
import { errorMessage } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { useToast } from "../context/ToastContext";
import { ACTIVITY_LEVELS, GOALS } from "../utils/constants";
import { PageHeader } from "../components/PageHeader";
import { TargetsBreakdown } from "../components/TargetsBreakdown";
import { Disclaimer } from "../components/Disclaimer";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Field";
import { ErrorState, PageSkeleton } from "../components/ui/Feedback";

export default function NutritionPage() {
  const toast = useToast();
  const { data, error, loading, reload, setData } = useAsync(() => profileApi.get(), []);
  const [weight, setWeight] = useState("");
  const [weightError, setWeightError] = useState("");
  const [saving, setSaving] = useState(false);

  if (loading && !data) return <PageSkeleton />;
  if (error && !data) return <ErrorState message={errorMessage(error)} onRetry={reload} />;

  const saveWeight = async (e) => {
    e.preventDefault();
    const w = Number(weight);
    if (!w || w < 30 || w > 300) return setWeightError("Enter a weight between 30 and 300 kg.");
    setSaving(true);
    try {
      const before = data.targets.calorie_target;
      const updated = await profileApi.updateWeight(w);
      setData(updated);
      setWeight("");
      setWeightError("");
      const diff = updated.targets.calorie_target - before;
      toast.success(`Weight saved. Your target is now ${updated.targets.calorie_target} kcal${diff ? ` (${diff > 0 ? "+" : ""}${diff})` : ""}.`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const activity = ACTIVITY_LEVELS.find((a) => a.value === data.activity_level);
  const goal = GOALS.find((g) => g.value === data.goal_type);

  return (
    <div>
      <PageHeader title="My Nutrition" subtitle="Your estimated daily needs and how they were worked out." />
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <section className="panel p-6"><TargetsBreakdown targets={data.targets} /></section>
        <div className="space-y-6">
          <section className="panel p-6">
            <h2 className="text-lg font-semibold">Update your weight</h2>
            <p className="mt-1 text-sm text-slate">Current: <span className="num font-semibold text-ink">{data.weight_kg} kg</span>. Targets recalculate as soon as you save.</p>
            <form onSubmit={saveWeight} className="mt-4 flex items-start gap-2" noValidate>
              <Input className="flex-1" label="New weight" type="number" step="0.1" suffix="kg" value={weight} onChange={(e) => setWeight(e.target.value)} error={weightError} />
              <Button type="submit" className="mt-[26px]" loading={saving}>Save</Button>
            </form>
          </section>
          <section className="panel p-6">
            <h2 className="text-lg font-semibold">Based on</h2>
            <dl className="mt-3 space-y-2.5 text-[15px]">
              {[["Age", `${data.age} years`], ["Height", `${data.height_cm} cm`], ["Equation", data.sex === "male" ? "Male (+5)" : "Female (−161)"],
                ["Activity", `${activity?.label} (×${activity?.factor})`], ["Goal", `${goal?.label}${data.goal_type !== "maintain" ? `, ${data.goal_pace}` : ""}`],
                ...(data.target_weight_kg ? [["Target weight", `${data.target_weight_kg} kg`]] : [])].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4"><dt className="text-slate">{k}</dt><dd className="text-right font-semibold">{v}</dd></div>
              ))}
            </dl>
            <Link to="/profile" className="mt-4 inline-block text-sm font-semibold text-canopy hover:underline">Edit profile details</Link>
          </section>
        </div>
      </div>
      <Disclaimer className="mt-6" text={data.targets.disclaimer} />
    </div>
  );
}
