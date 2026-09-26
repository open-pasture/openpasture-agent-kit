# Vision

## Founding Principle

Every human deserves to eat animals raised on pasture. Every animal deserves to
live on grass. Openpasture exists to scale humanity's access to pasture-based
livestock by building tools that help farmers grow their operations.

## Product Thesis

Openpasture is the data and decision layer between two things that already
exist:

- **What the world knows about the land.** Alexandria takes a location and
  returns what is known about it: current, historical, and forecast weather;
  the latest satellite imagery; drought, flood, and disaster history; soils;
  native and invasive species; and any other environmental signal worth
  tracking. Alexandria also carries the grazing knowledge: research papers,
  practitioner videos, and the hands-on wisdom of graziers like Greg Judy.
- **Where the animals are, and where they are allowed to be.** OpenCollar
  collars report each animal's position and accept boundary updates that move
  the herd.

Openpasture brings the two together. It holds the farm's own record, runs
calculations over land and collar data, and runs an agent whose job is one
question, asked every day for every herd:

> Should the herd move today, and if so, where?

The agent answers by reasoning over the data through tools and skills. When the
answer is to move, Openpasture writes the new boundary and sends it to the
collars.

## The Daily Loop

1. **Assemble.** Collar positions and tracks for the herd. An Alexandria land
   report for the current paddock and the candidates. The farm's own history of
   grazes, rest, and recovery. Relevant grazing knowledge.
2. **Derive.** Grazing pressure from collar data, days of rest per paddock,
   forage estimates from imagery, recovery trends, a feed budget against the
   forecast, weather and drought risk.
3. **Decide.** `STAY`, `MOVE` to a specific boundary, or `NEEDS_INFO`, with the
   reasoning, a confidence, and the single observation that would help most.
4. **Review.** The farmer sees the decision and can approve, change, or
   override it. How much review is required is the farmer's setting.
5. **Act.** The boundary goes to the collars. Openpasture confirms each collar
   received it.
6. **Learn.** Openpasture watches what happens next: whether the herd held the
   line, how the animals grazed, how the paddock recovered in later imagery.
   That outcome becomes context for tomorrow.

## The Farmer Stays The Operator

The engine is always working out where the herd should be. The farmer decides
how much of that to hand over:

- `propose`: every move waits for the farmer's approval. This is the default.
- `apply_unless_stopped`: a move is sent at a set time unless the farmer stops
  it first.
- `apply`: moves are sent when decided. The farmer reviews after the fact.

A farmer's override is never an error. It is the most valuable signal the
system gets, and it is recorded with the decision it replaced.

## What Openpasture Owns

Land data and grazing knowledge come from Alexandria. Position and boundary
control come from the collars. Openpasture owns what neither has:

- the farm's structure: pastures, paddocks, herds, animals, and infrastructure,
- the decision record: every decision, the inputs behind it, the farmer's
  response, the boundary sent, and the outcome that followed,
- the calculations that turn raw land and collar data into grazing signals,
- the agent's tools, skills, and operating stance.

The decision record is the heart of it. Over time it shows how this farm's land
responds to how it is grazed, and that makes each decision better than the
last.

## Where You See It

The engine runs whether anyone is watching or not. The farmer reaches it two
ways:

- **Conversation.** Any capable agent surface, including ChatGPT, Claude,
  Cursor, Hermes, a local agent, or the hosted Openpasture companion, connects
  to the same tools and state.
- **The farm view.** A map of the herd, today's boundary, and the proposed next
  one; a timeline of decisions with their reasoning; history and recovery for
  each paddock; and analytics built on the decision record. Overriding a
  decision happens right on the map.

## Repository Split

- `openpasture-agent-kit` (this repo): the engine. Domain model, decision
  record, calculations, the land and collar connectors, tools, skills, and
  knowledge access. It runs self-hosted without the cloud product.
- `openpasture-cloud`: hosted accounts, the farm view, notifications, billing,
  and support. It reads and writes through the kit.
- `opencollar`: collar hardware, firmware, and the collar protocol.
- `openpasture-web`: public site and positioning.

## Success

The product succeeds when more animals live on grass and more people can afford
to eat them. At the farm level, that means a farmer can say: "This knows my
land, watches my herd, and moves them where I would have, and when it doesn't,
it learns why."
