import { Box, Container, Paper, Typography } from "@mui/material";
import type { ReactNode } from "react";

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center", bgcolor: "background.default", py: 4 }}>
      <Container maxWidth="xs">
        <Paper elevation={2} sx={{ p: { xs: 3, sm: 4 } }}>
          <Typography component="h1" variant="h5" fontWeight={600} gutterBottom>
            {title}
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            {subtitle}
          </Typography>
          {children}
        </Paper>
      </Container>
    </Box>
  );
}
