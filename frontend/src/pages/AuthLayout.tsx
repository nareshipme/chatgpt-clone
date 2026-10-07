import { Alert, Box, Container, Paper, Typography } from "@mui/material";
import type { ReactNode } from "react";
import { BrandMark } from "../app/BrandMark";
import { BRAND, DEMO_NOTICE } from "../app/brand";
import { COLORS } from "../app/theme";

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <Box sx={{ minHeight: "100vh", display: "flex", flexDirection: "column", bgcolor: COLORS.grey50 }}>
      <Box component="header" sx={{ bgcolor: COLORS.black, color: "#fff", px: { xs: 2, sm: 4 }, py: 2, display: "flex", alignItems: "center", gap: 1.25 }}>
        <BrandMark size={28} />
        <Typography component="span" sx={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em" }}>
          {BRAND}
        </Typography>
      </Box>
      <Box sx={{ flex: 1, display: "grid", placeItems: "center", py: 4 }}>
        <Container maxWidth="xs">
          <Paper variant="outlined" sx={{ p: { xs: 3, sm: 4 }, borderRadius: 2 }}>
            <Typography component="h1" variant="h4" gutterBottom>
              {title}
            </Typography>
            <Typography color="text.secondary" sx={{ mb: 3 }}>
              {subtitle}
            </Typography>
            {children}
            <Alert severity="info" variant="outlined" sx={{ mt: 3 }}>
              {DEMO_NOTICE}
            </Alert>
          </Paper>
        </Container>
      </Box>
    </Box>
  );
}
