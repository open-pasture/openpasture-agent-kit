# ChatGPT Onboarding Web Component

This is the source component for the OpenPasture ChatGPT farm onboarding app.
It is plain HTML and JavaScript so the MCP server can inline a single iframe
asset without adding a frontend build step.

The packaged copy served by the MCP connector lives at:

`src/openpasture/connectors/assets/onboarding-summary.html`

Keep the component portable by using the MCP Apps standard bridge first:

- `ui/initialize`
- `ui/notifications/tool-input`
- `ui/notifications/tool-result`
- `tools/call`
- `ui/message`

Only use `window.openai` as a feature-detected ChatGPT compatibility fallback.
