import { useEffect, useState } from "react";
import { profileApi } from "../api/profile";
import { errorMessage } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { useToast } from "../context/ToastContext";
import { PageHeader } from "../components/PageHeader";
import { Button } from "../components/ui/Button";
import { ErrorState, PageSkeleton } from "../components/ui/Feedback";
import { TargetsBreakdown } from "../components/TargetsBreakdown";
import { BodySection, GoalSection, PreferenceSection, formToPayload, profileToForm, validateBody, validateGoal } from "../components/ProfileSections";

export default function ProfilePage() {
  const toast = useToast();
  const { data, error, loading, reload, setData } = useAsync(() => profileApi.get(), []);
  const [form, setForm] = useState(null);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (data) setForm(profileToForm(data)); }, [data]);

  if (loading && !data) return <PageSkeleton />;
  if (error && !data) return <ErrorState message={errorMessage(error)} onRetry={reload} />;
  if (!form) return <PageSkeleton />;

  const set = (k, v) => { setForm((f) => ({ ...f, [k]: v })); setErrors((e) => ({ ...e, [k]: undefined })); };
  const save = async () => {
    const v = { ...validateBody(form), ...validateGoal(form) };
    if (Object.keys(v).length) {
      setErrors(v);
      return toast.error("Check the highlighted fields.");
    }
    setSaving(true);
    try {
      const updated = await profileApi.save(formToPayload(form));
      setData(updated);
      toast.success(`Profile saved. Daily target: ${updated.targets.calorie_target} kcal.`);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader title="My Profile" subtitle="Change any detail and your targets recalculate when you save."
        actions={<Button onClick={save} loading={saving}>Save profile</Button>} />
      <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <div className="space-y-6">
          <section className="panel p-6"><h2 className="mb-5 text-lg font-semibold">Body</h2><BodySection form={form} set={set} errors={errors} /></section>
          <section className="panel p-6"><h2 className="mb-5 text-lg font-semibold">Activity and goal</h2><GoalSection form={form} set={set} errors={errors} /></section>
          <section className="panel p-6"><h2 className="mb-5 text-lg font-semibold">Food preferences</h2><PreferenceSection form={form} set={set} /></section>
          <div className="flex justify-end"><Button onClick={save} loading={saving}>Save profile</Button></div>
        </div>
        <aside className="xl:sticky xl:top-8 xl:self-start">
          <section className="panel p-6">
            <h2 className="mb-1 text-lg font-semibold">Current targets</h2>
            <p className="mb-4 text-sm text-slate">From your last saved profile.</p>
            <TargetsBreakdown targets={data.targets} />
          </section>
        </aside>
      </div>
    </div>
  );
}
