# Module 2 - LedgerLoop (multiplayer data-reliability teammate for fintech)

Applied AI for Entrepreneurs, weeks 4-6. Design doc: [LedgerLoop_one_pager.pdf](LedgerLoop_one_pager.pdf).

| Path | What |
|---|---|
| `fleet/` | LangSmith Fleet agent: `AGENTS.md`, `config.json`, `tools.json`, `skills/incident-pattern-library/SKILL.md` |
| `mcp-server/` | Mock fintech data-platform MCP server (FastMCP, 14 tools, 5 incidents covering every autonomy tier) |
| `LedgerLoop_one_pager.pdf` | One-page design doc: architecture, design choices tied to course articles |

Run the mock backend: `cd mcp-server && pip install -r requirements.txt && python server.py --http` (endpoint `/mcp`).
Set `mcp_server_url` in `fleet/tools.json` to the deployed URL. Slack channel and schedules are configured in Fleet (see doc).
Module 1 (customs mismatch resolver) is unchanged on `main`.
