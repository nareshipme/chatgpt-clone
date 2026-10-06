import type { MessagePart } from "../api/types";

/** Text of a message's text parts only (what the user typed / what the model wrote). */
export const textOf = (parts: MessagePart[]): string =>
  parts.map((p) => (p.type === "text" ? p.text : "")).join("");

/** A readable plain-text version of a whole message, used by "Copy message". Tables become tab-separated rows
 *  (they paste straight into a spreadsheet); other structured parts become a short bracketed description. */
export function partsToPlainText(parts: MessagePart[]): string {
  return parts
    .map((p) => {
      switch (p.type) {
        case "text":
          return p.text;
        case "table":
          return [p.title, p.columns.join("\t"), ...p.rows.map((r) => r.map((c) => (c ?? "")).join("\t"))].filter(Boolean).join("\n");
        case "chart":
          return `[chart${p.title ? `: ${p.title}` : ""}]`;
        case "image":
          return `[image: ${p.alt}]`;
        case "actions":
          return [p.prompt, p.options.map((o) => o.label).join(" | ")].filter(Boolean).join("\n");
      }
    })
    .filter((s) => s !== "")
    .join("\n\n");
}
