import CheckIcon from "@mui/icons-material/Check";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import { Box, IconButton, Paper, Tooltip, Typography } from "@mui/material";
import { lazy, Suspense, useState } from "react";
import { copyText } from "../lib/clipboard";

// Markdown (react-markdown, remark, highlight.js) is the heaviest part of the app and the sign-in pages
// never need it, so it is loaded on demand.
const Markdown = lazy(() => import("./Markdown").then((m) => ({ default: m.Markdown })));

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
  const [copied, setCopied] = useState(false);
  const canCopy = !isUser && !!text && !live;

  async function copy() {
    if (await copyText(text)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }

  return (
    <Box sx={{ display: "flex", justifyContent: isUser ? "flex-end" : "flex-start", mb: 2 }}>
      <Paper
        elevation={0}
        data-role={role}
        sx={{
          position: "relative",
          px: 2,
          py: 1.5,
          maxWidth: "85%",
          minWidth: 0,
          bgcolor: isUser ? "primary.main" : "action.hover",
          color: isUser ? "primary.contrastText" : "text.primary",
          borderRadius: 3,
          "&:hover .copy-message, & .copy-message:focus-visible": { opacity: 1 },
        }}
      >
        {isUser ? (
          <Typography component="div" sx={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {text}
          </Typography>
        ) : waiting ? (
          <Typography component="div">
            <span aria-label="The assistant is typing">…</span>
          </Typography>
        ) : (
          <Typography component="div">
            <Suspense fallback={<span style={{ whiteSpace: "pre-wrap" }}>{text}</span>}>
              <Markdown>{live ? `${text} ▍` : text}</Markdown>
            </Suspense>
          </Typography>
        )}
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
        {canCopy && (
          <Tooltip title={copied ? "Copied" : "Copy message"}>
            <IconButton
              className="copy-message"
              size="small"
              onClick={() => void copy()}
              aria-label="Copy message"
              sx={{ position: "absolute", right: 4, bottom: 4, opacity: 0, transition: "opacity .15s" }}
            >
              {copied ? <CheckIcon fontSize="inherit" /> : <ContentCopyIcon fontSize="inherit" />}
            </IconButton>
          </Tooltip>
        )}
      </Paper>
    </Box>
  );
}
