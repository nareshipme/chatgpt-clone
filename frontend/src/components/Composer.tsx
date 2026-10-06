import SendIcon from "@mui/icons-material/Send";
import StopIcon from "@mui/icons-material/Stop";
import { Box, IconButton, TextField, Tooltip } from "@mui/material";
import { useState, type KeyboardEvent } from "react";

const MAX_CHARS = 8000; // must match the server's limit

interface Props {
  streaming: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}

export function Composer({ streaming, onSend, onStop }: Props) {
  const [text, setText] = useState("");
  const canSend = text.trim().length > 0 && !streaming;

  function submit() {
    if (!canSend) return;
    onSend(text.trim());
    setText("");
  }

  function onKeyDown(e: KeyboardEvent) {
    // Enter sends; Shift+Enter inserts a newline. Ignore Enter while an IME is composing a character.
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <Box sx={{ display: "flex", gap: 1, alignItems: "flex-end", p: 2, borderTop: 1, borderColor: "divider" }}>
      <TextField
        fullWidth
        multiline
        minRows={1}
        maxRows={8}
        placeholder="Type a message"
        value={text}
        onChange={(e) => setText(e.target.value.slice(0, MAX_CHARS))}
        onKeyDown={onKeyDown}
        slotProps={{ htmlInput: { "aria-label": "Message" } }}
        helperText={text.length > MAX_CHARS - 500 ? `${text.length} / ${MAX_CHARS}` : undefined}
      />
      {streaming ? (
        <Tooltip title="Stop generating">
          <IconButton color="error" onClick={onStop} aria-label="Stop generating" size="large">
            <StopIcon />
          </IconButton>
        </Tooltip>
      ) : (
        <Tooltip title="Send">
          <span>
            <IconButton color="primary" onClick={submit} disabled={!canSend} aria-label="Send message" size="large">
              <SendIcon />
            </IconButton>
          </span>
        </Tooltip>
      )}
    </Box>
  );
}
