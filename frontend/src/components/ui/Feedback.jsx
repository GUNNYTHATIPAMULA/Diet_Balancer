import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "./Button";

export function Skeleton({ className = "" }) {
  return <div className={`animate-pulse rounded-xl bg-line/70 ${className}`} aria-hidden />;
}

export function PageSkeleton() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-9 w-64" />
      <div className="grid gap-4 md:grid-cols-3">
        <Skeleton className="h-40 md:col-span-2" />
        <Skeleton className="h-40" />
      </div>
      <Skeleton className="h-64" />
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children, action }) {
  return (
    <div className="flex flex-col items-center px-6 py-10 text-center">
      {Icon && (
        <div className="mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-sprout-light text-canopy">
          <Icon className="h-6 w-6" aria-hidden />
        </div>
      )}
      <p className="font-display text-lg font-semibold">{title}</p>
      {children && <p className="mt-1 max-w-sm text-sm text-slate">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="panel flex flex-col items-center gap-3 px-6 py-10 text-center" role="alert">
      <div className="grid h-12 w-12 place-items-center rounded-2xl bg-alert-light text-alert">
        <AlertTriangle className="h-6 w-6" aria-hidden />
      </div>
      <p className="max-w-md text-[15px] text-ink">{message}</p>
      {onRetry && <Button variant="secondary" size="sm" icon={RefreshCw} onClick={() => onRetry()}>Try again</Button>}
    </div>
  );
}

const BADGE_TONES = {
  green: "bg-sprout-light text-canopy",
  neutral: "bg-mist text-slate border border-line",
  amber: "bg-wheat-light text-[#7A5A12]",
  red: "bg-alert-light text-alert",
  blue: "bg-river-light text-river",
  plum: "bg-beet-light text-beet",
};

export function Badge({ tone = "neutral", children, className = "" }) {
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${BADGE_TONES[tone]} ${className}`}>{children}</span>;
}
