"""
Bakehouse Detective — the workshop's all-in-one App.

This single Databricks App serves four things:
  - GET /            -> a small landing page (static/index.html)
  - GET /lecture     -> the Hour 1 reveal.js deck (static/lecture.html)
  - GET /demo        -> a live investigation UI (static/demo.html)
  - GET /demo/investigate?franchise=X  -> SSE stream that runs the investigation
                                          step-by-step and emits each MCP tool
                                          call as it happens
  - POST/GET /mcp    -> the FastMCP Streamable HTTP endpoint
  - GET /healthz     -> health check

The MCP tools (`franchise_sales_trend`, `search_reviews`, `compose_brief`,
`log_finding`) plus a resource (`franchise://list`) and a prompt
(`/diagnose_franchise`) are exposed both via /mcp (for Genie Code / Playground)
and via the /demo SSE flow (for the live demo with no MCP host needed).

Identity passthrough: every Databricks call runs as the *calling user* via the
`X-Forwarded-Access-Token` header that the Apps platform injects.
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, AsyncIterator

from databricks import sql
from databricks.sdk import WorkspaceClient
from databricks.sdk.config import Config
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse
from mcp.server.fastmcp import Context, FastMCP

STATIC_DIR = Path(__file__).parent / "static"

# --- Identity passthrough ----------------------------------------------------

_user_token: ContextVar[str] = ContextVar("user_token", default="")
_user_email: ContextVar[str] = ContextVar("user_email", default="unknown")

HOST = os.environ["DATABRICKS_HOST"]
WAREHOUSE_ID = os.environ["DATABRICKS_WAREHOUSE_ID"]
CATALOG = os.environ.get("WORKSHOP_CATALOG", "workspace")
SCHEMA = os.environ.get("WORKSHOP_SCHEMA", "default")
FINDINGS_TABLE = f"{CATALOG}.{SCHEMA}.findings"

mcp = FastMCP("bakehouse-detective")


def _connect():
    """Connect as the calling user — UC enforces ACLs as that user."""
    token = _user_token.get()
    if not token:
        # Without identity passthrough we'd OAuth-loop; fail fast and clearly.
        # The Apps platform sets X-Forwarded-Access-Token only for users who
        # reach the App through an authenticated workspace session (Genie Code,
        # Playground, in-workspace browser). External clients won't have this.
        raise RuntimeError(
            "No X-Forwarded-Access-Token on this request. This server expects "
            "identity passthrough — call it from Genie Code or AI Playground "
            "inside the workspace, not directly via curl."
        )
    return sql.connect(
        server_hostname=HOST.replace("https://", ""),
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        access_token=token,
    )


def _query(sql_text: str, params: tuple = ()) -> list[dict[str, Any]]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql_text, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def _exec(sql_text: str, params: tuple = ()) -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql_text, params)


# --- Tools -------------------------------------------------------------------

@mcp.tool()
def franchise_sales_trend(franchise: str, days: int = 14) -> list[dict[str, Any]]:
    """
    Daily revenue for a named bakehouse franchise, anchored to the dataset's
    most recent date (`samples.bakehouse` covers May 2024). Use to confirm a
    slump or find an anomaly day.
    """
    return _query(
        """
        WITH bounds AS (SELECT max(dateTime) AS maxd FROM samples.bakehouse.sales_transactions)
        SELECT date(t.dateTime) AS day, ROUND(SUM(t.totalPrice), 2) AS revenue
        FROM samples.bakehouse.sales_transactions t
        JOIN samples.bakehouse.sales_franchises f ON t.franchiseID = f.franchiseID
        CROSS JOIN bounds
        WHERE f.name = ?
          AND t.dateTime >= dateadd(day, -?, bounds.maxd)
        GROUP BY day
        ORDER BY day
        """,
        (franchise, int(days)),
    )


@mcp.tool()
def search_reviews(query_substring: str, limit: int = 5) -> list[dict[str, Any]]:
    """
    Find customer reviews mentioning a keyword. Use after a sales anomaly to
    look for qualitative explanations.
    """
    return _query(
        """
        SELECT review, franchiseID, review_date
        FROM samples.bakehouse.media_customer_reviews
        WHERE LOWER(review) LIKE LOWER(?)
        LIMIT ?
        """,
        (f"%{query_substring}%", int(limit)),
    )


@mcp.tool()
async def compose_brief(ctx: Context, franchise: str) -> str:
    """
    Compose a one-paragraph diagnostic brief for a franchise. Uses SAMPLING:
    pulls trend + reviews, then asks the host's LLM to write the brief. No
    model API key on the server.
    """
    trend = franchise_sales_trend(franchise, days=14)
    reviews = search_reviews(franchise.split()[0], limit=3)
    payload = (
        f"Franchise: {franchise}\n"
        f"Recent daily revenue: {trend}\n"
        f"Related reviews: {reviews}\n\n"
        "Write ONE paragraph diagnosing what's wrong, leading with the most "
        "likely hypothesis and citing specific evidence."
    )
    result = await ctx.session.create_message(
        messages=[{"role": "user", "content": {"type": "text", "text": payload}}],
        max_tokens=400,
    )
    return result.content.text  # type: ignore[union-attr]


@mcp.tool()
def log_finding(franchise: str, hypothesis: str, evidence: str) -> dict[str, Any]:
    """
    Persist an investigator's conclusion to a Delta table for later review.
    Idempotent table create; one row per call.
    """
    _exec(
        f"""
        CREATE TABLE IF NOT EXISTS {FINDINGS_TABLE} (
          ts TIMESTAMP, user_email STRING, franchise STRING,
          hypothesis STRING, evidence STRING
        ) USING DELTA
        """
    )
    _exec(
        f"INSERT INTO {FINDINGS_TABLE} VALUES (current_timestamp(), ?, ?, ?, ?)",
        (_user_email.get(), franchise, hypothesis, evidence),
    )
    return {"status": "logged", "table": FINDINGS_TABLE, "user": _user_email.get()}


# --- Resource ----------------------------------------------------------------

@mcp.resource("franchise://list")
def franchise_index() -> str:
    """Markdown index of franchises, for the host's resource picker."""
    rows = _query(
        "SELECT name, city, country FROM samples.bakehouse.sales_franchises ORDER BY country, city"
    )
    return "\n".join(
        ["# Bakehouse Franchises", ""]
        + [f"- `{r['name']}` — {r['city']}, {r['country']}" for r in rows]
    )


