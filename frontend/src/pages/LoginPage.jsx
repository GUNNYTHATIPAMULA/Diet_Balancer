import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { errorMessage } from "../api/client";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Field";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [formError, setFormError] = useState("");
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm();

  const onSubmit = async ({ email, password }) => {
    setFormError("");
    try {
      const user = await login(email, password);
      navigate(user.has_profile ? location.state?.from || "/" : "/setup", { replace: true });
    } catch (e) {
      setFormError(errorMessage(e));
    }
  };

  return (
    <div>
      <h2 className="text-3xl font-semibold">Welcome back</h2>
      <p className="mt-2 text-slate">Log in to see today’s nutrition and your dispenser.</p>
      <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-5" noValidate>
        {formError && <p role="alert" className="rounded-xl bg-alert-light px-4 py-3 text-sm text-alert">{formError}</p>}
        <Input label="Email" type="email" autoComplete="email" error={errors.email?.message}
          {...register("email", { required: "Enter your email.", pattern: { value: /\S+@\S+\.\S+/, message: "Enter a valid email address." } })} />
        <Input label="Password" type="password" autoComplete="current-password" error={errors.password?.message}
          {...register("password", { required: "Enter your password." })} />
        <Button type="submit" size="lg" className="w-full" loading={isSubmitting}>Log in</Button>
      </form>
      <p className="mt-6 text-center text-sm text-slate">
        New to Diet Balancer? <Link to="/register" className="font-semibold text-canopy hover:underline">Create an account</Link>
      </p>
    </div>
  );
}
