# Databricks notebook source
# MAGIC %md
# MAGIC # MCP Under the Hood
# MAGIC
# MAGIC A guided walkthrough of the **Model Context Protocol** wire format. We define a tiny server in this notebook, connect a client to it in-memory, and watch the JSON-RPC calls fly. Then we add **sampling** (server calls back to the host's LLM) and **elicitation** (server asks the user a question), and finally connect to a real managed Databricks MCP endpoint to prove it's the same protocol.
# MAGIC
# MAGIC **Run All** and read the output of each cell.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 1 — Install the MCP SDK
# MAGIC
# MAGIC One Python package. It contains the server framework (`FastMCP`), a client (`ClientSession`), and the wire-protocol types.

# COMMAND ----------

# MAGIC %pip install --quiet "mcp>=1.2"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 2 — Define a tiny MCP server, in this notebook
# MAGIC
# MAGIC An MCP server is **just a collection of decorated Python functions**. Three tools, one resource, one prompt — about 30 lines of code.
# MAGIC
# MAGIC We'll call this server `bakery` and give it small, bakehouse-flavored capabilities. Don't worry about Databricks data yet — that's not the point of this section. The point is the *protocol*.

# COMMAND ----------

from mcp.server.fastmcp import Context, FastMCP

bakery = FastMCP("bakery")

@bakery.tool()
def list_products() -> list[str]:
    """List the products on the menu today."""
    return ["sourdough", "croissant", "cookie", "bagel"]

@bakery.tool()
def price(product: str) -> float:
    """Return the price of a single product. Use after list_products."""
    catalog = {"sourdough": 8.0, "croissant": 4.5, "cookie": 3.0, "bagel": 3.5}
    return catalog.get(product, -1.0)

@bakery.tool()
def total(items: list[str]) -> float:
    """Total price for a list of products."""
    return round(sum(price(it) for it in items), 2)

@bakery.resource("menu://today")
def menu() -> str:
    """A markdown menu, attachable to the host's context."""
    return "# Today's menu\n- sourdough $8\n- croissant $4.50\n- cookie $3\n- bagel $3.50"

@bakery.prompt()
def order(items: str) -> list[dict]:
    """Slash-command: /order 'sourdough, two cookies'"""
    return [{"role": "user", "content": {"type": "text", "text": f"Place an order for: {items}. Use list_products and total."}}]

