import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import { Box, IconButton, Link, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tooltip } from "@mui/material";
import { Children, isValidElement, memo, useState, type ComponentPropsWithoutRef, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import bash from "highlight.js/lib/languages/bash";
import css from "highlight.js/lib/languages/css";
import diff from "highlight.js/lib/languages/diff";
import go from "highlight.js/lib/languages/go";
import java from "highlight.js/lib/languages/java";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import markdown from "highlight.js/lib/languages/markdown";
import python from "highlight.js/lib/languages/python";
import rust from "highlight.js/lib/languages/rust";
import sql from "highlight.js/lib/languages/sql";
import typescript from "highlight.js/lib/languages/typescript";
import xml from "highlight.js/lib/languages/xml";
import yaml from "highlight.js/lib/languages/yaml";
import remarkGfm from "remark-gfm";
import { copyText } from "../lib/clipboard";
import "highlight.js/styles/github.css";

/**
 * Safe by construction:
 *  - react-markdown does not render raw HTML at all (a <script> or <img onerror> in a reply is shown as text/dropped);
 *  - links only keep http(s) and mailto, and open in a new tab with noopener noreferrer;
 *  - images must be absolute https URLs, load lazily and send no referrer (a hostile image URL must not
 *    learn who is reading, and http would be mixed content).
 */
// A curated set instead of highlight.js's whole library keeps the bundle small; anything else renders as plain code.
const LANGUAGES = { bash, css, diff, go, java, javascript, json, markdown, python, rust, sql, typescript, xml, yaml, html: xml, js: javascript, ts: typescript, sh: bash, py: python };

const SAFE_LINK = /^(https?:|mailto:)/i;
const SAFE_IMAGE = /^https:\/\//i;

function urlTransform(url: string, key: string): string {
  if (key === "src") return SAFE_IMAGE.test(url) ? url : "";
  return SAFE_LINK.test(url) ? url : "";
}

/** Concatenate the text inside a React subtree (react-markdown hands code blocks over as elements). */
function plainText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(plainText).join("");
  if (isValidElement<{ children?: ReactNode }>(node)) return plainText(node.props.children);
  return "";
}

function CodeBlock({ children }: ComponentPropsWithoutRef<"pre">) {
  const [copied, setCopied] = useState(false);
  const code = Children.toArray(children).find(isValidElement) as { props: { className?: string; children?: ReactNode } } | undefined;
  const language = /language-(\w+)/.exec(code?.props.className ?? "")?.[1];
  const source = plainText(children).replace(/\n$/, "");

  async function copy() {
    if (await copyText(source)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }

  return (
    <Box sx={{ my: 1.5, border: 1, borderColor: "divider", borderRadius: 2, overflow: "hidden", bgcolor: "background.paper" }}>
      <Box sx={{ display: "flex", alignItems: "center", px: 1.5, py: 0.25, bgcolor: "action.hover" }}>
        <Box component="span" sx={{ flex: 1, fontSize: 12, color: "text.secondary" }}>
          {language ?? "code"}
        </Box>
        <Tooltip title={copied ? "Copied" : "Copy code"}>
          <IconButton size="small" onClick={() => void copy()} aria-label="Copy code">
            <ContentCopyIcon fontSize="inherit" />
          </IconButton>
        </Tooltip>
      </Box>
      <Box component="pre" sx={{ m: 0, p: 1.5, overflowX: "auto", fontSize: 13, lineHeight: 1.5, "& code": { fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace", background: "none" } }}>
        {children}
      </Box>
    </Box>
  );
}

const components: Components = {
  pre: CodeBlock,
  code: ({ className, children, ...rest }) => (
    <code className={className} {...rest}>
      {children}
    </code>
  ),
  a: ({ href, children }) =>
    href ? (
      <Link href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </Link>
    ) : (
      <>{children}</>
    ),
  img: ({ src, alt }) =>
    src ? (
      <Box component="img" src={src} alt={alt ?? ""} loading="lazy" referrerPolicy="no-referrer" sx={{ maxWidth: "100%", borderRadius: 2, my: 1 }} />
    ) : (
      <span>{alt ? `[image: ${alt}]` : "[image blocked]"}</span>
    ),
  table: ({ children }) => (
    <TableContainer sx={{ my: 1.5, border: 1, borderColor: "divider", borderRadius: 2 }}>
      <Table size="small">{children}</Table>
    </TableContainer>
  ),
  thead: ({ children }) => <TableHead>{children}</TableHead>,
  tbody: ({ children }) => <TableBody>{children}</TableBody>,
  tr: ({ children }) => <TableRow>{children}</TableRow>,
  th: ({ children }) => <TableCell sx={{ fontWeight: 600 }}>{children}</TableCell>,
  td: ({ children }) => <TableCell>{children}</TableCell>,
};

function MarkdownImpl({ children }: { children: string }) {
  return (
    <Box
      sx={{
        wordBreak: "break-word",
        "& > :first-of-type": { mt: 0 },
        "& > :last-child": { mb: 0 },
        "& p": { my: 1 },
        "& ul, & ol": { pl: 3, my: 1 },
        "& blockquote": { m: 0, my: 1, pl: 2, borderLeft: 3, borderColor: "divider", color: "text.secondary" },
        "& :not(pre) > code": { px: 0.5, borderRadius: 1, bgcolor: "action.selected", fontSize: "0.9em" },
        "& h1, & h2, & h3, & h4": { mt: 2, mb: 1, lineHeight: 1.3, fontSize: "1.1em" },
      }}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[[rehypeHighlight, { detect: false, ignoreMissing: true, languages: LANGUAGES }]]} urlTransform={urlTransform} components={components}>
        {children}
      </ReactMarkdown>
    </Box>
  );
}

/** Memoised: while a reply streams, earlier messages must not re-render on every token. */
export const Markdown = memo(MarkdownImpl);