# --- Prompt ------------------------------------------------------------------

@mcp.prompt()
def diagnose_franchise(franchise: str) -> list[dict[str, Any]]:
    """Slash-command: /diagnose_franchise 'Crumbly Creations'"""
    return [{
        "role": "user",
        "content": {
            "type": "text",
            "text": (
                f"Diagnose `{franchise}`:\n"
                f"1. `franchise_sales_trend` for the last 14 days.\n"
                f"2. `search_reviews` for related qualitative signals.\n"
                f"3. `compose_brief` for a writeup.\n"
                f"4. `log_finding` once you settle on a hypothesis.\n"
            ),
        },
    }]


# --- HTTP app with identity-passthrough middleware ---------------------------
#
# When mounting FastMCP under a parent FastAPI app, the streamable-HTTP session
# manager's lifespan must be propagated — otherwise /mcp returns 500.

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def capture_user(request: Request, call_next):
    """Pull the forwarded user identity from the App platform headers."""
    token = request.headers.get("x-forwarded-access-token")
    email = request.headers.get("x-forwarded-email", "unknown")
    if token:
        _user_token.set(token)
        _user_email.set(email)
    return await call_next(request)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


# --- Static pages: landing, lecture, demo -----------------------------------

@app.get("/", include_in_schema=False)
def landing() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/lecture", include_in_schema=False)
def lecture() -> FileResponse:
    return FileResponse(STATIC_DIR / "lecture.html")


