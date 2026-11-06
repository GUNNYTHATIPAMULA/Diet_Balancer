import { forwardRef } from "react";
import { Loader2 } from "lucide-react";

const VARIANTS = {
  primary: "bg-canopy text-white hover:bg-canopy-dark shadow-sm disabled:bg-canopy/50",
  secondary: "bg-white text-ink border border-line hover:border-leaf/50 hover:bg-sprout-light disabled:text-slate-light",
  soft: "bg-sprout-light text-canopy hover:bg-sprout disabled:opacity-60",
  ghost: "text-slate hover:text-ink hover:bg-sprout-light disabled:opacity-50",
  danger: "bg-alert text-white hover:bg-alert/90 shadow-sm disabled:bg-alert/50",
  "danger-soft": "bg-alert-light text-alert hover:bg-alert/15 disabled:opacity-60",
};
const SIZES = {
  sm: "h-9 px-3 text-sm gap-1.5 rounded-xl",
  md: "h-11 px-4 text-[15px] gap-2 rounded-xl",
  lg: "h-12 px-5 text-base gap-2 rounded-2xl",
  icon: "h-9 w-9 rounded-xl justify-center",
};

export const Button = forwardRef(function Button(
  { variant = "primary", size = "md", loading = false, icon: Icon, className = "", children, disabled, type = "button", ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center font-semibold transition-colors disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : Icon ? <Icon className="h-4 w-4" aria-hidden /> : null}
      {children}
    </button>
  );
});
