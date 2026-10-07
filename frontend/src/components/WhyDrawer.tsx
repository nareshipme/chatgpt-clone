import { Box, Chip, Divider, Drawer, IconButton, Stack, Typography } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import type { Provenance } from "../api/types";
import { toolLabel } from "../lib/tools";

interface Props {
  open: boolean;
  onClose: () => void;
  provenance: Provenance[];
}

const CONFIDENCE_COLOR = { high: "success", medium: "warning", low: "error" } as const;

/** "Why this answer": what the assistant looked at, with what inputs, how current it was and what it assumed. */
export function WhyDrawer({ open, onClose, provenance }: Props) {
  return (
    <Drawer anchor="right" open={open} onClose={onClose} slotProps={{ paper: { sx: { width: { xs: "100%", sm: 420 }, p: 2 } } }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between">
        <Typography variant="h6" component="h2">
          Why this answer
        </Typography>
        <IconButton aria-label="Close" onClick={onClose}>
          <CloseIcon />
        </IconButton>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Every number in this answer came from the checks below, not from the model&apos;s memory.
      </Typography>
      {provenance.map((p, i) => (
        <Box key={i} sx={{ mb: 2 }}>
          {i > 0 && <Divider sx={{ mb: 2 }} />}
          <Stack direction="row" alignItems="center" justifyContent="space-between" gap={1}>
            <Typography variant="subtitle1">{toolLabel(p.tool)}</Typography>
            <Chip size="small" label={`${p.confidence} confidence`} color={CONFIDENCE_COLOR[p.confidence]} variant="outlined" />
          </Stack>
          <Typography variant="body2">Source: {p.source}</Typography>
          <Typography variant="body2">Data as of: {new Date(p.as_of).toLocaleString()}</Typography>
          {Object.keys(p.inputs).length > 0 && (
            <Typography variant="body2" sx={{ wordBreak: "break-word" }}>
              Inputs: {Object.entries(p.inputs).filter(([, v]) => v !== null).map(([k, v]) => `${k} = ${String(v)}`).join(", ")}
            </Typography>
          )}
          <Typography variant="body2" sx={{ mt: 1, fontWeight: 600 }}>
            Assumptions
          </Typography>
          <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
            {p.assumptions.map((a) => (
              <li key={a}>
                <Typography variant="body2">{a}</Typography>
              </li>
            ))}
          </Box>
        </Box>
      ))}
    </Drawer>
  );
}
