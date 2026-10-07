import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import { Button, Chip, Stack } from "@mui/material";
import { COLORS } from "../app/theme";

interface Props {
  starters: string[];
  onPick: (text: string) => void;
  disabled?: boolean;
  /** "chips": compact and centred (empty chat). "cards": full-width buttons with an arrow (home page). */
  variant?: "chips" | "cards";
}

/** Suggested first questions for the active persona. Clicking one asks it right away. */
export function StarterChips({ starters, onPick, disabled, variant = "chips" }: Props) {
  if (starters.length === 0) return null;
  if (variant === "cards") {
    return (
      <Stack gap={1.25} role="group" aria-label="Suggested questions" sx={{ maxWidth: 720 }}>
        {starters.map((s) => (
          <Button
            key={s}
            variant="outlined"
            disabled={disabled}
            onClick={() => onPick(s)}
            endIcon={<ArrowForwardIcon />}
            sx={{
              justifyContent: "space-between", textAlign: "left", py: 1.5, px: 2, fontWeight: 500, fontSize: 16,
              color: "text.primary", borderColor: COLORS.grey300, borderWidth: 1.5, bgcolor: "#fff",
              "&:hover": { borderColor: COLORS.cyan, bgcolor: COLORS.grey50, borderWidth: 1.5 },
              "& .MuiButton-endIcon": { color: COLORS.cyanDark },
            }}
          >
            {s}
          </Button>
        ))}
      </Stack>
    );
  }
  return (
    <Stack direction="row" flexWrap="wrap" gap={1} justifyContent="center" role="group" aria-label="Suggested questions">
      {starters.map((s) => (
        <Chip key={s} label={s} variant="outlined" clickable disabled={disabled} onClick={() => onPick(s)} sx={{ height: "auto", py: 0.75, "& .MuiChip-label": { whiteSpace: "normal" } }} />
      ))}
    </Stack>
  );
}