print(f"Server '{bakery.name}' defined with 3 tools, 1 resource, 1 prompt.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 3 — Connect a client, list the tools (the wire becomes visible)
# MAGIC
# MAGIC A client speaks JSON-RPC to the server. We use the in-memory transport — both ends in the same Python process — so we can focus on the *messages*, not the networking.
# MAGIC
# MAGIC The first method we'll call is `tools/list`. The server returns each tool's name, description, and JSON-Schema for arguments.

# COMMAND ----------

import asyncio, json
from mcp.shared.memory import create_connected_server_and_client_session

async def list_things():
    async with create_connected_server_and_client_session(bakery._mcp_server) as client:
        # tools/list
        tools = await client.list_tools()
        print("=== tools/list ===")
        for t in tools.tools:
            print(f"  {t.name}: {t.description.strip()}")
            print(f"    schema: {json.dumps(t.inputSchema, indent=6)[6:]}")

        # resources/list
        res = await client.list_resources()
        print("\n=== resources/list ===")
        for r in res.resources:
            print(f"  {r.uri} — {r.description}")

        # prompts/list
        prompts = await client.list_prompts()
        print("\n=== prompts/list ===")
        for p in prompts.prompts:
            print(f"  {p.name} — {p.description}")

await list_things()

# COMMAND ----------

# MAGIC %md
# MAGIC **What just happened.** The client sent three JSON-RPC requests:
# MAGIC ```
# MAGIC {"jsonrpc":"2.0","id":1,"method":"tools/list"}
# MAGIC {"jsonrpc":"2.0","id":2,"method":"resources/list"}
# MAGIC {"jsonrpc":"2.0","id":3,"method":"prompts/list"}
# MAGIC ```
# MAGIC The server replied with the inventory above. **That's the whole discovery handshake.** A host like Genie Code does this on every connect.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 4 — Call a tool, read a resource, expand a prompt

# COMMAND ----------

async def use_things():
    async with create_connected_server_and_client_session(bakery._mcp_server) as client:
        # tools/call
        print("=== tools/call total(['croissant', 'cookie']) ===")
        res = await client.call_tool("total", arguments={"items": ["croissant", "cookie"]})
        print("  result:", res.content[0].text)

        # resources/read
        print("\n=== resources/read menu://today ===")
        r = await client.read_resource("menu://today")
        print(r.contents[0].text)

        # prompts/get
        print("\n=== prompts/get order(items='2 cookies') ===")
        p = await client.get_prompt("order", arguments={"items": "2 cookies"})
        print("  expanded message:", p.messages[0].content.text)

await use_things()

# COMMAND ----------

# MAGIC %md
# MAGIC **Three flavors of interaction:**
# MAGIC
# MAGIC | Method            | Who picked it       |
# MAGIC |-------------------|---------------------|
# MAGIC | `tools/call`      | The model decided   |
# MAGIC | `resources/read`  | The app / user picked the URI |
# MAGIC | `prompts/get`     | The user picked from a slash-menu |
# MAGIC
# MAGIC Same server, three different "who controls this" stories.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 5 — Sampling: the server calls back to *the host's* LLM
# MAGIC
# MAGIC Here's the magic. The server can ask "please run this on your model" — and it gets a completion back without ever having an API key.
# MAGIC
# MAGIC We define a new tool `summarize_menu` that uses sampling. The notebook plays the *host* — when the server asks "summarize this with your LLM," we call the **Databricks Foundation Model API** (already available in Free Edition).
# MAGIC
# MAGIC ### What you should see when this works
# MAGIC
# MAGIC One line of LLM-generated text describing today's menu. Something like *"Treat yourself today with our buttery croissants, fresh sourdough, chewy cookies, and chewy bagels — all baked with love!"*
# MAGIC
# MAGIC ### What might go wrong
# MAGIC
# MAGIC | Error                                              | Likely cause                                                                                          | Fix                                                                       |
# MAGIC |----------------------------------------------------|-------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------|
# MAGIC | `ResourceDoesNotExist` / `model not found`          | `MODEL_NAME` isn't on your workspace.                                                                 | Open **Machine Learning → Serving** and pick a serving endpoint that exists. |
# MAGIC | `ImportError: cannot import name 'CreateMessage...'` | `mcp` SDK version mismatch.                                                                            | The first cell pinned `mcp>=1.2`. Re-run cell 1 + restart Python.          |
# MAGIC | Auth error                                          | `WorkspaceClient()` should pick up your notebook's identity. If it doesn't, this is workspace config. | Skip this cell — cells 2–4 already proved the protocol.                   |
# MAGIC
# MAGIC If anything fails: read the error, then move on to cell 6. The protocol story is intact.

# COMMAND ----------

import os
from databricks.sdk import WorkspaceClient
from mcp.types import CreateMessageRequestParams, CreateMessageResult, TextContent

# Pick a model your workspace serves; adjust if needed.
MODEL_NAME = "databricks-meta-llama-3-3-70b-instruct"

@bakery.tool()
async def summarize_menu(ctx: Context) -> str:
    """Summarize today's menu in one cheerful sentence. Uses SAMPLING."""
    return (await ctx.session.create_message(
        messages=[{"role": "user", "content": {"type": "text", "text":
            f"In one cheerful sentence, summarize this menu: {menu()}"}}],
        max_tokens=80,
    )).content.text

# Host-side handler: when the server asks for a sample, we call Databricks FMAPI.
async def sampling_handler(context, params: CreateMessageRequestParams) -> CreateMessageResult:
    w = WorkspaceClient()
    user_text = params.messages[0].content.text
    response = w.serving_endpoints.query(
        name=MODEL_NAME,
        messages=[{"role": "user", "content": user_text}],
        max_tokens=params.maxTokens or 200,
    )
    text = response.choices[0].message.content
    return CreateMessageResult(role="assistant", content=TextContent(type="text", text=text), model=MODEL_NAME)

async def sample_demo():
    async with create_connected_server_and_client_session(
        bakery._mcp_server,
        sampling_callback=sampling_handler,
    ) as client:
        print("=== tools/call summarize_menu  (server will ask host for a completion) ===")
        result = await client.call_tool("summarize_menu", arguments={})
        print("  result:", result.content[0].text)

await sample_demo()

# COMMAND ----------

# MAGIC %md
# MAGIC **What happened on the wire:**
# MAGIC
# MAGIC ```
# MAGIC client → server:  tools/call summarize_menu
# MAGIC server → client:  sampling/createMessage  ← the callback
# MAGIC client → server:  result (LLM-generated text)
# MAGIC server → client:  result (tool's final return)
# MAGIC ```
# MAGIC
# MAGIC **Why this is the most underused feature in the spec:**
# MAGIC - Server has no model API key.
# MAGIC - Host pays for the inference.
# MAGIC - The same server works with any host's model — Claude, Llama, GPT, whatever.
# MAGIC - Secrets stay on the host side.
# MAGIC
# MAGIC In Section E we'll build a Databricks-App-hosted server that uses sampling against the calling user's workspace LLM endpoints.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 6 — Elicitation: the server asks *the user* for input
# MAGIC
# MAGIC Sometimes a tool needs a piece of information the model shouldn't guess (severity, confirmation, target environment). MCP defines `elicitation/create`: the server pauses, the host renders a UI, the user picks, the server resumes.
# MAGIC
# MAGIC In our notebook, the "user" is us — we'll respond to elicitation programmatically.

# COMMAND ----------

from mcp.types import ElicitRequestParams, ElicitResult

@bakery.tool()
async def cancel_order(ctx: Context, order_id: str) -> dict:
    """Cancel an order. Asks the user to confirm."""
    response = await ctx.elicit(
        message=f"Cancel order {order_id}? This is permanent.",
        schema={
            "type": "object",
            "properties": {"confirm": {"type": "string", "enum": ["yes", "no"]}},
            "required": ["confirm"],
        },
    )
    if response.action != "accept" or response.content.get("confirm") != "yes":
        return {"order_id": order_id, "status": "kept"}
    return {"order_id": order_id, "status": "cancelled"}

# Host-side handler: simulate a user clicking "yes."
async def elicit_handler(context, params: ElicitRequestParams) -> ElicitResult:
    print(f"  >>> server is asking user: {params.message}")
    print(f"  >>> user (us) answers: yes")
    return ElicitResult(action="accept", content={"confirm": "yes"})

async def elicit_demo():
    async with create_connected_server_and_client_session(
        bakery._mcp_server,
        elicitation_callback=elicit_handler,
    ) as client:
        print("=== tools/call cancel_order(order_id='abc-123') ===")
        result = await client.call_tool("cancel_order", arguments={"order_id": "abc-123"})
        print("  result:", result.content[0].text)

await elicit_demo()

# COMMAND ----------

# MAGIC %md
# MAGIC **Why this matters:** without elicitation, your tool either (a) fails when the model lacks an argument or (b) hallucinates one. Elicitation makes "ask the user" a first-class part of the protocol. Hosts render real UI for it.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 7 — Connect to a *real* managed Databricks MCP endpoint
# MAGIC
# MAGIC Same client code, different transport. We point at the workspace's managed MCP endpoint — the one Genie Code and Playground use behind the scenes — over **Streamable HTTP** with workspace OAuth.
# MAGIC
# MAGIC ### Heads up — this cell is the most likely to fail
# MAGIC
# MAGIC The managed MCP endpoint URL pattern (`/api/2.0/mcp/<server-kind>`) is documented but evolves. The cell is wrapped in a try/except so a failure here doesn't crash the notebook.
# MAGIC
# MAGIC ### What you should see when this works
# MAGIC
# MAGIC A list of up to 5 tool names from the managed Genie MCP server, like `genie__01f1...__query` (one per Genie Space you can read). The point: the *exact same client code* from cells 3–4 talks to a real Databricks-hosted MCP endpoint.
# MAGIC
# MAGIC ### What might go wrong
# MAGIC
# MAGIC | Error                              | Why                                                              | What to do                                                |
# MAGIC |------------------------------------|------------------------------------------------------------------|-----------------------------------------------------------|
# MAGIC | `404 Not Found`                     | Endpoint path differs on your workspace.                         | Skip this cell. Cells 2–6 already proved the protocol.    |
# MAGIC | `401 / 403`                         | Token from `WorkspaceClient` doesn't have MCP audience.          | Skip this cell. Try calling the same MCP from Genie Code (Section A) instead. |
# MAGIC | `streamablehttp_client` import fails | `mcp` SDK version mismatch.                                      | Re-run cell 1 + restart Python.                            |
# MAGIC
# MAGIC **The "right" answer if this errors: shrug, move on.** Cells 2–6 are the load-bearing ones for the workshop.

# COMMAND ----------

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
host = w.config.host                                                # e.g. https://dbc-xxxx.cloud.databricks.com
token = w.config.authenticate().get("Authorization", "").split()[-1]  # bearer token for current identity

managed_mcp_url = f"{host}/api/2.0/mcp/genie"                       # managed Genie Spaces MCP

async def list_managed():
    try:
        async with streamablehttp_client(
            managed_mcp_url,
            headers={"Authorization": f"Bearer {token}"},
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                print(f"=== {managed_mcp_url} ===")
                for t in tools.tools[:5]:
                    print(f"  {t.name}: {(t.description or '')[:80].strip()}")
                if len(tools.tools) > 5:
                    print(f"  ... and {len(tools.tools)-5} more")
    except Exception as e:
        print(f"Could not connect to managed endpoint: {type(e).__name__}: {e}")
        print("That's OK — the in-memory cells above still demonstrated the protocol fully.")

await list_managed()

# COMMAND ----------

# MAGIC %md
# MAGIC **The whole point.** Whether the server is:
# MAGIC - 30 lines of Python in this notebook,
# MAGIC - a managed Databricks endpoint behind OAuth,
# MAGIC - or a custom Databricks App you'll build in Section E —
# MAGIC
# MAGIC the *client code is identical*. That is MCP.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Recap
# MAGIC
# MAGIC You just spoke MCP three times:
# MAGIC 1. To a tiny in-process server (cells 2–4)
# MAGIC 2. With sampling and elicitation (cells 5–6)
# MAGIC 3. To a real managed Databricks endpoint (cell 7)
# MAGIC
# MAGIC **Next:** open `05-custom-app/README.md` and ship your own MCP server as a Databricks App.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Modify and re-run (optional)
# MAGIC
# MAGIC - **Cell 2:** add a fourth tool, `discount(product: str, percent: float)`. Re-run cells 2–4 to see it appear in the inventory.
# MAGIC - **Cell 5:** change the prompt template inside `summarize_menu` to ask for *grumpy* instead of *cheerful*. Re-run to see the model behave.
# MAGIC - **Cell 6:** change the schema's `enum` to `["yes", "no", "maybe"]` and have `elicit_handler` answer `"maybe"`. Watch the tool branch.
