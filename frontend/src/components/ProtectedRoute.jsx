import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export function FullScreenLoader() {
  return (
    <div className="grid min-h-screen place-items-center bg-mist" aria-busy="true">
      <Loader2 className="h-7 w-7 animate-spin text-leaf" aria-label="Loading" />
    </div>
  );
}

/** Requires login. With requireProfile, users without a profile go to the setup wizard first. */
export function ProtectedRoute({ requireProfile = true }) {
  const { status, user } = useAuth();
  const location = useLocation();
  if (status === "loading") return <FullScreenLoader />;
  if (status !== "authenticated") return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (requireProfile && !user.has_profile) return <Navigate to="/setup" replace />;
  return <Outlet />;
}

export function GuestRoute() {
  const { status } = useAuth();
  if (status === "loading") return <FullScreenLoader />;
  if (status === "authenticated") return <Navigate to="/" replace />;
  return <Outlet />;
}
