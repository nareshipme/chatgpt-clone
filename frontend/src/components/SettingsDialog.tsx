import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, FormControl, FormControlLabel, FormLabel, Radio, RadioGroup, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { useChoosePersona, usePersonas } from "../hooks/usePersonas";

interface Props {
  open: boolean;
  onClose: () => void;
}

export function SettingsDialog({ open, onClose }: Props) {
  const personas = usePersonas();
  const choose = useChoosePersona();
  const current = personas.data?.find((p) => p.selected)?.id ?? "";
  const [value, setValue] = useState(current);

  useEffect(() => {
    if (open) setValue(current);
  }, [open, current]);

  async function save() {
    await choose.mutateAsync(value);
    onClose();
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm" aria-labelledby="settings-title">
      <DialogTitle id="settings-title">Settings</DialogTitle>
      <DialogContent>
        {personas.isError && <Alert severity="error">Could not load personas.</Alert>}
        {personas.data && (
          <FormControl>
            <FormLabel id="persona-label">Who is the assistant helping?</FormLabel>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              This changes the suggested questions and how the assistant frames its answers. It never changes what data you can see.
            </Typography>
            <RadioGroup aria-labelledby="persona-label" value={value} onChange={(e) => setValue(e.target.value)}>
              {personas.data.map((p) => (
                <FormControlLabel
                  key={p.id}
                  value={p.id}
                  control={<Radio />}
                  label={
                    <>
                      <Typography>{p.name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {p.description}
                      </Typography>
                    </>
                  }
                  sx={{ alignItems: "flex-start", mb: 1 }}
                />
              ))}
            </RadioGroup>
          </FormControl>
        )}
        {choose.isError && (
          <Alert severity="error" sx={{ mt: 1 }}>
            {choose.error instanceof ApiError ? choose.error.message : "Could not save. Please try again."}
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={() => void save()} disabled={!personas.data || value === "" || value === current || choose.isPending}>
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}
