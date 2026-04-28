# MCP on Databricks — A 3-Hour Workshop

A hands-on introduction to **Model Context Protocol (MCP)** for data engineers, data scientists, and analysts. Everything runs **inside your Databricks Free Edition workspace**. No local install. No leaving the browser (except one optional `databricks bundle deploy` for Section E).

## What you'll do

By the end you will:

- Know what MCP is, why the industry adopted it, and how it works.
- Have driven managed MCP servers (Genie text-to-SQL, Vector Search, UC Functions) from **Genie Code** *and* **AI Playground**.
- Understand external MCPs and how to wire them up.
- Have peeked under the hood from a Databricks notebook — seen the literal JSON-RPC, including sampling and elicitation.
- Have deployed a custom MCP server as a Databricks App and used it from Genie Code.

## The scenario

> **The Bakehouse Detective.** Crumbly Creations (the Austin franchise of our bakery chain) had a single day in May 2024 where it took only $6 in revenue. Use every MCP server we wire up to figure out *what happened*.

Same scenario across all five sections, dataset is `samples.bakehouse` (preloaded in Free Edition).

## Schedule

| Time         | Section                                                        |
|--------------|----------------------------------------------------------------|
| 0:00 – 1:00  | **Lecture** — open `docs/lecture.html` in your browser          |
| 1:00 – 1:25  | [**A. Genie Code + managed MCP**](#section-a--genie-code--managed-mcp) |
| 1:25 – 1:50  | [**B. AI Playground + managed MCP**](#section-b--ai-playground--managed-mcp) |
| 1:50 – 2:00  | [**C. External MCP** (discussion-only)](#section-c--external-mcp) |
| 2:00 – 2:35  | [**D. Notebook deep-dive**](#section-d--notebook-deep-dive)     |
| 2:35 – 3:00  | [**E. Custom MCP as a Databricks App**](#section-e--custom-mcp-as-a-databricks-app) |

## Prerequisites

1. **Databricks Free Edition workspace** — sign up at https://www.databricks.com/learn/free-edition.
2. A web browser.
3. *(Section E only)* the **Databricks CLI** locally — `brew install databricks` or see the docs. Used for `databricks bundle deploy`.

## Repo layout

```
.
├── README.md                  <- you are here
├── databricks.yml             <- DAB bundle (notebook + App)
├── docs/
│   ├── lecture.html           <- Hour 1 deck — open in your browser
│   └── architecture.md        <- production-patterns appendix
├── notebook/
│   └── mcp_under_the_hood.py  <- Section D notebook (Databricks source format)
└── app/
    ├── main.py                <- Section E FastMCP server
    ├── app.yaml
    └── requirements.txt
```

## Deployable artifacts

Everything that *can* be code-deployed is in the bundle:

```bash
databricks bundle validate -p <profile>
databricks bundle deploy   -p <profile>     # uploads notebook + registers App
databricks bundle run bakehouse_detective -p <profile>   # starts the App
```

Not in the bundle: Genie Code wiring, Playground tool config, external MCP URLs, the lecture HTML. Those are workspace-UI or local-browser concerns.

---

## Three runtime checks before workshop day

Some MCP surfaces shipped in March 2026 and Free Edition support is uncertain in current docs. Verify on your workspace before the live event:

1. **Genie Code** in the right sidebar of any notebook. If absent, fold Section A into Section B.
2. **AI Playground → Tools → Add tool → MCP Servers** present. If not, demo SQL Editor's Genie integration in Section B.
3. **Apps deploy works.** The bundle in this repo deploys cleanly on Free Edition (verified 2026-04-28). Try `databricks bundle run` once before the live event.

---

# Section A — Genie Code + managed MCP

> **25 min. No code.** Drive the in-workspace AI agent and watch it reach for the right MCP tool on its own.

Genie Code (released March 2026, replaced Databricks Assistant) is the chat sidebar inside notebooks and the SQL editor. It supports MCP natively.

## Step 1 — Look at what's already wired (3 min)

Top-left → **Agents** → **MCP Servers**. You should see at least:

| Server                  | What it does                                                                                       |
|-------------------------|----------------------------------------------------------------------------------------------------|
| **UC Functions**        | Every UC function in any schema you can read becomes an MCP tool.                                   |
| **Vector Search**       | Every Vector Search index you can read becomes an MCP tool.                                         |
| **Genie Spaces**        | Every Genie Space you have access to (text-to-SQL).                                                  |

These are **managed** servers — Databricks operates them, your workspace identity authorizes you, no setup.

> **Heads up — 20-tool cap.** A host session can attach at most 20 tools across all MCP servers.

## Step 2 — Genie Code knows about `samples.bakehouse` (5 min)

In a fresh notebook, open Genie Code and ask:

> *"What tables are in `samples.bakehouse`? Show me one row from each."*

Genie Code calls a SQL tool. Three tables come back: `media_customer_reviews`, `sales_franchises`, `sales_transactions`. You wrote zero code.

## Step 3 — Use the pre-built Genie Space (5 min)

Free Edition ships a Genie Space called **"Bakehouse Sales Starter Space"** over the bakehouse sales tables. Already attached as a managed MCP source.

> *"Use the Bakehouse Sales Starter Space to find which franchise had the lowest single-day revenue across the entire dataset."*

Expected: surfaces **Crumbly Creations** (Austin, US) on **2024-05-08** at **$6**. That's the workshop's investigation hook.

## Step 4 — Look at the customer reviews (7 min)

> *"Search the customer reviews in `samples.bakehouse.media_customer_reviews` for any text mentioning 'Austin' or 'Crumbly'. Return up to 5 reviews with their review dates."*

Note: only ~6 reviews are tagged to Austin's franchise. Without a Vector Search index, the model uses SQL `LIKE` — try:

> *"Are there any reviews talking about a closure, outage, or really bad day at any franchise?"*

The model has to be creative without semantic search. We'll fix that with a custom server in Section E.

## Step 5 — Stitch it together (5 min)

> *"Build a one-paragraph hypothesis about what happened at Crumbly Creations on 2024-05-08. Use the sales data and any related reviews to form your view. Cite the evidence."*

Watch the trace expand: SQL on `sales_transactions` for that day, SQL on reviews, model synthesizing. Likely outcome: *"isolated single-day operational issue — closure or POS outage"*, **not** a sustained slump.

## Discussion (5 min)

1. **Tool selection.** Re-read 2 of the traces — was the choice obvious from the prompts?
2. **Permission boundaries.** Try asking Genie Code to read a catalog you don't have access to. It fails cleanly because the managed servers run as you. UC ACLs apply automatically.

---

# Section B — AI Playground + managed MCP

> **25 min.** Same managed MCPs, different surface. The point: see the *trace*. Watch the model pick a tool, format arguments, read responses.

Top-left → **Machine Learning** → **AI Playground**. Pick a tool-capable model. **Tools → + Add tool → MCP Servers**.

## Step 1 — Attach the managed servers (3 min)

In Tools → Add tool → MCP Servers, attach:
- **UC Functions** (no schema scope = all schemas you can access)
- **Vector Search**
- **Genie Spaces** → "Bakehouse Sales Starter Space"

Apply. Tool count appears in the panel. Remember: 20-tool cap.

## Step 2 — Same first question, watch the trace (5 min)

> *"What tables are in `samples.bakehouse`? Show me one row from each."*

Click the trace expander. You should see:

```
tools/call
  name: query
  arguments: { "statement": "SELECT * FROM samples.bakehouse.<table> LIMIT 1" }

tool_result
  [..rows..]
```

**This is what Genie Code did silently.** Same wire calls.

## Step 3 — Genie Space tool with arguments visible (7 min)

> *"Using the Bakehouse Sales Starter Space, find the worst single sales day for any franchise. Return the franchise name, date, and revenue."*

In the trace, find the call to the Genie Space tool. You'll see the natural-language question Playground passed to Genie, the SQL Genie generated, and the result rows.

Now experiment:

> *"That answer was good. Now ask the same question but break it down by country and weekend-vs-weekday."*

Read which tool the model chose for the follow-up. Either is reasonable; the *trace* is the value.

## Step 4 — Compare across models (5 min, optional)

Switch the model dropdown. Re-run:

> *"What is the most likely explanation for Crumbly Creations earning only $6 on 2024-05-08? Use the sales and reviews data."*

Different models pick different tools first. Different reasoning chains. Different conclusions. **The tool catalog is identical**; the *agent* changes.

## Step 5 — System prompt → behavior (5 min)

Paste:

```
You are a careful data analyst. For every claim you make, you must cite either
a SQL result or a specific review text. If you don't have evidence, say so.
```

Re-ask the May-8 question. The trace changes — more tool calls, more grounding.

## Discussion (5 min)

1. **Genie Code vs Playground.** Genie Code is "ambient, in your workflow." Playground is "explicit, see what's happening, iterate on prompts." Same plumbing.
2. **Trace is the killer feature** of MCP for debugging agents.
3. **Tool description = prompt engineering at the server level.** Better descriptions → better selection.

---

# Section C — External MCP

> **10 min, discussion-only.** No hands-on. We talk through what an *external* MCP is and why we're not adding one live.

## What "external" means

An MCP server you don't operate, accessed over **Streamable HTTP**:

- **you.com**, **Brave** — web search
- **GitHub** — repo issues, PRs, file reads
- **Slack, Notion, Linear, Confluence** — first-party MCPs
- A growing **Databricks Marketplace** category for MCP listings

To Genie Code or Playground, these are no different from the managed servers. Same protocol, different URL.

## How you'd add one

In the workspace UI: **Agents → MCP Servers → + Add → External MCP**. Provide:
- **Name** (free text)
- **URL** (the server's Streamable HTTP endpoint)
- **Auth** — usually OAuth 2.1 (workspace negotiates) or a Bearer header you supply

Caveat: Databricks doesn't currently support *dynamic client registration* for OAuth — the external server must be pre-registered as a known app. For paid SaaS MCPs this is fine; for hobby servers it's friction.

## Why we're not doing it live

1. No reliable no-auth public MCP that's both useful and stable enough for a 10-min slot.
2. Workshop time is better spent on Sections D and E.
3. The *concept* is the value here — you've already seen the same protocol in Sections A and B.

## Three things to try after the workshop

1. **you.com** — sign up at https://api.you.com (free tier), generate a key, add as an external MCP, then ask Genie Code something like *"Use you-search to find any 2026 news about Austin's coffee shop competitive landscape."*
2. **Browse Databricks Marketplace** — search for "MCP" in the in-workspace marketplace listings.
3. **A first-party SaaS MCP for a tool your team uses** — Notion, GitHub, Linear, Slack. Most have official MCP servers.

## Why this matters for governance

Every external MCP is a new trust surface:
- **Where does the data go?** A `you-search` call sends your prompt to you.com.
- **Can the model leak via tool args?** Audit your traces.
- **Is the auth scope right?** Scope GitHub tokens to read-only / specific orgs.

In Databricks, the MCP server is configured by an admin; per-user access can be governed.

---

# Section D — Notebook deep-dive

> **35 min.** A pre-written notebook that walks the actual JSON-RPC wire — tools, resources, prompts, sampling, elicitation, plus a connection to a real managed Databricks MCP endpoint.

## Setup

1. In your workspace, **Workspace → your home → + Add → Notebook**, language **Python**.
2. **File → Import**, point at `notebook/mcp_under_the_hood.py` (or paste its contents).
3. Attach to **Serverless** compute.
4. **Run All**.

Or if you ran `databricks bundle deploy`, the notebook is already at `/Workspace/Users/<you>/.bundle/mcp_workshop/<target>/files/notebook/mcp_under_the_hood.py` — open it from there.

## What the cells do

| Cell | What it shows                                                                                       |
|-----:|------------------------------------------------------------------------------------------------------|
|    1 | `%pip install mcp` — restart Python.                                                                  |
|    2 | Define a tiny FastMCP server in this notebook (~30 lines). 3 tools, 1 resource, 1 prompt.             |
|    3 | Connect a client via in-memory transport. Call `tools/list`, `resources/list`, `prompts/list`. Print the wire. |
|    4 | `tools/call`, `resources/read`, `prompts/get`. Each demonstrates a different "who controls this" story. |
|    5 | **Sampling** — define a tool that calls back to the host's LLM. The notebook plays host using **Databricks Foundation Model APIs** (no API key). |
|    6 | **Elicitation** — server asks the user a structured question; notebook responds programmatically.    |
|    7 | Connect to the real **managed Databricks MCP endpoint** over Streamable HTTP using the workspace OAuth token. |

By the end you can sketch MCP on a napkin.

## Troubleshooting

- **`ModuleNotFoundError: mcp`** — first cell didn't run. Re-run, then `dbutils.library.restartPython()`.
- **Sampling cell errors with model not found** — adjust `MODEL_NAME` in cell 5 to a model your workspace serves; check **Machine Learning → Serving**.
- **Cell 7 (managed MCP) errors** — the endpoint path may differ; the rest of the notebook still demonstrates the protocol fully.

---

# Section E — Custom MCP as a Databricks App

> **25 min.** Deploy a pre-written FastMCP server as a Databricks App, then add it to Genie Code's MCP servers and use it. **No Python written from scratch.**

## What you'll deploy

A small FastMCP server (`app/main.py`, ~165 LOC) that adds capabilities the managed servers don't have:

| Tool                    | What it does                                                                            |
|-------------------------|-----------------------------------------------------------------------------------------|
| `franchise_sales_trend` | Daily revenue for a franchise, anchored to dataset window (May 2024).                   |
| `search_reviews`        | Keyword search over `media_customer_reviews`.                                            |
| `compose_brief`         | Uses **sampling** to ask the host's LLM to write a one-paragraph diagnostic brief.       |
| `log_finding`           | Writes the investigator's conclusion to `workspace.default.findings`.                    |
| `franchise://list`      | Resource: a markdown index of all 48 franchises.                                          |
| `/diagnose_franchise`   | Prompt: a slash-command that orchestrates the four tools.                                |

Identity passthrough: every UC call runs as the *calling user* via the `X-Forwarded-Access-Token` header that the Apps platform injects. **External curl calls won't have it** — by design — and the SQL tools fail fast with a clear error. Drive this from inside the workspace.

## Step 1 — Walk through the source (5 min)

Open `app/main.py`. Six call-out points:

1. **Top of file** — `_user_token` / `_user_email` ContextVars; populated by middleware.
2. **`_connect()`** — uses the calling user's token; raises clearly if missing.
3. **`@mcp.tool() franchise_sales_trend`** — note the `dateadd(day, -?, bounds.maxd)` pattern (Databricks SQL doesn't allow `INTERVAL ? DAYS` parameter markers).
4. **`@mcp.tool() async compose_brief`** — `ctx.session.create_message(...)` is **sampling**. **No model API key in this file.**
5. **`@mcp.tool() log_finding`** — only tool with a side effect. `CREATE TABLE IF NOT EXISTS` + `INSERT`. Per-user attribution via `_user_email`.
6. **`capture_user` middleware + `lifespan`** — the entire identity-passthrough story plus the FastMCP-under-FastAPI lifespan plumbing. ~10 lines.

`app/app.yaml` is 8 lines: binds a SQL warehouse, sets two env vars, runs uvicorn.

## Step 2 — Deploy with Databricks Asset Bundles (8 min)

```bash
databricks bundle validate -p <your-profile>
databricks bundle deploy   -p <your-profile>     # uploads source + registers App
databricks bundle run bakehouse_detective -p <your-profile>   # starts compute + deploys code
```

When `bundle run` says *"App started successfully"*, copy the URL — `https://bakehouse-detective-mcp-<id>.aws.databricksapps.com`.

Per-target overrides live in `databricks.yml` under `targets:`. The shipped config defaults to a Free Edition workspace; set `var.warehouse_id` and `workspace.host` to match yours.

Quick sanity:

```bash
curl <App URL>/healthz   # expect {"status": "ok"}
```

### Fallback: deploy via the Apps UI

1. **Compute → Apps → Create app**.
2. **Source code path:** import `app/` from this repo (Git URL or workspace files).
3. **Resources:** bind the Serverless SQL warehouse with binding name `warehouse_id`.
4. **Deploy**. Copy the App URL.

## Step 3 — Add the App to Genie Code (5 min)

**Agents → MCP Servers → + Add → Custom Databricks App** → pick `bakehouse-detective-mcp`. Test connection. You should see **4 tools, 1 resource, 1 prompt**.

If "Custom Databricks App" isn't a dropdown option, fall back to **+ Add → External MCP** with `<App URL>/mcp` as the URL — same result.

## Step 4 — Use it from Genie Code (7 min)

> *"Use the bakehouse-detective server. First get the franchise list, then look at Crumbly Creations' last 14 days of revenue, then search reviews for the word 'closed' or 'wait', then write a brief and log it as a finding with hypothesis 'isolated single-day operational issue on May 8'."*

Watch:

- `franchise://list` is fetched as a *resource*, not a tool call.
- `franchise_sales_trend` runs (May 8 $6 anomaly visible).
- `search_reviews` runs.
- `compose_brief` calls back to the host's LLM via **sampling** — you'll see a nested `sampling/createMessage` request in the trace.
- `log_finding` writes a row to `workspace.default.findings`.

Verify:

```sql
SELECT * FROM workspace.default.findings ORDER BY ts DESC LIMIT 5
```

`user_email` populated as **you** — identity passthrough working.

## Discussion (5 min)

1. **What did this server give you that the managed ones didn't?** A side-effecting tool, a sampling tool, a resource picker, and a curated workflow.
2. **Why a Databricks App?** Workspace OAuth, identity passthrough, autoscaling, no separate billing line.
3. **Production hardening** (out of scope today; see `docs/architecture.md`): `@traced` decorator → `mcp_calls`, lineage rows → `mcp_lineage`, deny-list any tool you don't want exposed, rate-limit per user.

---

# Recap

You walked through:
- **Section A** — Genie Code with managed MCP. Zero config.
- **Section B** — AI Playground with the same MCPs, trace visible.
- **Section C** — External MCP, conceptually.
- **Section D** — A notebook walking the actual JSON-RPC wire.
- **Section E** — Deployed your own MCP capability into the workspace.

Recipe for the next custom server you'll build:

1. Three to six narrowly-scoped tools.
2. One resource for "the catalog" if you have a big list.
3. One prompt for your common workflow.
4. Reach for **sampling** before bringing a model API key into the server.
5. Ship it as a Databricks App. UC handles the governance.
6. That's it.

For deeper production patterns (gateway, identity passthrough, audit/lineage in Delta), see `docs/architecture.md`.
