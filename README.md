# MCP on Databricks — A 3-Hour Workshop

A hands-on introduction to **Model Context Protocol (MCP)** for data engineers, data scientists, and analysts. Everything runs **inside your Databricks Free Edition workspace**. No local install required.

The workshop's deployed **Bakehouse Detective App** is the through-line: it serves the lecture deck, hosts a live MCP demonstration you can drive from any browser, and is itself the custom MCP server you'll deploy in Section E. One URL covers Hour 1 through Section E.

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

| Time         | Section                                                        | Where                              |
|--------------|----------------------------------------------------------------|------------------------------------|
| 0:00 – 1:00  | **Lecture** + the live demo as a teaser                         | `<App URL>/`                       |
| 1:00 – 1:25  | [**A. Genie Code + managed MCP**](#section-a--genie-code--managed-mcp) | workspace notebook + sidebar |
| 1:25 – 1:50  | [**B. AI Playground + managed MCP**](#section-b--ai-playground--managed-mcp) | workspace AI Playground |
| 1:50 – 2:00  | [**C. External MCP**](#section-c--external-mcp) — you.com walkthrough | workspace UI               |
| 2:00 – 2:35  | [**D. Notebook deep-dive**](#section-d--notebook-deep-dive)     | workspace notebook                |
| 2:35 – 3:00  | [**E. Deploy your own copy**](#section-e--custom-mcp-as-a-databricks-app) | Apps UI + Genie Code           |

## Prerequisites

1. **Databricks Free Edition workspace** — sign up at https://www.databricks.com/learn/free-edition.
2. A web browser.

That's it. Sections A–E run in the workspace UI. (If you'd prefer a CLI deploy in Section E, the repo ships a `databricks.yml` bundle — but the primary path is UI.)

## Repo layout

```
.
├── README.md                  <- you are here
├── databricks.yml             <- DAB bundle (notebook + App)
├── docs/
│   ├── architecture.md        <- production-patterns appendix
│   └── screenshots/           <- README image anchors (drop your PNGs here)
├── notebook/
│   └── mcp_under_the_hood.py  <- Section D notebook (Databricks source format)
└── app/
    ├── main.py                <- FastMCP server + landing/lecture/demo routes
    ├── app.yaml
    ├── requirements.txt
    └── static/
        ├── index.html         <- /         (landing)
        ├── lecture.html       <- /lecture  (Hour 1 reveal.js deck)
        └── demo.html          <- /demo     (live MCP investigation UI)
```

## Deployable artifacts (optional CLI path)

For attendees comfortable with the Databricks CLI, the repo ships a bundle that wraps both Section D's notebook and Section E's App:

```bash
databricks bundle validate -p <profile>
databricks bundle deploy   -p <profile>     # uploads notebook + registers App
databricks bundle run bakehouse_detective -p <profile>   # starts the App
```

Edit `databricks.yml` to point `targets.free.workspace.host` and `var.warehouse_id` at your workspace before running. The UI paths in Sections D and E produce the same result.

---

## Three runtime checks before workshop day

Some MCP surfaces shipped in March 2026 and Free Edition support is uncertain in current docs. Verify on your workspace before the live event:

1. **Genie Code** in the right sidebar of any notebook. If absent, fold Section A into Section B.
2. **AI Playground → Tools → Add tool → MCP Servers** present. If not, demo SQL Editor's Genie integration in Section B.
3. **Apps deploy works.** The bundle in this repo deploys cleanly on Free Edition (verified 2026-04-28). Try `databricks bundle run` once before the live event.

---

# Hour 1 — Lecture + Live Demo

> Before the workshop, **deploy the App once** (see Section E). Once it's running, every attendee just visits the App URL. No clones, no downloads, no setup.

The App's landing page (`/`) has three cards:

- **Lecture** (`/lecture`) — the ~36-slide reveal.js deck. Press `s` for speaker notes.
- **Demo** (`/demo`) — pick a franchise, watch the agent investigate live. Each MCP tool call streams in as a card. This is the workshop's "what is MCP doing?" moment in a single page.
- **MCP endpoint** (`/mcp`) — the Streamable HTTP MCP server. Genie Code and Playground attach to this in Section E.

End the lecture by clicking **Demo** and running an investigation on Crumbly Creations live. That's the bridge from concept to the rest of the workshop.

---

# Section A — Genie Code + managed MCP

> **25 min. No code.** Drive the in-workspace AI agent and watch it reach for the right MCP tool on its own.

Genie Code (released March 2026, replaced Databricks Assistant) is the chat sidebar inside notebooks and the SQL editor. It supports MCP natively.

## Step 1 — Look at what's already wired (3 min)

In the workspace, **top-left nav → Agents → MCP Servers**:

![Agents → MCP Servers panel](docs/screenshots/agents-mcp-servers-panel.png)

You should see at least:

| Server                  | What it does                                                                                       |
|-------------------------|----------------------------------------------------------------------------------------------------|
| **UC Functions**        | Every UC function in any schema you can read becomes an MCP tool.                                   |
| **Vector Search**       | Every Vector Search index you can read becomes an MCP tool.                                         |
| **Genie Spaces**        | Every Genie Space you have access to (text-to-SQL).                                                  |

These are **managed** servers — Databricks operates them, your workspace identity authorizes you, no setup.

Now open any notebook and look at the right sidebar — Genie Code is the small chat icon:

![Genie Code in the notebook sidebar](docs/screenshots/genie-code-sidebar.png)

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

![Genie Code response with trace expanded](docs/screenshots/genie-code-trace.png)

## Discussion (5 min)

1. **Tool selection.** Re-read 2 of the traces — was the choice obvious from the prompts?
2. **Permission boundaries.** Try asking Genie Code to read a catalog you don't have access to. It fails cleanly because the managed servers run as you. UC ACLs apply automatically.

---

# Section B — AI Playground + managed MCP

> **25 min.** Same managed MCPs, different surface. The point: see the *trace*. Watch the model pick a tool, format arguments, read responses.

Top-left → **Machine Learning** → **AI Playground**. Pick a tool-capable model. **Tools → + Add tool → MCP Servers**.

![Playground Tools dropdown with MCP Servers option](docs/screenshots/playground-tools-add.png)

## Step 1 — Attach the managed servers (3 min)

In Tools → Add tool → MCP Servers, attach:
- **UC Functions** (no schema scope = all schemas you can access)
- **Vector Search**
- **Genie Spaces** → "Bakehouse Sales Starter Space"

Apply. Tool count appears in the panel.

> **Heads up — 20-tool cap.** A host session can attach at most 20 tools across all MCP servers. Don't connect every Genie Space and every UC schema.

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

![Playground trace showing tools/call JSON](docs/screenshots/playground-trace.png)

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

> **10 min.** A worked walkthrough wiring up **you.com** as an external MCP — same dialog, same protocol as the managed servers, just an internet URL instead of a Databricks one.

## What "external" means

An MCP server you don't operate, accessed over **Streamable HTTP**:

- **you.com**, **Brave** — web search
- **GitHub**, **GitLab** — repo issues, PRs, file reads
- **Slack, Notion, Linear, Confluence** — first-party MCPs from those vendors
- A growing **Databricks Marketplace** category for MCP listings

To Genie Code or Playground, these are no different from managed servers. Same protocol, different URL.

## Step 1 — Get a free you.com key (~2 min)

1. Visit https://api.you.com.
2. Sign up — free tier, no credit card required.
3. Generate an API key. Keep it for Step 3.

If you'd rather not sign up live, watch the instructor's screencap and skip ahead — the dialog is the value, the key is replaceable.

## Step 2 — Open the Add External MCP dialog

In the workspace: **Agents → MCP Servers → + Add → External MCP**.

![Add External MCP dialog](docs/screenshots/add-external-mcp-dialog.png)

## Step 3 — Fill in the form (~2 min)

| Field         | Value                                                            |
|---------------|------------------------------------------------------------------|
| **Name**      | `you-search`                                                     |
| **URL**       | `https://mcp.you.com/v1`                                          |
| **Auth**      | Bearer header → `Authorization: Bearer <your-key>`                |

![Filled-in form](docs/screenshots/external-mcp-form-filled.png)

Hit **Connect**. After a few seconds the panel should show `you-search` Connected with a tool count:

![you-search connected](docs/screenshots/external-mcp-connected.png)

> **Caveat.** Databricks doesn't currently support *dynamic client registration* for OAuth — the external server must be pre-registered as a known app. For paid SaaS MCPs this is fine; for hobby servers it's friction. you.com works because they pre-registered.

## Step 4 — Drive it (~3 min)

In Genie Code, ask:

> *"Use you-search to find any 2026 news about Austin's coffee shop competitive landscape. Then combine that with the bakehouse data and refine your hypothesis about the May 8 anomaly at Crumbly Creations."*

![Trace showing you-search call](docs/screenshots/you-search-trace.png)

Notice in the trace: the model ran `you-search` first, then went back to UC SQL on `samples.bakehouse`, then synthesized. **External MCP and managed MCP composed in a single agent turn.** Same trace shape; some calls hit the public internet, some stayed in your workspace.

## Discussion (~3 min)

Every external MCP is a new trust surface. Things to think about before adding one for your team:

- **Where does the data go?** A `you-search` call sends your prompt to you.com. Is that OK for your team's policy?
- **Can the model leak via tool args?** A naive agent might paste customer data into a web search. Audit your traces.
- **Is the auth scope right?** A GitHub MCP wired with a full org PAT gives the agent everything. Scope it down.

In Databricks, MCP servers are configured by an admin; per-user access is governed in *Agents → MCP Servers*.

## Try after the workshop

- Browse the in-workspace **Marketplace** for the MCP category (in public preview as of April 2026).
- Wire a first-party SaaS MCP for something your team already uses — Notion, GitHub, Slack. Most major SaaS vendors ship one.

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

> **25 min.** Deploy *your own copy* of the App you've been using all hour — same lecture, same demo, your own MCP server. Add it to Genie Code's MCP servers and use it. **No Python written from scratch.**

## What you'll deploy

The same `app/` you've already seen serving the lecture and demo. It's a small FastMCP server (`app/main.py`, ~350 LOC) that:

- Hosts the workshop's static pages (`/`, `/lecture`, `/demo`).
- Streams a live investigation via SSE at `/demo/investigate`.
- Exposes an MCP server at `/mcp` with these capabilities the managed servers don't have:

| Tool                    | What it does                                                                            |
|-------------------------|-----------------------------------------------------------------------------------------|
| `franchise_sales_trend` | Daily revenue for a franchise, anchored to dataset window (May 2024).                   |
| `search_reviews`        | Keyword search over `media_customer_reviews`.                                            |
| `compose_brief`         | Uses **sampling** to ask the host's LLM to write a one-paragraph diagnostic brief.       |
| `log_finding`           | Writes the investigator's conclusion to `workspace.default.findings`.                    |
| `franchise://list`      | Resource: a markdown index of all 48 franchises.                                          |
| `/diagnose_franchise`   | Prompt: a slash-command that orchestrates the four tools.                                |

Identity behavior: the App captures `x-forwarded-email` from every authenticated request and uses it for audit attribution (the `findings` table records who triggered each finding). Whether downstream UC and FMAPI calls run *as the user* (full identity passthrough) or as the App's service principal depends on workspace tier:

- **Paid workspaces with `user_authorization` enabled** — `x-forwarded-access-token` is forwarded; the App runs every Databricks call as the calling user. UC RLS/CLS apply naturally.
- **Free Edition (April 2026)** — only identity *attribution* headers come through, not the OAuth token. The App runs as its own service principal but logs the user's email for the audit trail. The demo's step 0 card tells you which mode you're in.

Either mode is a real production pattern. The workshop demonstrates both — with the right copy in step 0.

## Step 1 — Walk through the source (5 min)

Open `app/main.py`. Six call-out points:

1. **Top of file** — `_user_token` / `_user_email` ContextVars; populated by middleware.
2. **`_connect()`** — uses the calling user's token; raises clearly if missing.
3. **`@mcp.tool() franchise_sales_trend`** — note the `dateadd(day, -?, bounds.maxd)` pattern (Databricks SQL doesn't allow `INTERVAL ? DAYS` parameter markers).
4. **`@mcp.tool() async compose_brief`** — `ctx.session.create_message(...)` is **sampling**. **No model API key in this file.**
5. **`@mcp.tool() log_finding`** — only tool with a side effect. `CREATE TABLE IF NOT EXISTS` + `INSERT`. Per-user attribution via `_user_email`.
6. **`capture_user` middleware + `lifespan`** — the entire identity-passthrough story plus the FastMCP-under-FastAPI lifespan plumbing. ~10 lines.

`app/app.yaml` is 8 lines: binds a SQL warehouse, sets two env vars, runs uvicorn.

## Step 2 — Deploy via the Apps UI (8 min) — *the primary path*

In the workspace:

1. **Compute → Apps → Create app**.

   ![Compute → Apps → Create app](docs/screenshots/apps-create.png)

2. **Source code path** → import the `app/` directory from this repo. Two ways:
   - **From a Git URL** (easiest): paste the repo URL, set the path to `app/`.
   - **From workspace files**: clone the repo into a Git Folder, point the App at `<workspace>/mcp_workshop/app/`.

3. **Resources** → add the Serverless SQL Warehouse with binding name `warehouse_id` (this matches `app.yaml`).

   ![App configuration form](docs/screenshots/apps-config-form.png)

4. **Deploy**. Wait ~3–5 min for the build.

5. When status flips to `Running`, copy the **App URL** — something like `https://bakehouse-detective-mcp-<id>.aws.databricksapps.com`.

   ![App in RUNNING state](docs/screenshots/apps-running.png)

Sanity check (open the URL in your browser and add `/healthz`):

```
{"status": "ok"}
```

### Alternative: deploy with Databricks Asset Bundles

If you have the Databricks CLI configured, the repo ships a `databricks.yml` that registers the same App:

```bash
databricks bundle validate -p <your-profile>
databricks bundle deploy   -p <your-profile>     # uploads source + registers App
databricks bundle run bakehouse_detective -p <your-profile>   # starts compute + deploys code
```

Edit `databricks.yml` under `targets:` to set `var.warehouse_id` and `workspace.host` to your workspace before running. Faster on re-deploys; same result as the UI path.

## Step 3 — Add the App to Genie Code (5 min)

**Agents → MCP Servers → + Add → Custom Databricks App** → pick `bakehouse-detective-mcp`. Test connection. You should see **4 tools, 1 resource, 1 prompt**.

![Add the App as a custom MCP server](docs/screenshots/add-app-as-mcp.png)

If "Custom Databricks App" isn't a dropdown option, fall back to **+ Add → External MCP** with `<App URL>/mcp` as the URL — same result.

## Step 4 — Use it from Genie Code (7 min)

> *"Use the bakehouse-detective server. First get the franchise list, then look at Crumbly Creations' last 14 days of revenue, then search reviews for the word 'closed' or 'wait', then write a brief and log it as a finding with hypothesis 'isolated single-day operational issue on May 8'."*

Watch:

- `franchise://list` is fetched as a *resource*, not a tool call.
- `franchise_sales_trend` runs (May 8 $6 anomaly visible).
- `search_reviews` runs.
- `compose_brief` calls back to the host's LLM via **sampling** — you'll see a nested `sampling/createMessage` request in the trace.
- `log_finding` writes a row to `workspace.default.findings`.

![Genie Code calling the deployed App](docs/screenshots/genie-code-using-custom-app.png)

Verify in the SQL Editor:

```sql
SELECT * FROM workspace.default.findings ORDER BY ts DESC LIMIT 5
```

![findings row in SQL Editor](docs/screenshots/findings-row.png)

`user_email` populated as **you** — even in SP-execution mode, the audit attribution is the calling user. The step-0 card in the demo tells you whether you got full identity passthrough or just attribution.

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
