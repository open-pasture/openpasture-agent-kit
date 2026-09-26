# Domain Model

The domain layer gives `Openpasture` a stable internal language.

## Core Entities

### Farm

The top-level management unit.

A farm contains paddocks, herds, infrastructure, and observations. It also carries important context such as timezone and the farm's primary location.

### Paddock

A bounded grazing unit within a farm.

A paddock stores geometry, area, management status, and any notes that affect movement planning.

### Herd

A livestock group managed together.

A herd tracks species, count, optional animal-unit assumptions, and current paddock assignment.

### Animal

An individual animal with durable identity and current state.

An animal tracks stable fields such as tag, species, sex, breed, herd assignment, current paddock, parentage, lifecycle status, and notes. Health checks, breeding events, treatments, movements, images, and other historical detail should be recorded as activity events instead of growing unbounded arrays on the animal row.

### Observation

A time-bound signal about the state of the farm.

The observation model is intentionally unified. A weather report, a farmer note, a photo analysis, and a satellite-derived NDVI summary should all be expressible as observations.

### FarmActivityEvent

The append-only historical source of truth for profile feeds.

Every meaningful farm fact that should later appear in a CRM-style history feed should be written as a `FarmActivityEvent`. Observations remain a useful source-specific shape, but notes, images, weather reports, movement updates, grazing decisions, daily briefs, animal health records, treatments, breeding records, lifecycle events, and imported reports should all emit activity events.

An activity event uses a stable envelope plus flexible typed payload:

- stable fields: event id, farm id, event type, source, occurred time, recorded time, title, body, summary, provenance, visibility,
- typed payload: event-specific detail such as weather readings, treatment dose, breeding outcome, or image analysis,
- targets: indexed links to every profile that should show the event: farm, pasture, paddock, herd, animal, or another land unit,
- attachments: images, reports, files, and other media associated with the event. Image attachments may include a stable thumbnail URL for feed previews.

This lets Openpasture keep a fluid model that can grow with new data sources while preserving fast profile feeds.

### GrazingDecision

The decision for one herd in one decision window.

A grazing decision records:

- the action: `STAY`, `MOVE`, or `NEEDS_INFO`,
- the decision window,
- source and destination land units, and the target boundary for a move,
- reasoning, confidence, and the uncertainty request when needed,
- the inputs it drew on: land reports, collar summary, observations, knowledge,
- the autonomy setting in force,
- the farmer's response, including any modified boundary,
- the boundary command sent,
- the outcome, evaluated on later cycles.

The full shape is in `docs/contracts.md`.

### LandReport

What Alexandria returns about a geometry: weather, imagery, climate, hazards,
soil, vegetation, species, water, and terrain, each with sources. Stored as
observations linked to the land units it covers.

### BoundaryCommand

A versioned boundary sent to a herd's collars, with exclusions and an optional
transition corridor. Active only once collars acknowledge it.

### DailyBrief

The human-readable artifact delivered to the farmer.

A brief wraps the latest grazing decision with context, key observations, and a targeted request for more information when useful.

### KnowledgeEntry

A structured lesson extracted from a trusted source.

The initial four knowledge entry types are:

- `principle`,
- `technique`,
- `signal`,
- `mistake`.

## Relationship Sketch

```mermaid
flowchart TD
    Farm --> Paddock
    Farm --> Herd
    Farm --> Animal
    Farm --> Observation
    Farm --> FarmActivityEvent
    FarmActivityEvent --> FarmActivityTarget
    Farm --> GrazingDecision
    GrazingDecision --> LandReport
    GrazingDecision --> KnowledgeEntry
    GrazingDecision --> BoundaryCommand
    DailyBrief --> GrazingDecision
```

## Design Notes

- Prefer explicit objects over weak dictionaries.
- Keep these types free of Hermes-specific logic.
- Keep room for geospatial representation without requiring a UI.
- Preserve provenance on every recommendation and knowledge record.
- Treat `FarmActivityEvent` as the historical source of truth. Current-state rows answer "what is true now"; activity events answer "what happened and why does this profile remember it?"
