# Notion import

1. **Docs:** in Notion, create a page "ChatGPT Clone", then Import -> Markdown/CSV -> `docs/PLAN.md` (Mermaid blocks import as code blocks; set their language to Mermaid to render).
2. **Feature tracker:** Import -> CSV -> `docs/notion/feature-tracker.csv`. Then change `Status`, `Priority`, `Slice`, `Type` to **Select** properties and add a Board view grouped by Status and a Table view grouped by Slice.
3. After the Notion MCP is authorised (`/mcp` in an interactive Claude Code session), the agent can keep both in sync.
