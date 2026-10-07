import { createTheme, type ThemeOptions } from "@mui/material/styles";

/**
 * Design tokens. The look (black navigation, cyan and burgundy accents, navy text links, a humanist sans, calm
 * grey surfaces) follows the public blueyonder.com site. Only the visual language is borrowed: the product keeps
 * its own name and mark.
 */
export const COLORS = {
  black: "#000000",
  navy: "#000e4e",
  cyan: "#00b7f1",
  cyanDark: "#007ca3",
  burgundy: "#6a0136",
  burgundyDark: "#4d0126",
  grey50: "#f6f7f9",
  grey100: "#eceef2",
  grey300: "#cfd3dc",
  grey600: "#5b6070",
} as const;

/** Colours for chart series, in order. Distinct in hue and in lightness so they survive colour-blindness. */
export const CHART_COLORS = [COLORS.cyan, COLORS.burgundy, COLORS.navy, "#7a8fb8", "#c0568a", "#5ec2a3"];

const FONT = '"Source Sans 3 Variable", "Calibre", system-ui, -apple-system, "Segoe UI", Arial, sans-serif';

const shared: ThemeOptions = {
  shape: { borderRadius: 8 },
  typography: {
    fontFamily: FONT,
    fontSize: 15,
    h4: { fontWeight: 500, letterSpacing: "-0.01em" },
    h5: { fontWeight: 500, letterSpacing: "-0.01em" },
    h6: { fontWeight: 600 },
    button: { textTransform: "none", fontWeight: 600, letterSpacing: 0 },
  },
  components: {
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: { root: { borderRadius: 6 } },
    },
    MuiChip: { styleOverrides: { root: { fontWeight: 500 } } },
    MuiLink: { defaultProps: { underline: "hover" }, styleOverrides: { root: { color: COLORS.navy, fontWeight: 600 } } },
    MuiPaper: { styleOverrides: { outlined: { borderColor: COLORS.grey300 } } },
  },
};

export const theme = createTheme({
  ...shared,
  palette: {
    mode: "light",
    primary: { main: COLORS.burgundy, dark: COLORS.burgundyDark, contrastText: "#fff" },
    secondary: { main: COLORS.cyan, dark: COLORS.cyanDark, contrastText: COLORS.black },
    info: { main: COLORS.cyanDark },
    background: { default: "#fff", paper: "#fff" },
    text: { primary: "#111318", secondary: COLORS.grey600 },
    divider: COLORS.grey100,
  },
  components: {
    ...shared.components,
    MuiOutlinedInput: { styleOverrides: { root: { backgroundColor: "#fff" } } },
  },
});

/** The black navigation column: dark surface, cyan actions. Wrap only the sidebar in this. */
export const sidebarTheme = createTheme({
  ...shared,
  palette: {
    mode: "dark",
    primary: { main: COLORS.cyan, dark: COLORS.cyanDark, contrastText: COLORS.black },
    background: { default: COLORS.black, paper: COLORS.black },
    text: { primary: "#fff", secondary: "#aeb4c4" },
    divider: "rgba(255,255,255,0.14)",
  },
  components: {
    ...shared.components,
    MuiOutlinedInput: {
      styleOverrides: {
        root: { backgroundColor: "rgba(255,255,255,0.08)", "& fieldset": { borderColor: "rgba(255,255,255,0.22)" } },
      },
    },
  },
});
