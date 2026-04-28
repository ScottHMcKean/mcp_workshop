# Hour 1, Part B — Production Patterns on Databricks (Appendix)

> Goal: by the end of this section, you can sketch an MCP architecture on a whiteboard and defend every box.
>
> **Note:** this workshop runs entirely inside Databricks Free Edition (Genie Code, AI Playground, a notebook, a Databricks App). The patterns below are what you'd reach for when productionizing for your team — covered conceptually here, not all built in the hands-on portion.

## The reference architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  HOST: Genie Code  /  AI Playground  /  your Databricks notebook │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐                 │
│   │  Client A  │  │  Client B  │  │  Client C  │                 │
│   └─────┬──────┘  └──────┬─────┘  └──────┬─────┘                 │
└─────────┼────────────────┼───────────────┼──────────────────────┘
          │                │               │
   ┌──────▼─────┐   ┌──────▼─────┐  ┌──────▼─────────────┐
   │  Managed   │   │  External  │  │ bakehouse-detective │
   │  MCPs      │   │  MCP       │  │  (your FastMCP, on │
   │  (Genie,   │   │  (you.com  │  │   a Databricks App)│
   │   VS, UC)  │   │   etc.)    │  │                     │
   └─────┬──────┘   └────────────┘  └─────────┬───────────┘
         │                                    │
         └──────────────┬─────────────────────┘
                        │
                ┌───────▼────────┐
                │  Databricks    │
                │   Free Edition │
                │  (UC, Genie,   │
                │  VS, Apps)     │
                └────────────────┘
```

Three things to note:

1. **Servers do not talk to each other.** The host fans out and reconciles.
2. **Managed MCPs are zero-config** — they appear in *Agents → MCP Servers* the moment you log in.
3. **Only `bakehouse-detective` is something you operate** (Section E). The rest you consume.

## Pattern 1 — The MCP gateway

When you have many MCP servers, do not give the host N URLs. Run one **gateway** server that aggregates them. Reasons:

- Single auth surface.
- Single quota / rate-limit point.
- A `tools/list` denylist for "we don't want users to see *that* tool from the upstream."
- Tool name namespacing (`internal.consumption.query` vs `web.search`).
- Observability: every call passes through one place.

Databricks Apps is a great gateway — a FastMCP server proxies to upstream servers and writes audit rows to UC.

## Pattern 2 — Identity passthrough

The single most important governance decision: **does the MCP server act as the user, or as itself?**

| Mode                  | Pros                              | Cons                                                |
|-----------------------|-----------------------------------|-----------------------------------------------------|
| Service principal     | Easy, one identity to provision   | Lose per-user attribution; UC ACLs become "the SP can do everything" |
| **Identity passthrough** | UC RLS/CLS just works; real audit | Must forward tokens correctly; tokens expire        |

In a Databricks App, the user's OAuth token is available as `X-Forwarded-Access-Token`. Use it. Do not run an SP unless you have a hard reason.

## Pattern 3 — Tools that *are* UC functions

A Unity Catalog Python function is callable from Genie, the SQL editor, and an MCP server with no glue code.

```sql
CREATE OR REPLACE FUNCTION main.workshop.franchise_health(
  franchise_id STRING
) RETURNS DOUBLE
LANGUAGE PYTHON AS $$ ... $$;
```

The Databricks UC Functions MCP server exposes every UC function in a schema as a tool, with permissions enforced by UC. This is the cheapest way to ship a governed tool — you don't write any MCP code.

**Rule of thumb**: if the tool is "read or compute over Delta", make it a UC function. Reach for FastMCP only when you need sampling, elicitation, resources, or non-Delta side effects.

## Pattern 4 — Genie as a tool

A Genie Space is callable as an MCP tool through the managed Genie MCP server. Don't reimplement text-to-SQL — let Genie own that, and have your custom server orchestrate around it.

```
custom MCP tool: compose_brief(franchise)
  ├─ calls ask_genie:    "Austin sales trend last 90 days"
  ├─ calls query_vs_index: "Austin reviews mentioning waiting"
  ├─ calls you.com:      "Austin food-and-bev competition 2026"
  ├─ ctx.session.create_message(...)   <- sampling
  └─ writes a Delta row to a `findings` table
```

This is the layering people miss. **Genie is not the agent — Genie is one of the agent's tools.** Same for Vector Search.

## Pattern 5 — Resources for "give me the catalog"

Browsing 5,000 franchises as a tool argument autocomplete is bad UX. Expose them as **resources**:

```
franchise://list                 <- index resource
franchise://austin/profile        <- per-franchise markdown
franchise://austin/recent_signals <- per-franchise live data (subscribable, drives notifications)
```

The host can render these as a picker. The user attaches one to context. The model never sees the full list.

## Pattern 6 — Governance as Delta tables

Don't outsource your audit log. Write it.

```sql
CREATE TABLE main.observability.mcp_calls (
  call_id STRING, ts TIMESTAMP, user_email STRING,
  server STRING, tool STRING, args STRING, latency_ms BIGINT,
  status STRING, error STRING
) USING DELTA;

CREATE TABLE main.observability.mcp_lineage (
  call_id STRING, ts TIMESTAMP, user_email STRING,
  produced_table STRING, produced_uri STRING,
  source_tools ARRAY<STRING>
) USING DELTA;
```

Every tool call writes to `mcp_calls`. Every tool that produces a Delta row writes to `mcp_lineage`. You get a real audit trail, a self-service usage dashboard via AI/BI, and a lineage graph that joins to UC system tables.

## Anti-patterns to call out

- **One mega-tool with a `mode` parameter.** Split it. The model picks better with narrow tools.
- **Tool descriptions that re-explain JSON-Schema.** The host already shows the schema. Use the description to say *when to use this tool*.
- **Servers that wrap the OpenAI SDK.** If you find yourself shipping an API key inside an MCP server, you wanted **sampling**.
- **stdio in production.** stdio is for the host's child processes. A Databricks App should not be stdio.
- **Auth via shared bearer in env var.** This is a hack for demos. Use the App's OAuth integration.

## Recap

- Run a gateway. Pass identity through. Govern in UC.
- Reach for UC functions first, FastMCP second.
- Layer Genie and Vector Search as tools, not as agents.
- Audit and lineage are Delta tables, not log files.

Next: open `01-genie-code/README.md` and start Section A.
