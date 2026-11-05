import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Home, Target, UtensilsCrossed, Cpu, Lightbulb, BarChart3, UserRound, Settings, LogOut, Menu, X, MoreHorizontal } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/Logo";

export const NAV = [
  { to: "/", label: "Overview", icon: Home, end: true },
  { to: "/nutrition", label: "My Nutrition", icon: Target },
  { to: "/food", label: "Food Tracker", icon: UtensilsCrossed },
  { to: "/dispenser", label: "Smart Dispenser", icon: Cpu },
  { to: "/recommendations", label: "Recommendations", icon: Lightbulb },
  { to: "/reports", label: "Reports", icon: BarChart3 },
  { to: "/profile", label: "My Profile", icon: UserRound },
  { to: "/settings", label: "Settings", icon: Settings },
];
const MOBILE_TABS = ["/", "/food", "/dispenser", "/reports"];

function NavItems({ onNavigate }) {
  return NAV.map(({ to, label, icon: Icon, end }) => (
    <NavLink key={to} to={to} end={end} onClick={onNavigate}
      className={({ isActive }) =>
        `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] font-medium transition-colors ${
          isActive ? "bg-sprout-light text-canopy" : "text-slate hover:bg-mist hover:text-ink"}`}>
      {({ isActive }) => (
        <>
          <Icon className={`h-[18px] w-[18px] ${isActive ? "text-canopy" : "text-slate-light group-hover:text-ink"}`} aria-hidden />
          {label}
        </>
      )}
    </NavLink>
  ));
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [drawer, setDrawer] = useState(false);

  useEffect(() => setDrawer(false), [location.pathname]);

  const doLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const LogoutButton = (
    <button onClick={doLogout} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] font-medium text-slate hover:bg-alert-light hover:text-alert">
      <LogOut className="h-[18px] w-[18px]" aria-hidden /> Logout
    </button>
  );

  return (
    <div className="min-h-screen lg:flex">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-xl focus:bg-white focus:px-4 focus:py-2">Skip to content</a>

      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-line bg-white px-4 py-6 lg:flex">
        <Logo className="px-2" />
        <nav className="mt-8 flex-1 space-y-1" aria-label="Main">
          <NavItems />
        </nav>
        <div className="border-t border-line pt-4">
          <div className="mb-2 px-3">
            <p className="truncate text-sm font-semibold text-ink">{user?.full_name}</p>
            <p className="truncate text-xs text-slate">{user?.email}</p>
          </div>
          {LogoutButton}
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-mist/90 px-4 py-3 backdrop-blur lg:hidden" style={{ paddingTop: "max(0.75rem, env(safe-area-inset-top))" }}>
        <Logo />
        <button onClick={() => setDrawer(true)} className="rounded-xl p-2 text-ink hover:bg-white" aria-label="Open menu">
          <Menu className="h-6 w-6" />
        </button>
      </header>

      {/* Mobile drawer */}
      {drawer && (
        <div className="fixed inset-0 z-40 bg-ink/40 lg:hidden" onClick={() => setDrawer(false)}>
          <div className="absolute right-0 top-0 flex h-full w-72 flex-col bg-white p-4 shadow-lift" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Menu">
            <div className="mb-4 flex items-center justify-between">
              <p className="font-display text-lg font-semibold">Menu</p>
              <button onClick={() => setDrawer(false)} className="rounded-xl p-2 hover:bg-mist" aria-label="Close menu"><X className="h-5 w-5" /></button>
            </div>
            <nav className="flex-1 space-y-1" aria-label="Main"><NavItems onNavigate={() => setDrawer(false)} /></nav>
            <div className="border-t border-line pt-3">{LogoutButton}</div>
          </div>
        </div>
      )}

      <main id="main" className="min-w-0 flex-1 px-4 pb-28 pt-6 sm:px-6 lg:px-10 lg:pb-12 lg:pt-10">
        <div className="mx-auto max-w-6xl">
          <Outlet />
        </div>
      </main>

      {/* Mobile tab bar */}
      <nav aria-label="Quick" className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-line bg-white/95 backdrop-blur lg:hidden" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
        {NAV.filter((n) => MOBILE_TABS.includes(n.to)).map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => `flex flex-col items-center gap-0.5 py-2.5 text-[11px] font-semibold ${isActive ? "text-canopy" : "text-slate"}`}>
            <Icon className="h-5 w-5" aria-hidden />
            {label.replace("Smart ", "").replace("Food ", "")}
          </NavLink>
        ))}
        <button onClick={() => setDrawer(true)} className="flex flex-col items-center gap-0.5 py-2.5 text-[11px] font-semibold text-slate">
          <MoreHorizontal className="h-5 w-5" aria-hidden /> More
        </button>
      </nav>
    </div>
  );
}
