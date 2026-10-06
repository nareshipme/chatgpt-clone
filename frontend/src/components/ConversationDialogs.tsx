import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  TextField,
} from "@mui/material";
import { useEffect, useState, type FormEvent } from "react";
import type { Conversation } from "../api/types";

interface RenameProps {
  conversation: Conversation | null;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (title: string) => void;
}

export function RenameDialog({ conversation, busy, error, onClose, onSubmit }: RenameProps) {
  const [title, setTitle] = useState("");
  useEffect(() => setTitle(conversation?.title ?? ""), [conversation]);

  function submit(e: FormEvent) {
    e.preventDefault();
    const trimmed = title.trim();
    if (trimmed) onSubmit(trimmed);
  }

  return (
    <Dialog open={!!conversation} onClose={onClose} fullWidth maxWidth="xs">
      <form onSubmit={submit}>
        <DialogTitle>Rename conversation</DialogTitle>
        <DialogContent>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          <TextField
            autoFocus
            fullWidth
            margin="dense"
            label="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            slotProps={{ htmlInput: { maxLength: 200 } }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={busy || !title.trim()}>
            Save
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

interface DeleteProps {
  conversation: Conversation | null;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: () => void;
}

export function DeleteDialog({ conversation, busy, error, onClose, onConfirm }: DeleteProps) {
  return (
    <Dialog open={!!conversation} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>Delete conversation?</DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <DialogContentText>
          &ldquo;{conversation?.title}&rdquo; will be permanently deleted. This cannot be undone.
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button color="error" variant="contained" onClick={onConfirm} disabled={busy}>
          Delete
        </Button>
      </DialogActions>
    </Dialog>
  );
}
