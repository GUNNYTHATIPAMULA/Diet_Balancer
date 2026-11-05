import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="grid min-h-[60vh] place-items-center text-center">
      <div>
        <p className="num font-display text-6xl font-semibold text-sprout">404</p>
        <h1 className="mt-2 text-2xl font-semibold">This page doesn’t exist</h1>
        <p className="mt-2 text-slate">The link may be broken or the page was moved.</p>
        <Link to="/" className="mt-6 inline-flex h-11 items-center rounded-xl bg-canopy px-5 font-semibold text-white hover:bg-canopy-dark">Back to overview</Link>
      </div>
    </div>
  );
}
