import { Box, CircularProgress } from "@mui/material";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

function Loading() {
  return (
    <Box sx={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
      <CircularProgress aria-label="Loading" />
    </Box>
  );
}

/** Protected routes: wait for the silent session restore, then redirect anonymous users to /login. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status, signedOut } = useAuth();
  const location = useLocation();
  if (status === "loading") return <Loading />;
  if (status === "anonymous") {
    // Remember where the user was going so login can return them there, but not after a deliberate sign-out:
    // the next person to sign in on this browser must not be sent to the previous user's page.
    return <Navigate to="/login" replace state={signedOut ? undefined : { from: location.pathname }} />;
  }
  return <>{children}</>;
}

/** Login/register pages: signed-in users are sent to the app instead. */
export function PublicOnly({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  if (status === "loading") return <Loading />;
  if (status === "authenticated") return <Navigate to="/" replace />;
  return <>{children}</>;
}
