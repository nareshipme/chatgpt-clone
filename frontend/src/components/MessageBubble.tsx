import CheckIcon from "@mui/icons-material/Check";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import { Box, Button, Chip, CircularProgress, IconButton, Paper, Stack, Tooltip, Typography } from "@mui/material";
import { useState } from "react";
import type { MessagePart, Provenance, ToolEvent } from "../api/types";
import { COLORS } from "../app/theme";
import { copyText } from "../lib/clipboard";
import { partsToPlainText } from "../lib/parts";
import { toolLabel } from "../lib/tools";
import { PartsView } from "./PartsView";
import { WhyDrawer } from "./WhyDrawer";

interface Props {
  role: "user" | "assistant" | "system";
  /** The message content as typed parts. For plain text you may pass `text` instead. */
  parts?: MessagePart[];
  text?: string;
  /** Saved status of an assistant message, shown as a quiet note. */
  status?: "streaming" | "complete" | "interrupted" | "error";
  /** True while this bubble is still receiving content. */
  live?: boolean;
  /** Tools run for this reply so far (shown while it is being written). */
  tools?: ToolEvent[];
  /** How the answer was made (saved with the reply): drives the "Why this answer" drawer. */
  provenance?: Provenance[];
  /** Choice buttons in this message can be clicked (only the newest reply with nothing after it). */
  actionsActive?: boolean;
  answeredWith?: string;
  onChoose?: (value: string) => void;
}

export function MessageBubble({ role, parts, text = "", status, live, tools = [], provenance = [], actionsActive, answeredWith, onChoose }: Props) {
  const content: MessagePart[] = parts ?? (text ? [{ type: "text", text }] : []);
  const isUser = role === "user";
  const hasContent = content.some((p) => p.type !== "text" || p.text);
  const waiting = !isUser && !hasContent && tools.length === 0 && (live || status === "streaming");
  const [copied, setCopied] = useState(false);
  const [whyOpen, setWhyOpen] = useState(false);
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
          bgcolor: isUser ? COLORS.navy : COLORS.grey50,
          border: isUser ? 0 : 1,
          borderColor: COLORS.grey100,
          color: isUser ? "#fff" : "text.primary",
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
            {tools.length > 0 && (
              <Stack direction="row" flexWrap="wrap" gap={0.5} sx={{ mb: 1 }} role="status" aria-label="Tools used">
                {tools.map((t) => (
                  <Chip
                    key={t.id}
                    size="small"
                    variant="outlined"
                    color={t.status === "error" ? "error" : t.status === "done" ? "success" : "default"}
                    icon={t.status === "running" ? <CircularProgress size={12} /> : undefined}
                    label={t.status === "running" ? `Checking: ${toolLabel(t.name)}` : t.status === "done" ? `Checked: ${toolLabel(t.name)}` : `Could not check: ${toolLabel(t.name)}`}
                  />
                ))}
              </Stack>
            )}
            <PartsView parts={content} live={live} actionsActive={actionsActive} answeredWith={answeredWith} onChoose={onChoose} />
          </Typography>
        )}
        {!isUser && !live && provenance.length > 0 && (
          <>
            <Button size="small" startIcon={<InfoOutlinedIcon fontSize="small" />} onClick={() => setWhyOpen(true)} sx={{ mt: 0.5, textTransform: "none" }}>
              Why this answer
            </Button>
            <WhyDrawer open={whyOpen} onClose={() => setWhyOpen(false)} provenance={provenance} />
          </>
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
