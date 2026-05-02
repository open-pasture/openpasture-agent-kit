# ChatGPT Farm Onboarding App

This document keeps the ChatGPT app submission material close to the canonical
OpenPasture agent behavior. The app is intentionally narrow: it helps a farmer
set up the first farm, herd, paddocks, current paddock, and optional starting
field notes.

## App Listing Draft

- App name: OpenPasture Farm Onboarding
- Short description: Set up an OpenPasture farm record from a ChatGPT
  conversation, then show a clear onboarding summary.
- Support contact: hello@openpasture.com
- Privacy policy URL: https://openpasture.com/privacy
- Intended first distribution: private ChatGPT Developer Mode, then public
  Apps Directory review after OAuth or mixed authentication is ready.

## Tool Surface

The public ChatGPT app should expose only the onboarding-specific tools from
`openpasture.connectors.mcp_chatgpt_app`:

- `get_onboarding_status`: read-only check of which setup details are present
  or missing.
- `save_farm_onboarding`: writes the first farm, first herd, paddocks, and
  current paddock after the farmer provides enough detail. It can accept
  ChatGPT-extracted map context as structured `location` GeoJSON or as
  `location_hint` notes when coordinates are uncertain.
- `record_starting_observation`: writes one farmer-provided field note during
  onboarding.
- `render_onboarding_summary`: read-only render tool that attaches
  `ui://openpasture/onboarding-summary-v2.html` through the MCP Apps standard
  `_meta.ui.resourceUri`, with `_meta["openai/outputTemplate"]` included as a
  ChatGPT compatibility alias.

The general MCP tools `list_openpasture_tools` and `run_openpasture_tool` should
remain available for self-hosted and power-user clients, but they are too broad
for the first public ChatGPT app submission.

## Review Test Prompts

Use these prompts during Developer Mode testing and as starting submission test
cases:

1. "Use the OpenPasture farm onboarding app. Help me set up Willow Creek in
   America/Chicago with 28 cattle in Home paddock. I also have North and South
   paddocks."
2. "Check what setup details are still missing before saving anything."
3. "Record this starting field note: Home paddock has knee-high grass and the
   herd is calm."
4. Upload a Google Maps screenshot with a dropped pin and visible coordinates,
   then say: "Use this map pin as the farm location. The farm is Pinned
   Pastures in America/Chicago with 18 cattle in Home paddock."
5. "Show the onboarding summary widget."

Expected behavior:

- ChatGPT asks for the smallest missing detail instead of guessing.
- When a map screenshot includes visible GPS coordinates, ChatGPT extracts them
  and passes a structured GeoJSON `location` point to `save_farm_onboarding`.
- When coordinates are unclear, ChatGPT asks the farmer to confirm them or saves
  only a plain `location_hint` rather than inventing precision.
- Write tools are called only after the farmer provides the relevant details.
- The render tool is called after data tools and the iframe summary shows farm,
  herd, paddock, current-paddock, and observation counts.
- Tool responses do not include API keys, debug logs, trace IDs, raw chat
  transcripts, or unrelated personal data.

## MCP Apps Compatibility

The onboarding summary widget should lead with the MCP Apps standard so it can
run in ChatGPT and other compatible hosts:

- Keep the source component in `apps/chatgpt-onboarding/web/`.
- Serve the packaged iframe asset from
  `src/openpasture/connectors/assets/onboarding-summary.html`.
- Declare the component on `render_onboarding_summary` with
  `_meta.ui.resourceUri`.
- Listen for `ui/initialize`, `ui/notifications/tool-input`, and
  `ui/notifications/tool-result` over JSON-RPC 2.0 `postMessage`.
- Use `tools/call` for UI-initiated tool refreshes.
- Use `ui/message` for the "Ask this in chat" action.
- Treat `window.openai` as an optional ChatGPT compatibility layer only, with
  feature detection and graceful fallback.

## Annotation Justification

- `get_onboarding_status`: `readOnlyHint=true`, `destructiveHint=false`,
  `openWorldHint=false`; it only reads private tenant farm state.
- `save_farm_onboarding`: `readOnlyHint=false`, `destructiveHint=false`,
  `openWorldHint=false`; it creates private tenant farm records and should be
  confirmed by the user, but it does not affect the public internet.
- `record_starting_observation`: `readOnlyHint=false`,
  `destructiveHint=false`, `openWorldHint=false`; it writes a private field note
  the farmer explicitly provides.
- `render_onboarding_summary`: `readOnlyHint=true`, `destructiveHint=false`,
  `openWorldHint=false`; it renders structured data already returned by the app.

## Pre-Submission Checklist

- Host the MCP server on a public HTTPS domain.
- Replace private API-key-in-path testing with an OpenAI-supported public auth
  path, such as OAuth or mixed authentication.
- Verify organization identity in the OpenAI Platform Dashboard.
- Confirm the privacy policy is live and matches returned data fields.
- Capture screenshots of the onboarding summary widget in ChatGPT web and
  mobile.
- Test all review prompts in Developer Mode and save expected responses.
- Confirm the Content Security Policy allows only required widget and API
  domains.
