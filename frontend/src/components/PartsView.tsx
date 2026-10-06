import { Box, CircularProgress } from "@mui/material";
import { lazy, Suspense } from "react";
import type { MessagePart } from "../api/types";
import { ActionsView } from "./parts/ActionsView";
import { ImageView } from "./parts/ImageView";
import { TableView } from "./parts/TableView";

// The heavy renderers are loaded on demand: Markdown (react-markdown, highlight.js) and charts (Recharts)
// are only needed once a reply contains them; sign-in and empty chats never download them.
const Markdown = lazy(() => import("./Markdown").then((m) => ({ default: m.Markdown })));
const ChartView = lazy(() => import("./parts/ChartView"));

interface Props {
  parts: MessagePart[];
  /** True while the reply is still arriving: adds a cursor to the last text part. */
  live?: boolean;
  actionsActive?: boolean;
  /** The user message that followed this reply, if any (used to show which option was chosen). */
  answeredWith?: string;
  onChoose?: (value: string) => void;
}

function Placeholder() {
  return (
    <Box sx={{ display: "grid", placeItems: "center", minHeight: 48 }}>
      <CircularProgress size={18} aria-label="Loading" />
    </Box>
  );
}

export function PartsView({ parts, live, actionsActive = false, answeredWith, onChoose }: Props) {
  const lastIndex = parts.length - 1;
  return (
    <>
      {parts.map((part, i) => {
        switch (part.type) {
          case "text":
            return (
              <Suspense key={i} fallback={<span style={{ whiteSpace: "pre-wrap" }}>{part.text}</span>}>
                <Markdown>{live && i === lastIndex ? `${part.text} ▍` : part.text}</Markdown>
              </Suspense>
            );
          case "table":
            return <TableView key={i} part={part} />;
          case "chart":
            return (
              <Suspense key={i} fallback={<Placeholder />}>
                <ChartView part={part} />
              </Suspense>
            );
          case "image":
            return <ImageView key={i} part={part} />;
          case "actions":
            return <ActionsView key={i} part={part} active={actionsActive} answeredWith={answeredWith} onChoose={(v) => onChoose?.(v)} />;
        }
      })}
    </>
  );
}
