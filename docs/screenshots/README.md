# Screenshot checklist

The main `README.md` references the images below. Drop PNG files in this folder using these exact names. Until then, GitHub will render broken-image icons — that's expected.

Aim for ~600px wide. Crop tightly — show one UI element per shot.

| Filename                         | What it shows                                                                                | Section |
|----------------------------------|----------------------------------------------------------------------------------------------|---------|
| `agents-mcp-servers-panel.png`   | Workspace **Agents → MCP Servers** panel listing UC Functions, Vector Search, Genie Spaces.   | A       |
| `genie-code-sidebar.png`         | A notebook with **Genie Code** open in the right sidebar.                                     | A       |
| `genie-code-trace.png`           | A Genie Code response with a tool-call trace expanded.                                        | A       |
| `playground-tools-add.png`       | AI Playground **Tools → + Add tool → MCP Servers** dropdown.                                  | B       |
| `playground-trace.png`           | Playground showing a `tools/call` JSON trace with arguments + result.                          | B       |
| `add-external-mcp-dialog.png`    | The **+ Add → External MCP** dialog (empty form).                                             | C       |
| `external-mcp-form-filled.png`   | Same dialog, filled in for `you-search` (URL + Bearer header). Redact your real key.           | C       |
| `external-mcp-connected.png`     | The MCP Servers panel showing `you-search` Connected, with a tool count.                       | C       |
| `you-search-trace.png`           | Genie Code trace showing the `you-search` tool being called from a prompt.                    | C       |
| `notebook-cell5-sampling.png`    | Section D notebook with cell 5 (sampling) executed, output visible.                            | D       |
| `apps-create.png`                | **Compute → Apps → Create app** screen.                                                        | E       |
| `apps-config-form.png`           | The App config form with `app/` selected as source path and the warehouse resource bound.      | E       |
| `apps-running.png`               | The deployed App in `RUNNING` state, with its URL.                                             | E       |
| `add-app-as-mcp.png`             | **Agents → MCP Servers → + Add → Custom Databricks App** picker showing `bakehouse-detective-mcp`. | E       |
| `genie-code-using-custom-app.png`| Genie Code calling `compose_brief` from the deployed App, with the trace visible.              | E       |
| `findings-row.png`               | SQL Editor showing `SELECT * FROM workspace.default.findings` with one row.                    | E       |

## Why placeholders

Without these images, the workshop's UI-driven sections require attendees to hunt through unfamiliar menus. Less-technical learners get lost. Even quick phone-camera screenshots of your own workspace beat nothing.

## Sequence

If you only have time for a subset, ship in this order:
1. `agents-mcp-servers-panel.png` (Section A's anchor — most important)
2. `apps-create.png` + `apps-config-form.png` (Section E's anchor)
3. `add-external-mcp-dialog.png` + `external-mcp-form-filled.png` (Section C is purely visual)
4. The rest fill in over time.
