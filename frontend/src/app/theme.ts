import { createTheme } from "@mui/material/styles";

// One place for design tokens. Dark mode (a later slice) adds a second palette here.
export const theme = createTheme({
  palette: { mode: "light", primary: { main: "#3a5876" } },
  shape: { borderRadius: 10 },
  typography: { fontFamily: '"Inter", system-ui, -apple-system, "Segoe UI", sans-serif' },
});
