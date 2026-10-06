import { Box, Button, Stack, Typography } from "@mui/material";
import type { ActionsPart } from "../../api/types";

interface Props {
  part: ActionsPart;
  /** True only for the newest reply with nothing after it: older menus are history and cannot be clicked. */
  active: boolean;
  /** The user message that followed this menu, if any. When it matches an option, that option is shown as chosen. */
  answeredWith?: string;
  onChoose: (value: string) => void;
}

export function ActionsView({ part, active, answeredWith, onChoose }: Props) {
  return (
    <Box sx={{ my: 1.5 }}>
      {part.prompt && (
        <Typography variant="body2" sx={{ mb: 1, fontWeight: 600 }}>
          {part.prompt}
        </Typography>
      )}
      <Stack direction="row" flexWrap="wrap" gap={1} role="group" aria-label={part.prompt ?? "Choose an option"}>
        {part.options.map((o) => {
          const chosen = answeredWith !== undefined && answeredWith === o.value;
          return (
            <Button
              key={o.id}
              size="small"
              variant={chosen ? "contained" : "outlined"}
              disabled={!active && !chosen}
              aria-pressed={chosen || undefined}
              onClick={() => active && onChoose(o.value)}
              sx={{ textTransform: "none", borderRadius: 5 }}
            >
              {o.label}
            </Button>
          );
        })}
      </Stack>
    </Box>
  );
}
