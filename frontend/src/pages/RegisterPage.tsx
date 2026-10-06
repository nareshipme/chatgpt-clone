import { Alert, Button, Link, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { useState, type FormEvent } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useTenants } from "../hooks/useTenants";
import { AuthLayout } from "./AuthLayout";

type FieldErrors = Partial<Record<"email" | "password" | "display_name", string>>;

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const tenants = useTenants();
  const [tenantId, setTenantId] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setFieldErrors({});
    setBusy(true);
    try {
      await register(email, password, displayName, tenantId || tenants.data?.[0]?.id);
      navigate("/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.code === "email_taken") {
        setFieldErrors({ email: err.message });
      } else if (err instanceof ApiError && err.details) {
        // Map the server's per-field validation messages onto the matching inputs.
        const mapped: FieldErrors = {};
        for (const d of err.details) mapped[d.field as keyof FieldErrors] = d.message;
        setFieldErrors(mapped);
      } else {
        setError(err instanceof ApiError ? err.message : "Could not reach the server. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Create your account" subtitle="It takes a few seconds.">
      <form onSubmit={onSubmit} noValidate>
        <Stack spacing={2}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            label="Display name"
            autoComplete="name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            error={!!fieldErrors.display_name}
            helperText={fieldErrors.display_name}
            required
            autoFocus
          />
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={!!fieldErrors.email}
            helperText={fieldErrors.email}
            required
          />
          <TextField
            label="Password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={!!fieldErrors.password}
            helperText={fieldErrors.password ?? "At least 10 characters"}
            required
          />
          {tenants.data && tenants.data.length > 0 && (
            <TextField
              select
              label="Demo company"
              value={tenantId || tenants.data[0].id}
              onChange={(e) => setTenantId(e.target.value)}
              helperText="Each company has its own fictional supply-chain data. You only ever see your own."
            >
              {tenants.data.map((t) => (
                <MenuItem key={t.id} value={t.id}>
                  {t.name} ({t.industry})
                </MenuItem>
              ))}
            </TextField>
          )}
          <Button type="submit" variant="contained" size="large" disabled={busy || !email || !password || !displayName}>
            {busy ? "Creating account..." : "Create account"}
          </Button>
          <Typography variant="body2" textAlign="center">
            Already registered?{" "}
            <Link component={RouterLink} to="/login">
              Sign in
            </Link>
          </Typography>
        </Stack>
      </form>
    </AuthLayout>
  );
}
