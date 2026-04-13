---
name: pipeline-spypoint
description: Collect recurring farm observations from SPYPOINT using an authenticated Firecrawl profile and the learned site navigation.
version: 1.0.0
---
# Pipeline SPYPOINT

## Login

- Login URL: `https://webapp.spypoint.com/`
- Expected authentication flow: `Use the authenticated SPYPOINT web app session and Shared with me.`

## Navigation

- Open Shared with me.
- Choose WSN SL research plot (Matthew).
- Inspect the daily gallery and prefer the clearest image with the measuring stick visible.
- Use the 10:00 AM-style daylight frame when it is the clearest daily reference.

## Extraction Prompts

- `From the Shared with me gallery for WSN SL research plot, identify the single best daily grass-height image. Prefer the photo where the measuring stick or reference stake is clearest and the grass canopy is easiest to compare against it. Return JSON with the chosen photo URL, capture time, visible measuring-stick notes, and a short grass-height summary.`

## Output Shape

- Return JSON with photo_url, captured_at, measuring_stick_visible, grass_height_summary, and confidence.

## Collection Goal

- Collect the single best daily photo that shows grass height against the measuring stick in the WSN SL research plot.

## Gotchas

- Signed image URLs can expire quickly; prefer the SPYPOINT photo preview URL from the authenticated page.
- Night IR frames are usable but daylight frames around 10:00 AM are clearer for grass-height comparison.
