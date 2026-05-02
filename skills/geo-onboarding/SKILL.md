---
name: geo-onboarding
description: Turn farmer-provided map clues into draft farm, pasture, paddock, and section GeoJSON.
version: 1.0.0
---
# Geo Onboarding

## When To Use

Use this skill when a farmer provides a map screenshot, dropped pin, survey report, address, parcel clue, or hand-drawn boundary and wants OpenPasture to show their farm on a GIS map.

OpenPasture is the toolkit and storage layer. The agent is responsible for reading the image or document, extracting the visible clues, and calling OpenPasture tools with structured geospatial data.

## Procedure

1. Identify the farm name, timezone, and any known herd or paddock context if this is part of first-run onboarding.
2. Read visible center coordinates from the screenshot or document. Convert them to GeoJSON order: `[longitude, latitude]`.
3. Treat farmer-drawn boxes, outlines, highlighted fields, or survey sketches as approximate land-unit hints.
4. Create one draft farm boundary that covers the intended operation.
5. Create durable `pasture` land units for the visible fields or pastures inside the farm.
6. Create `paddock` or `section` land units only when the farmer or screenshot clearly indicates subdivisions.
7. Set `provenance.source` to `map_screenshot`, `survey`, `address`, `farmer_description`, or the best matching source.
8. Set confidence below `1.0` for agent-generated geometry. For screenshot-only boundaries, prefer low-to-moderate confidence.
9. Preserve uncertainty in `warnings`; do not claim legal, survey-grade, or parcel-accurate boundaries.
10. Call `save_geo_onboarding_draft` for a full draft or `upsert_land_unit` for one follow-up edit.
11. Return the map confirmation link from the tool so the farmer can review and edit the boundary.

## Screenshot Guidance

For a Google Maps screenshot with a dropped pin and loose boxes:

- Use the visible dropped-pin coordinates as the farm `location`.
- Estimate the loose boxes as approximate polygons around the highlighted farm and pasture areas.
- If scale is uncertain, make the polygons conservative and add a warning.
- If the image includes multiple red boxes, create separate pasture land units for each box and a farm boundary that covers the combined intended farm area.
- Do not invent exact corners behind trees, rivers, labels, or UI overlays. Store the draft and send the farmer to the map editor.

## Tool Payload Shape

Prefer this shape for `save_geo_onboarding_draft`:

```json
{
  "name": "Duck River Farm",
  "timezone": "America/Chicago",
  "location": { "type": "Point", "coordinates": [-87.038675, 35.642109] },
  "boundary": {
    "type": "Polygon",
    "coordinates": [[
      [-87.043, 35.646],
      [-87.034, 35.646],
      [-87.034, 35.639],
      [-87.043, 35.639],
      [-87.043, 35.646]
    ]]
  },
  "source": "map_screenshot",
  "confidence": 0.55,
  "evidence": ["Google Maps screenshot with dropped pin and farmer-drawn boxes"],
  "pastures": [
    {
      "id": "pasture_west",
      "name": "West boxed pasture",
      "geometry": { "type": "Polygon", "coordinates": [[[-87.042, 35.646], [-87.038, 35.646], [-87.038, 35.640], [-87.042, 35.640], [-87.042, 35.646]]] },
      "confidence": 0.5,
      "warnings": ["Estimated from screenshot box; farmer should confirm corners."]
    }
  ]
}
```

## Success Criteria

The farmer receives a map link with the farm and pastures rendered as editable drafts. The stored geometry is good enough for visual confirmation, future NDVI/pasture analysis, and follow-up editing, but it remains clearly marked as approximate until confirmed.
