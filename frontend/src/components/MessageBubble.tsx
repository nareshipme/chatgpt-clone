import { Box, Paper, Typography } from "@mui/material";

interface Props {
  role: "user" | "assistant" | "system";
  text: string;
  /** Saved status of an assistant message, shown as a quiet note. */
  status?: "streaming" | "complete" | "interrupted" | "error";
  /** True while this bubble is still receiving tokens. */
  live?: boolean;
}

export function MessageBubble({ role, text, status, live }: Props) {
  const isUser = role === "user";
  const waiting = !isUser && !text && (live || status === "streaming");
  return (
    <Box sx={{ display: "flex", justifyContent: isUser ? "flex-end" : "flex-start", mb: 2 }}>
      <Paper
        elevation={0}
        data-role={role}
        sx={{
          px: 2,
          py: 1.5,
          maxWidth: "85%",
          bgcolor: isUser ? "primary.main" : "action.hover",
          color: isUser ? "primary.contrastText" : "text.primary",
          borderRadius: 3,
        }}
      >
        <Typography component="div" sx={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
          {waiting ? <span aria-label="The assistant is typing">…</span> : text}
          {live && text && <span aria-hidden="true"> ▍</span>}
        </Typography>
        {!isUser && status === "interrupted" && (
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
            Stopped
          </Typography>
        )}
        {!isUser && status === "error" && (
          <Typography variant="caption" color="error" display="block" sx={{ mt: 0.5 }}>
            This reply did not finish
          </Typography>
        )}
      </Paper>
    </Box>
  );
}
