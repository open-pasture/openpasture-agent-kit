# Contracts

The engine depends on three formats: the **land report** it gets from
Alexandria, the **boundary command** it sends to collars, and the **grazing
decision** that ties them together in the decision record.

Geometry is always GeoJSON in `[longitude, latitude]` order (WGS 84). Times are
ISO 8601 with a timezone offset. Every externally sourced value carries
provenance.

## Land Report

A request for what is known about a place. The caller passes a geometry and
asks for the sections it needs. Anything not requested is not fetched.

### Request

```json
{
  "geometry": { "type": "Polygon", "coordinates": [[[-92.41, 38.12], [-92.40, 38.12], [-92.40, 38.13], [-92.41, 38.13], [-92.41, 38.12]]] },
  "buffer_meters": 2000,
  "as_of": "2026-09-25T06:00:00-05:00",
  "sections": {
    "weather": { "history_days": 90, "forecast_days": 10 },
    "imagery": { "latest": true, "history_days": 365, "products": ["rgb", "ndvi"] },
    "climate": { "history_years": 30, "include": ["drought", "precipitation_normals", "temperature_normals"] },
    "hazards": { "history_years": 30, "include": ["flood", "fire", "severe_weather"] },
    "soil": {},
    "vegetation": { "include": ["native", "invasive", "toxic_to_livestock"] },
    "species": { "include": ["wildlife", "pests", "pollinators"] },
    "water": { "include": ["surface_water", "wetlands", "floodplain"] },
    "terrain": { "include": ["elevation", "slope", "aspect"] }
  }
}
```

A `Point` geometry is also valid. The report then covers the buffer around it.

### Response

Each requested section comes back with its data and its sources. Sections that
could not be filled return `status: "unavailable"` with a reason, never silent
omission.

```json
{
  "report_id": "lr_01J8...",
  "geometry": { "type": "Polygon", "coordinates": ["..."] },
  "as_of": "2026-09-25T06:00:00-05:00",
  "sections": {
    "weather": {
      "status": "ok",
      "current": { "air_temp_c": 14.2, "precip_mm_24h": 0.0, "wind_kph": 11, "relative_humidity": 0.71 },
      "history": [{ "date": "2026-09-24", "precip_mm": 3.1, "temp_max_c": 27.0, "temp_min_c": 12.4, "et0_mm": 3.8 }],
      "forecast": [{ "date": "2026-09-26", "precip_mm": 12.0, "precip_probability": 0.8, "temp_max_c": 22.0, "temp_min_c": 11.0 }],
      "sources": [{ "provider": "...", "retrieved_at": "2026-09-25T05:58:12Z", "resolution": "1 km", "license": "..." }]
    },
    "imagery": {
      "status": "ok",
      "latest": { "captured_at": "2026-09-23T16:41:00Z", "cloud_cover": 0.03, "resolution_meters": 3.0, "assets": { "rgb": "https://...", "ndvi": "https://..." } },
      "ndvi_stats": { "mean": 0.62, "p10": 0.48, "p90": 0.74 },
      "history": [{ "captured_at": "2026-09-08T16:39:00Z", "ndvi_mean": 0.55 }],
      "sources": ["..."]
    },
    "soil": { "status": "unavailable", "reason": "No survey coverage for this area." }
  }
}
```

The land connector stores each `ok` section as an `Observation` linked to the
land units the geometry covers, keeping `report_id` and `sources` as provenance.
Observations carry compact metrics; the full section data stays on the stored
report. Unavailable sections are kept on the report only.

## Boundary Command

What the engine sends to a herd's collars. Fence logic runs on the collar, so
the command carries the full geometry the collar enforces.

```json
{
  "command_id": "bc_01J8...",
  "decision_id": "gd_01J8...",
  "farm_id": "farm_willow_creek",
  "herd_id": "herd_1",
  "collar_ids": ["oc_0012", "oc_0013"],
  "version": 42,
  "effective_at": "2026-09-25T07:30:00-05:00",
  "boundary": { "type": "Polygon", "coordinates": ["..."] },
  "exclusions": [{ "type": "Polygon", "coordinates": ["..."] }],
  "transition": {
    "type": "open_then_close",
    "corridor": { "type": "Polygon", "coordinates": ["..."] },
    "close_after_minutes": 90
  }
}
```

- `version` increases with every command for the herd. A collar ignores any
  command older than the one it holds.
- `exclusions` are areas inside the boundary the herd must stay out of, such
  as a pond edge, a creek bank, or a road.
- `transition` moves the herd without cueing animals that are walking the
  right way. With `open_then_close`, the collar allows old paddock, corridor,
  and new paddock together, then closes to the new boundary after the set time.
  `immediate` skips the transition.

