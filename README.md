# LedgerLoop

Always-on data-reliability teammate for fintech data teams, built as a LangSmith Fleet agent that works in Slack
alongside a data engineer, finance ops and compliance. Applied AI for Entrepreneurs, Module 2 (weeks 4-6).

Design doc: [docs/LedgerLoop_one_pager.pdf](docs/LedgerLoop_one_pager.pdf)

## Layout
| Path | Purpose |
|---|---|
| `ledgerloop-core/AGENTS.md` | Agent prompt: outcome, team, triggers, operating sequence, autonomy tiers, hard constraints |
| `ledgerloop-core/config.json`, `tools.json` | Fleet agent metadata; 14 MCP tools with approval gates (`interrupt_config`) |
| `ledgerloop-core/skills/incident-pattern-library/SKILL.md` | Known-safe patterns, never-auto list, evaluator rubric |
| `ledgerloop-core/server.py` | FastMCP data-platform server (simulated incident data in memory) |

## Run / deploy
```
cd ledgerloop-core && pip install -r requirements.txt && python server.py --http   # serves /mcp
```
Deployed on Render (root directory `ledgerloop-core`, start `python server.py --http`): `https://applied-ai-fleet-project.onrender.com/mcp`.

Module 1 (customs mismatch resolver) is preserved on `main`.
