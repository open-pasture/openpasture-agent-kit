# Vision

## Founding Principle

Complex systems are best worked with, not abstracted away from. Regenerative agriculture rests on that insight, and `openPasture` is built from the same premise.

The daily movement decision is a living systems problem. It depends on pasture condition, rest periods, weather, herd pressure, labor realities, and the farmer's accumulated judgment. The goal is not to replace that judgment. The goal is to extend it.

## The Bottleneck

The limiting factor in regenerative grazing is not raw data collection. It is attention.

A farmer cannot be everywhere every morning. Yet a movement decision still has to be made with enough context to avoid overgrazing, preserve recovery, and keep operations moving.

`openPasture` exists to scale observational capacity without collapsing the farm into reductionist metrics.

## Product Thesis

A farmer needs two classes of input to make a good movement decision:

1. accumulated industry knowledge,
2. current farm context.

Accumulated knowledge comes from practitioners who have already learned what healthy rotation looks like in the field. Current context comes from the state of the farm today: notes, weather, imagery, photos, and prior decisions.

An agent can combine those two inputs into a daily recommendation and a targeted request for the next most useful observation.

## The Product

The product is a conversational farm companion.

Every morning it should be able to say, in plain language:

- what it believes is true about the farm,
- whether the animals should move, stay, or wait for more information,
- why it thinks that,
- what single observation would reduce uncertainty the most.

## Agent-First Stance

The open-source Hermes plugin is the primary product artifact.

Everything that can reasonably live inside the self-hostable agent should live there. Hosted infrastructure is valuable, but secondary. The community value comes from the agent core being coherent, useful, and extensible.

## Inputs We Can Start With

- farmer field notes,
- farmer photos,
- weather data,
- satellite imagery,
- curated practitioner knowledge, especially video transcripts.

These are enough to build the first useful morning brief loop.

## What We Are Not Building First

- autonomous collar control,
- real-time herd tracking,
- hardware firmware,
- dense soil instrumentation,
- a dashboard-first product.

Those may matter later. The first milestone is a trustworthy daily advisor.

## Why Now

Three things now converge:

- modern LLM agents can reason across heterogeneous signals,
- satellite and weather data are accessible enough to be practical inputs,
- messaging-first software can meet farmers where they already are.

## Success

The product succeeds when a farmer says: "This matches how I think about my land." It wins when they say: "I can manage more acres because this is here."