### Acknowledgement

Each collar reports back. A boundary is active for the herd only once enough
collars confirm it. Any collar that does not confirm is surfaced to the farmer.

```json
{
  "command_id": "bc_01J8...",
  "collar_id": "oc_0012",
  "version": 42,
  "status": "applied",
  "received_at": "2026-09-25T07:30:04-05:00"
}
```

`status` is one of `received`, `applied`, or `rejected` (with a `reason`).
Only `applied` counts toward activation. `received` means the collar has
staged it for `effective_at`.

The collar wire format in `opencollar/protocol/README.md` is simpler than this
command: one ring, no exclusions, no transitions. The collar connector
translates. An `open_then_close` transition goes out as two versions (old
paddock, corridor, and new paddock together, then the new paddock alone), and
exclusions are cut out of the ring. An exclusion that would leave a hole or
split the paddock is refused with a reason.

The stored command also records `final_version`, `status`,
`activation_threshold`, `land_unit_id`, `sent_at`, `activated_at`, `gateway`,
and `error`.

### Position Report

What collars send between commands. The collar connector stores raw fixes for a
retention window and rolls them into summaries per herd and land unit.

```json
{
  "collar_id": "oc_0012",
  "fixes": [{ "at": "2026-09-25T05:40:00-05:00", "point": [-92.4051, 38.1244], "accuracy_meters": 1.8, "activity": "grazing" }],
  "cues": [{ "at": "2026-09-25T05:12:00-05:00", "type": "audio", "point": [-92.4040, 38.1250] }],
  "battery": 0.81
}
```

## Grazing Decision

The record of one decision for one herd in one decision window. It grows as the
decision moves through its lifecycle.

```json
{
  "decision_id": "gd_01J8...",
  "farm_id": "farm_willow_creek",
  "herd_id": "herd_1",
  "window": { "starts_at": "2026-09-25T06:00:00-05:00", "ends_at": "2026-09-26T06:00:00-05:00" },
  "action": "MOVE",
  "from_land_unit_id": "paddock_home_3",
  "to_land_unit_id": "paddock_home_4",
  "to_boundary": { "type": "Polygon", "coordinates": ["..."] },
  "reasoning": [
    "Paddock 3 is at roughly 4 inches of residual by collar pressure and imagery.",
    "Paddock 4 has rested 38 days and imagery shows full recovery.",
    "12 mm of rain is expected tomorrow. Moving today keeps the herd off wet ground on the low side of 3."
  ],
  "confidence": "high",
  "uncertainty_request": null,
  "inputs": {
    "land_report_ids": ["lr_01J8..."],
    "collar_summary_id": "cs_01J8...",
    "observation_ids": ["obs_..."],
    "knowledge_entry_ids": ["ke_greg_judy_residual"]
  },
  "autonomy": "propose",
  "status": "evaluated",
  "farmer_response": {
    "at": "2026-09-25T06:48:00-05:00",
    "response": "modified",
    "note": "Shift the west line in 20 yards, the wet spot is bigger than it looks.",
    "boundary": { "type": "Polygon", "coordinates": ["..."] }
  },
  "boundary_command_id": "bc_01J8...",
  "outcome": {
    "evaluated_at": "2026-10-02T06:00:00-05:00",
    "herd_held_boundary": true,
    "cue_count": 3,
    "residual_estimate_inches": 4.5,
    "notes": ["Paddock 3 NDVI back to 0.58 after 7 days."]
  }
}
```

- `action` is `STAY`, `MOVE`, or `NEEDS_INFO`. Only `MOVE` carries a target.
  `NEEDS_INFO` must carry an `uncertainty_request`.
- `autonomy` is the setting in force when the decision was made: `propose`,
  `apply_unless_stopped`, or `apply`.
- `status` moves through `proposed` → `approved` | `modified` | `rejected` →
  `sent` → `active` → `evaluated`. A `STAY` or `NEEDS_INFO` decision skips the
  send steps.
- When the farmer modifies a decision, the farmer's boundary is the one sent,
  and the engine's original stays on the record.
- `outcome` is filled in on later cycles. It is how the engine learns what its
  decisions did.
- The stored record also carries `decided_by` (agent or fallback advisor),
  `send_after` (when an `apply_unless_stopped` move goes out),
  `boundary_options`, `created_at`, and `updated_at`. A farmer can modify with
  `farmer_response.land_unit_id` instead of a drawn boundary.
- `respond_to_decision` takes `approve`, `modify`, or `reject`. The record
  stores `approved`, `modified`, or `rejected`.
