import { Box } from "@mui/material";
import { COLORS } from "./theme";

/** Our own mark: a small tile mosaic. Decorative, so it is hidden from screen readers. */
export function BrandMark({ size = 22 }: { size?: number }) {
  return (
    <Box component="svg" viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" sx={{ flexShrink: 0 }}>
      <rect x="2" y="2" width="9" height="9" rx="2" fill={COLORS.cyan} />
      <rect x="13" y="2" width="9" height="9" rx="2" fill="#fff" fillOpacity="0.92" />
      <rect x="2" y="13" width="9" height="9" rx="2" fill="#fff" fillOpacity="0.92" />
      <rect x="13" y="13" width="9" height="9" rx="2" fill={COLORS.burgundy} stroke="#fff" strokeOpacity="0.35" />
    </Box>
  );
}
