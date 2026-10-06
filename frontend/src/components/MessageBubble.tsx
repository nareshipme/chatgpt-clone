import CheckIcon from "@mui/icons-material/Check";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import { Box, IconButton, Paper, Tooltip, Typography } from "@mui/material";
import { useState } from "react";
import type { MessagePart } from "../api/types";
import { copyText } from "../lib/clipboard";
import { partsToPlainText } from "../lib/parts";
import { PartsView } from "./PartsView";

interface Props {
  role: "user" | "assistant" | "system";
  /** The message content as typed parts. For plain text you may pass `text` instead. */
  parts?: MessagePart[];
  text?: string;
  /** Saved status of an assistant message, shown as a quiet note. */
  status?: "streaming" | "complete" | "interrupted" | "error";
  /** True while this bubble is still receiving content. */
  live?: boolean;
  /** Choice buttons in this message can be clicked (only the newest reply with nothing after it). */
  actionsActive?: boolean;
  answeredWith?: string;
  onChoose?: (value: string) => void;
}

export function MessageBubble({ role, parts, text = "", status, live, actionsActive, answeredWith, onChoose }: Props) {
  const content: MessagePart[] = parts ?? (text ? [{ type: "text", text }] : []);
  const isUser = role === "user";
  const hasContent = content.some((p) => p.type !== "text" || p.text);
  const waiting = !isUser && !hasContent && (live || status === "streaming");
  const [copied, setCopied] = useState(false);
  const canCopy = !isUser && hasContent && !live;

  async function copy() {
    if (await copyText(partsToPlainText(content))) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }

  const userText = content.map((p) => (p.type === "text" ? p.text : "")).join("");

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
            {userText}
          </Typography>
        ) : waiting ? (
          <Typography component="div">
            <span aria-label="The assistant is typing">…</span>
          </Typography>
        ) : (
          <Typography component="div">
            <PartsView parts={content} live={live} actionsActive={actionsActive} answeredWith={answeredWith} onChoose={onChoose} />
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
