import { Chip, Stack } from "@mui/material";

interface Props {
  starters: string[];
  onPick: (text: string) => void;
  disabled?: boolean;
}

/** Suggested first questions for the active persona. Clicking one asks it right away. */
export function StarterChips({ starters, onPick, disabled }: Props) {
  if (starters.length === 0) return null;
  return (
    <Stack direction="row" flexWrap="wrap" gap={1} justifyContent="center" role="group" aria-label="Suggested questions">
      {starters.map((s) => (
        <Chip key={s} label={s} variant="outlined" clickable disabled={disabled} onClick={() => onPick(s)} sx={{ height: "auto", py: 0.75, "& .MuiChip-label": { whiteSpace: "normal" } }} />
      ))}
    </Stack>
  );
}
