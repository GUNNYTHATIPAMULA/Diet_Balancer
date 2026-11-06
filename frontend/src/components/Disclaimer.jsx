import { Info } from "lucide-react";
import { DISCLAIMER } from "../utils/constants";

export function Disclaimer({ text = DISCLAIMER, className = "" }) {
  return (
    <p className={`flex items-start gap-2 text-sm text-slate ${className}`}>
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-slate-light" aria-hidden />
      <span>{text}</span>
    </p>
  );
}
