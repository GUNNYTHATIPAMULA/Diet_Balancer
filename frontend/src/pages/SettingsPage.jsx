import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { authApi } from "../api/auth";
import { API_BASE_URL, errorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { PageHeader } from "../components/PageHeader";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Field";
import { ConfirmDialog } from "../components/ui/Modal";
import { Disclaimer } from "../components/Disclaimer";

export default function SettingsPage() {
  const { user, setUser, acceptToken, logout } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const nameForm = useForm({ values: { full_name: user?.full_name || "" } });
  const pwForm = useForm();
  const [confirmAll, setConfirmAll] = useState(false);

  const saveName = async ({ full_name }) => {
    try {
      setUser(await authApi.updateMe({ full_name }));
      toast.success("Name updated.");
    } catch (e) { toast.error(errorMessage(e)); }
  };
  const changePassword = async (values) => {
    try {
      acceptToken(await authApi.changePassword(values));
      pwForm.reset();
      toast.success("Password changed. Other sessions were signed out.");
    } catch (e) { toast.error(errorMessage(e)); }
  };
  const signOutEverywhere = async () => {
    try {
      await authApi.logoutAll();
    } catch (e) { toast.error(errorMessage(e)); }
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="max-w-3xl">
      <PageHeader title="Settings" subtitle="Account and security." />
      <div className="space-y-6">
        <section className="panel p-6">
          <h2 className="text-lg font-semibold">Account</h2>
          <form onSubmit={nameForm.handleSubmit(saveName)} className="mt-4 grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end" noValidate>
            <Input label="Full name" error={nameForm.formState.errors.full_name?.message}
              {...nameForm.register("full_name", { required: "Enter your name.", minLength: { value: 2, message: "Enter your name." } })} />
            <Button type="submit" variant="secondary" loading={nameForm.formState.isSubmitting}>Save name</Button>
          </form>
          <p className="mt-3 text-sm text-slate">Email: <span className="font-semibold text-ink">{user?.email}</span></p>
        </section>

        <section className="panel p-6">
          <h2 className="text-lg font-semibold">Change password</h2>
          <form onSubmit={pwForm.handleSubmit(changePassword)} className="mt-4 grid gap-4 sm:grid-cols-3" noValidate>
            <Input label="Current password" type="password" autoComplete="current-password" error={pwForm.formState.errors.current_password?.message}
              {...pwForm.register("current_password", { required: "Required." })} />
            <Input label="New password" type="password" autoComplete="new-password" error={pwForm.formState.errors.new_password?.message}
              {...pwForm.register("new_password", { required: "Required.", minLength: { value: 8, message: "At least 8 characters." },
                validate: (v) => (/[A-Za-z]/.test(v) && /\d/.test(v)) || "Include a letter and a number." })} />
            <Input label="Confirm new password" type="password" autoComplete="new-password" error={pwForm.formState.errors.confirm_password?.message}
              {...pwForm.register("confirm_password", { validate: (v) => v === pwForm.watch("new_password") || "Passwords do not match." })} />
            <div className="sm:col-span-3"><Button type="submit" loading={pwForm.formState.isSubmitting}>Change password</Button></div>
          </form>
        </section>

        <section className="panel p-6">
          <h2 className="text-lg font-semibold">Sessions</h2>
          <p className="mt-1 text-sm text-slate">Sign out on every browser and device where you’re logged in, including this one.</p>
          <Button className="mt-4" variant="danger-soft" onClick={() => setConfirmAll(true)}>Sign out everywhere</Button>
        </section>

        <section className="panel p-6">
          <h2 className="text-lg font-semibold">About</h2>
          <p className="mt-1 text-sm text-slate">Connected to <code className="rounded bg-mist px-1.5 py-0.5 text-ink">{API_BASE_URL}</code></p>
          <Disclaimer className="mt-4" />
        </section>
      </div>
      <ConfirmDialog open={confirmAll} title="Sign out everywhere?" confirmLabel="Sign out everywhere"
        message="All sessions end immediately, including this one. Dispenser tokens are not affected." onConfirm={signOutEverywhere} onCancel={() => setConfirmAll(false)} />
    </div>
  );
}
