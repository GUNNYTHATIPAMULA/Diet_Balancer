import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { errorMessage, fieldErrors } from "../api/client";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Field";

export default function RegisterPage() {
  const { register: registerUser } = useAuth();
  const navigate = useNavigate();
  const [formError, setFormError] = useState("");
  const { register, handleSubmit, watch, setError, formState: { errors, isSubmitting } } = useForm();

  const onSubmit = async (values) => {
    setFormError("");
    try {
      await registerUser(values);
      navigate("/setup", { replace: true });
    } catch (e) {
      const fields = fieldErrors(e);
      Object.entries(fields).forEach(([field, message]) => field && setError(field, { message }));
      setFormError(errorMessage(e));
    }
  };

  return (
    <div>
      <h2 className="text-3xl font-semibold">Create your account</h2>
      <p className="mt-2 text-slate">It takes a minute. Next, we’ll estimate your daily targets.</p>
      <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-5" noValidate>
        {formError && <p role="alert" className="rounded-xl bg-alert-light px-4 py-3 text-sm text-alert">{formError}</p>}
        <Input label="Full name" autoComplete="name" error={errors.full_name?.message}
          {...register("full_name", { required: "Enter your full name.", minLength: { value: 2, message: "Enter your full name." } })} />
        <Input label="Email" type="email" autoComplete="email" error={errors.email?.message}
          {...register("email", { required: "Enter your email.", pattern: { value: /\S+@\S+\.\S+/, message: "Enter a valid email address." } })} />
        <Input label="Password" type="password" autoComplete="new-password" error={errors.password?.message}
          hint="At least 8 characters, including a letter and a number."
          {...register("password", {
            required: "Choose a password.",
            minLength: { value: 8, message: "Use at least 8 characters." },
            validate: (v) => (/[A-Za-z]/.test(v) && /\d/.test(v)) || "Include at least one letter and one number.",
          })} />
        <Input label="Confirm password" type="password" autoComplete="new-password" error={errors.confirm_password?.message}
          {...register("confirm_password", { required: "Re-enter your password.", validate: (v) => v === watch("password") || "Passwords do not match." })} />
        <Button type="submit" size="lg" className="w-full" loading={isSubmitting}>Create account</Button>
      </form>
      <p className="mt-6 text-center text-sm text-slate">
        Already have an account? <Link to="/login" className="font-semibold text-canopy hover:underline">Log in</Link>
      </p>
    </div>
  );
}
