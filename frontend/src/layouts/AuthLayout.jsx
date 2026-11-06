import { Outlet } from "react-router-dom";
import { Logo } from "../components/Logo";

export function AuthLayout() {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden overflow-hidden bg-canopy p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <Logo light />
        <div className="relative z-10 max-w-md">
          <h1 className="font-display text-[44px] font-semibold leading-[1.05] text-white">
            Know what’s on your plate, down to the gram.
          </h1>
          <p className="mt-5 text-lg leading-relaxed text-sprout">
            Track meals, see where your day stands against your target, and let your dispenser weigh each portion for you.
          </p>
        </div>
        {/* Abstract plate: the same ring language used on the dashboard */}
        <svg viewBox="0 0 400 400" className="absolute -bottom-24 -right-24 h-[460px] w-[460px] opacity-90" aria-hidden>
          <circle cx="200" cy="200" r="170" fill="none" stroke="#2C7550" strokeWidth="28" />
          <circle cx="200" cy="200" r="170" fill="none" stroke="#CFE8D3" strokeWidth="28" strokeLinecap="round" strokeDasharray="1068" strokeDashoffset="330" transform="rotate(-90 200 200)" />
          <circle cx="200" cy="200" r="128" fill="none" stroke="#7FB8D1" strokeWidth="12" strokeLinecap="round" strokeDasharray="804" strokeDashoffset="300" transform="rotate(-90 200 200)" />
          <circle cx="200" cy="200" r="106" fill="none" stroke="#E7C36B" strokeWidth="12" strokeLinecap="round" strokeDasharray="666" strokeDashoffset="160" transform="rotate(-90 200 200)" />
          <circle cx="200" cy="200" r="84" fill="none" stroke="#C99BBE" strokeWidth="12" strokeLinecap="round" strokeDasharray="528" strokeDashoffset="260" transform="rotate(-90 200 200)" />
        </svg>
        <p className="relative z-10 text-sm text-sprout/80">Estimates only, not medical advice.</p>
      </section>
      <section className="flex items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-md">
          <Logo className="mb-10 lg:hidden" />
          <Outlet />
        </div>
      </section>
    </div>
  );
}