@app.get("/demo", include_in_schema=False)
def demo() -> FileResponse:
    return FileResponse(STATIC_DIR / "demo.html")


# --- SSE investigation endpoint for the demo page ---------------------------
#
# Same tools as the MCP server, but called server-side so we can stream each
# step to the browser without an MCP host (Genie Code / Playground) being
# involved. This makes the demo work even on workspaces where Genie Code's
# MCP UI isn't available yet.

def _sse(event: str, data: Any) -> str:
    # default=str so dates/datetimes/decimals from SQL serialize cleanly.
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _compose_brief_via_fmapi(franchise: str, trend: list[dict], reviews: list[dict]) -> str:
    """
    Same shape as the MCP `compose_brief` tool, but calls Foundation Model APIs
    directly instead of using sampling — needed because the demo runs server-
    side without an MCP host.
    """
    # auth_type="pat" disables auto-detection of the App's service-principal
    # OAuth env vars; we want this call to run as the *forwarded user*.
    w = WorkspaceClient(config=Config(host=HOST, token=_user_token.get(), auth_type="pat"))
    payload = (
        f"Franchise: {franchise}\n"
        f"Recent daily revenue: {trend}\n"
        f"Related reviews: {reviews}\n\n"
        "Write ONE paragraph diagnosing what's wrong, leading with the most "
        "likely hypothesis and citing specific evidence."
    )
    response = w.serving_endpoints.query(
        name=os.environ.get("WORKSHOP_LLM", "databricks-meta-llama-3-3-70b-instruct"),
        messages=[ChatMessage(role=ChatMessageRole.USER, content=payload)],
        max_tokens=400,
    )
    return response.choices[0].message.content


async def _investigate_stream(franchise: str) -> AsyncIterator[str]:
    """Run the full investigation; yield SSE events as each step finishes."""
    try:
        # Step 1 — sales trend
        trend = franchise_sales_trend(franchise, days=14)
        yield _sse("step", {
            "n": 1, "name": "franchise_sales_trend", "kind": "tools/call (SQL)",
            "args": {"franchise": franchise, "days": 14},
            "result": trend,
        })
        await asyncio.sleep(0.1)

        # Step 2 — reviews
        keyword = franchise.split()[0]
        reviews = search_reviews(keyword, limit=3)
        yield _sse("step", {
            "n": 2, "name": "search_reviews", "kind": "tools/call (SQL)",
            "args": {"query_substring": keyword, "limit": 3},
            "result": reviews,
        })
        await asyncio.sleep(0.1)

        # Step 3 — brief via Foundation Model APIs (sampling-equivalent)
        brief = _compose_brief_via_fmapi(franchise, trend, reviews)
        yield _sse("step", {
            "n": 3, "name": "compose_brief", "kind": "tools/call (sampling → FMAPI)",
            "args": {"franchise": franchise},
            "result": brief,
        })
        await asyncio.sleep(0.1)

        # Step 4 — log finding
        finding = log_finding(
            franchise,
            hypothesis="isolated single-day operational anomaly",
            evidence=brief[:500],
        )
        yield _sse("step", {
            "n": 4, "name": "log_finding", "kind": "tools/call (Delta write)",
            "args": {"franchise": franchise, "hypothesis": "...", "evidence": "..."},
            "result": finding,
        })

        # Done
        yield _sse("done", {
            "brief": brief,
            "logged_to": FINDINGS_TABLE,
            "logged_user": _user_email.get(),
        })
    except Exception as e:
        yield _sse("error", str(e))


@app.get("/demo/investigate")
async def demo_investigate(franchise: str) -> StreamingResponse:
    return StreamingResponse(
        _investigate_stream(franchise),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Mount LAST so explicit routes aren't shadowed.
app.mount("/", mcp.streamable_http_app())
