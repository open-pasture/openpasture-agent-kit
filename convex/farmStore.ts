import { mutationGeneric as mutation, queryGeneric as query } from "convex/server";
import { v } from "convex/values";

const landUnitType = v.union(
  v.literal("farm"),
  v.literal("pasture"),
  v.literal("paddock"),
  v.literal("section"),
  v.literal("no_graze_zone"),
  v.literal("water_area"),
);

const farmRecord = v.object({
  farmId: v.string(),
  name: v.string(),
  timezone: v.string(),
  boundary: v.optional(v.any()),
  location: v.optional(v.any()),
  herdIds: v.array(v.string()),
  waterSources: v.array(v.any()),
  notes: v.string(),
  createdAt: v.string(),
});

const farmPatch = v.object({
  name: v.optional(v.string()),
  timezone: v.optional(v.string()),
  boundary: v.optional(v.any()),
  location: v.optional(v.any()),
  herdIds: v.optional(v.array(v.string())),
  waterSources: v.optional(v.array(v.any())),
  notes: v.optional(v.string()),
});

const landUnitRecord = v.object({
  landUnitId: v.string(),
  farmId: v.string(),
  parentId: v.optional(v.string()),
  unitType: landUnitType,
  name: v.string(),
  geometry: v.any(),
  areaHectares: v.optional(v.number()),
  confidence: v.number(),
  provenance: v.any(),
  geometryVersion: v.number(),
  status: v.string(),
  notes: v.string(),
  warnings: v.array(v.string()),
  createdAt: v.string(),
  updatedAt: v.string(),
});

const landUnitPatch = v.object({
  parentId: v.optional(v.string()),
  name: v.optional(v.string()),
  geometry: v.optional(v.any()),
  areaHectares: v.optional(v.number()),
  confidence: v.optional(v.number()),
  provenance: v.optional(v.any()),
  geometryVersion: v.optional(v.number()),
  status: v.optional(v.string()),
  notes: v.optional(v.string()),
  warnings: v.optional(v.array(v.string())),
  updatedAt: v.optional(v.string()),
});

const herdRecord = v.object({
  herdId: v.string(),
  farmId: v.string(),
  species: v.string(),
  count: v.number(),
  currentPaddockId: v.optional(v.string()),
  animalUnits: v.optional(v.number()),
  notes: v.string(),
});

const animalRecord = v.object({
  animalId: v.string(),
  farmId: v.string(),
  herdId: v.optional(v.string()),
  species: v.string(),
  sex: v.string(),
  name: v.optional(v.string()),
  tag: v.string(),
  secondaryTags: v.array(v.string()),
  breed: v.optional(v.string()),
  birthDate: v.optional(v.string()),
  damId: v.optional(v.string()),
  sireId: v.optional(v.string()),
  status: v.string(),
  currentPaddockId: v.optional(v.string()),
  notes: v.string(),
  metadata: v.any(),
  createdAt: v.string(),
  updatedAt: v.string(),
});

const animalPatch = v.object({
  herdId: v.optional(v.string()),
  species: v.optional(v.string()),
  sex: v.optional(v.string()),
  name: v.optional(v.string()),
  tag: v.optional(v.string()),
  secondaryTags: v.optional(v.array(v.string())),
  breed: v.optional(v.string()),
  birthDate: v.optional(v.string()),
  damId: v.optional(v.string()),
  sireId: v.optional(v.string()),
  status: v.optional(v.string()),
  currentPaddockId: v.optional(v.string()),
  notes: v.optional(v.string()),
  metadata: v.optional(v.any()),
  updatedAt: v.optional(v.string()),
});

const observationRecord = v.object({
  observationId: v.string(),
  farmId: v.string(),
  source: v.string(),
  observedAt: v.string(),
  content: v.string(),
  paddockId: v.optional(v.string()),
  herdId: v.optional(v.string()),
  metrics: v.any(),
  mediaUrl: v.optional(v.string()),
  mediaThumbnailUrl: v.optional(v.string()),
  mediaMetadata: v.optional(v.any()),
  tags: v.array(v.string()),
});

const activityTargetRecord = v.object({
  subjectType: v.string(),
  subjectId: v.string(),
  relationship: v.string(),
});

const activityAttachmentRecord = v.object({
  attachmentId: v.string(),
  url: v.string(),
  mediaType: v.string(),
  thumbnailUrl: v.optional(v.string()),
  fileName: v.optional(v.string()),
  contentType: v.optional(v.string()),
  metadata: v.any(),
});

const activityRecord = v.object({
  activityId: v.string(),
  farmId: v.string(),
  eventType: v.string(),
  source: v.string(),
  occurredAt: v.string(),
  recordedAt: v.string(),
  title: v.string(),
  body: v.string(),
  summary: v.optional(v.string()),
  payload: v.any(),
  provenance: v.any(),
  visibility: v.string(),
  targets: v.array(activityTargetRecord),
  attachments: v.array(activityAttachmentRecord),
});

const pipelineRecord = v.object({
  pipelineId: v.string(),
  farmId: v.string(),
  name: v.string(),
  profileId: v.string(),
  loginUrl: v.string(),
  targetUrls: v.array(v.string()),
  extractionPrompts: v.array(v.string()),
  observationSource: v.string(),
  observationTags: v.array(v.string()),
  schedule: v.string(),
  vendorSkillVersion: v.optional(v.string()),
  enabled: v.boolean(),
  lastCollectedAt: v.optional(v.string()),
  lastError: v.optional(v.string()),
  createdAt: v.string(),
});

const pipelinePatch = v.object({
  name: v.optional(v.string()),
  profileId: v.optional(v.string()),
  loginUrl: v.optional(v.string()),
  targetUrls: v.optional(v.array(v.string())),
  extractionPrompts: v.optional(v.array(v.string())),
  observationSource: v.optional(v.string()),
  observationTags: v.optional(v.array(v.string())),
  schedule: v.optional(v.string()),
  vendorSkillVersion: v.optional(v.string()),
  enabled: v.optional(v.boolean()),
  lastCollectedAt: v.optional(v.string()),
  lastError: v.optional(v.string()),
});

const farmerActionRecord = v.object({
  actionId: v.string(),
  farmId: v.string(),
  actionType: v.string(),
  summary: v.string(),
  context: v.any(),
  createdAt: v.string(),
  resolvedAt: v.optional(v.string()),
  resolution: v.optional(v.string()),
});

const planRecord = v.object({
  planId: v.string(),
  farmId: v.string(),
  herdId: v.optional(v.string()),
  forDate: v.string(),
  action: v.string(),
  reasoning: v.array(v.string()),
  confidence: v.string(),
  sourcePaddockId: v.optional(v.string()),
  targetPaddockId: v.optional(v.string()),
  knowledgeEntryIds: v.array(v.string()),
  status: v.string(),
  farmerFeedback: v.optional(v.string()),
  createdAt: v.string(),
});

const briefRecord = v.object({
  briefId: v.string(),
  farmId: v.string(),
  generatedAt: v.string(),
  summary: v.string(),
  recommendationId: v.string(),
  uncertaintyRequest: v.optional(v.string()),
  highlights: v.array(v.string()),
});

function cleanPatch<T extends Record<string, unknown>>(value: T) {
  return Object.fromEntries(Object.entries(value).filter(([, entry]) => entry !== undefined)) as Partial<T>;
}

async function activityOut(ctx: any, tenantKey: string, event: any) {
  const [targets, attachments] = await Promise.all([
    ctx.db
      .query("farmActivityTargets")
      .withIndex("by_tenant_key_and_activity_id", (q: any) =>
        q.eq("tenantKey", tenantKey).eq("activityId", event.activityId),
      )
      .take(100),
    ctx.db
      .query("farmActivityAttachments")
      .withIndex("by_tenant_key_and_activity_id", (q: any) =>
        q.eq("tenantKey", tenantKey).eq("activityId", event.activityId),
      )
      .take(100),
  ]);

  return { ...event, targets, attachments };
}

async function listActivityFeedForSubject(
  ctx: any,
  args: {
    tenantKey: string;
    farmId: string;
    subjectType: string;
    subjectId: string;
    limit?: number;
    before?: string;
  },
) {
  const limit = Math.min(args.limit ?? 50, 100);
  const targets = args.before
    ? await ctx.db
        .query("farmActivityTargets")
        .withIndex("by_tenant_key_subject_and_occurred_at", (q: any) =>
          q.eq("tenantKey", args.tenantKey).eq("subjectType", args.subjectType).eq("subjectId", args.subjectId).lt("occurredAt", args.before),
        )
        .order("desc")
        .take(limit)
    : await ctx.db
        .query("farmActivityTargets")
        .withIndex("by_tenant_key_subject_and_occurred_at", (q: any) =>
          q.eq("tenantKey", args.tenantKey).eq("subjectType", args.subjectType).eq("subjectId", args.subjectId),
        )
        .order("desc")
        .take(limit);
  const events = [];
  for (const target of targets.filter((target: any) => target.farmId === args.farmId)) {
    const event = await ctx.db
      .query("farmActivityEvents")
      .withIndex("by_tenant_key_and_activity_id", (q: any) =>
        q.eq("tenantKey", args.tenantKey).eq("activityId", target.activityId),
      )
      .unique();
    if (event) events.push(await activityOut(ctx, args.tenantKey, event));
  }
  return events;
}

function uniqueActivityId(prefix: string) {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

async function targetsForPaddock(ctx: any, tenantKey: string, paddockId: string, relationship = "primary") {
  const targets = [{ subjectType: "paddock", subjectId: paddockId, relationship }];
  const unit = await ctx.db
    .query("landUnits")
    .withIndex("by_tenant_key_and_land_unit_id", (q: any) => q.eq("tenantKey", tenantKey).eq("landUnitId", paddockId))
    .unique();
  if (unit?.unitType === "pasture") {
    return [{ subjectType: "pasture", subjectId: paddockId, relationship }];
  }
  if (unit?.parentId) {
    const parent = await ctx.db
      .query("landUnits")
      .withIndex("by_tenant_key_and_land_unit_id", (q: any) => q.eq("tenantKey", tenantKey).eq("landUnitId", unit.parentId))
      .unique();
    if (parent?.unitType === "pasture") {
      targets.push({ subjectType: "pasture", subjectId: parent.landUnitId, relationship: "parent" });
    }
  }
  return targets;
}

async function insertActivityRows(ctx: any, tenantKey: string, record: any) {
  await ctx.db.insert("farmActivityEvents", {
    tenantKey,
    activityId: record.activityId,
    farmId: record.farmId,
    eventType: record.eventType,
    source: record.source,
    occurredAt: record.occurredAt,
    recordedAt: record.recordedAt,
    title: record.title,
    body: record.body,
    summary: record.summary,
    payload: record.payload ?? {},
    provenance: record.provenance ?? {},
    visibility: record.visibility ?? "farm",
  });
  for (const target of record.targets ?? []) {
    await ctx.db.insert("farmActivityTargets", {
      tenantKey,
      activityId: record.activityId,
      farmId: record.farmId,
      subjectType: target.subjectType,
      subjectId: target.subjectId,
      relationship: target.relationship ?? "primary",
      occurredAt: record.occurredAt,
    });
  }
  for (const attachment of record.attachments ?? []) {
    await ctx.db.insert("farmActivityAttachments", {
      tenantKey,
      activityId: record.activityId,
      ...attachment,
      metadata: attachment.metadata ?? {},
    });
  }
}

async function appendFarmReference(
  ctx: any,
  tenantKey: string,
  farmId: string,
  field: "herdIds",
  value: string,
) {
  const farm = await ctx.db
    .query("farms")
    .withIndex("by_tenant_key_and_farm_id", (q: any) => q.eq("tenantKey", tenantKey).eq("farmId", farmId))
    .unique();

  if (!farm) {
    throw new Error(`Farm '${farmId}' does not exist.`);
  }

  const values = farm[field];
  if (!values.includes(value)) {
    await ctx.db.patch(farm._id, { [field]: [...values, value] });
  }
}

export const listFarms = query({
  args: { tenantKey: v.string() },
  handler: async (ctx, args) => {
    const farms = await ctx.db
      .query("farms")
      .withIndex("by_tenant_key", (q: any) => q.eq("tenantKey", args.tenantKey))
      .take(500);
    return farms.sort((left, right) => left.name.localeCompare(right.name));
  },
});

export const getFarm = query({
  args: { tenantKey: v.string(), farmId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("farms")
      .withIndex("by_tenant_key_and_farm_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("farmId", args.farmId))
      .unique();
  },
});

export const createFarm = mutation({
  args: { tenantKey: v.string(), record: farmRecord },
  handler: async (ctx, args) => {
    await ctx.db.insert("farms", { tenantKey: args.tenantKey, ...args.record });
    return args.record.farmId;
  },
});

export const updateFarm = mutation({
  args: { tenantKey: v.string(), farmId: v.string(), patch: farmPatch },
  handler: async (ctx, args) => {
    const farm = await ctx.db
      .query("farms")
      .withIndex("by_tenant_key_and_farm_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("farmId", args.farmId))
      .unique();
    if (!farm) throw new Error(`Farm '${args.farmId}' does not exist.`);
    await ctx.db.patch(farm._id, cleanPatch(args.patch));
    return true;
  },
});

export const getLandUnit = query({
  args: { tenantKey: v.string(), landUnitId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("landUnits")
      .withIndex("by_tenant_key_and_land_unit_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("landUnitId", args.landUnitId))
      .unique();
  },
});

export const listLandUnits = query({
  args: { tenantKey: v.string(), farmId: v.string(), unitType: v.optional(landUnitType) },
  handler: async (ctx, args) => {
    const rows = args.unitType
      ? await ctx.db
          .query("landUnits")
          .withIndex("by_tenant_key_farm_and_type", (q: any) =>
            q.eq("tenantKey", args.tenantKey).eq("farmId", args.farmId).eq("unitType", args.unitType),
          )
          .take(500)
      : await ctx.db
          .query("landUnits")
          .withIndex("by_tenant_key_and_farm_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("farmId", args.farmId))
          .take(500);
    return rows.sort((left, right) => left.unitType.localeCompare(right.unitType) || left.name.localeCompare(right.name));
  },
});

export const upsertLandUnit = mutation({
  args: { tenantKey: v.string(), record: landUnitRecord },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("landUnits")
      .withIndex("by_tenant_key_and_land_unit_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("landUnitId", args.record.landUnitId))
      .unique();
    if (existing) {
      await ctx.db.patch(existing._id, args.record);
    } else {
      await ctx.db.insert("landUnits", { tenantKey: args.tenantKey, ...args.record });
    }
    return args.record.landUnitId;
  },
});

export const updateLandUnit = mutation({
  args: { tenantKey: v.string(), landUnitId: v.string(), patch: landUnitPatch },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("landUnits")
      .withIndex("by_tenant_key_and_land_unit_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("landUnitId", args.landUnitId))
      .unique();
    if (!existing) throw new Error(`Land unit '${args.landUnitId}' does not exist.`);
    await ctx.db.patch(existing._id, cleanPatch(args.patch));
    return true;
  },
});

export const createHerd = mutation({
  args: { tenantKey: v.string(), record: herdRecord },
  handler: async (ctx, args) => {
    await ctx.db.insert("herds", { tenantKey: args.tenantKey, ...args.record });
    await appendFarmReference(ctx, args.tenantKey, args.record.farmId, "herdIds", args.record.herdId);
    return args.record.herdId;
  },
});

export const listHerds = query({
  args: { tenantKey: v.string(), farmId: v.string() },
  handler: async (ctx, args) => {
    const herds = await ctx.db
      .query("herds")
      .withIndex("by_tenant_key_and_farm_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("farmId", args.farmId))
      .take(500);
    return herds.sort((left, right) => left.species.localeCompare(right.species) || left.herdId.localeCompare(right.herdId));
  },
});

export const updateHerdPosition = mutation({
  args: { tenantKey: v.string(), herdId: v.string(), paddockId: v.string() },
  handler: async (ctx, args) => {
    const herd = await ctx.db
      .query("herds")
      .withIndex("by_tenant_key_and_herd_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("herdId", args.herdId))
      .unique();
    if (!herd) throw new Error(`Herd '${args.herdId}' does not exist.`);
    await ctx.db.patch(herd._id, { currentPaddockId: args.paddockId });
    const now = new Date().toISOString();
    await insertActivityRows(ctx, args.tenantKey, {
      activityId: uniqueActivityId("activity_herd_position"),
      farmId: herd.farmId,
      eventType: "movement",
      source: "herd_position",
      occurredAt: now,
      recordedAt: now,
      title: "Herd moved",
      body: `${herd.species} herd moved to ${args.paddockId}.`,
      payload: { herd_id: args.herdId, target_paddock_id: args.paddockId },
      provenance: { source: "herd_position" },
      visibility: "farm",
      targets: [
        { subjectType: "farm", subjectId: herd.farmId, relationship: "farm" },
        { subjectType: "herd", subjectId: args.herdId, relationship: "primary" },
        ...(await targetsForPaddock(ctx, args.tenantKey, args.paddockId, "target")),
      ],
      attachments: [],
    });
    return true;
  },
});

export const createAnimal = mutation({
  args: { tenantKey: v.string(), record: animalRecord },
  handler: async (ctx, args) => {
    await ctx.db.insert("animals", { tenantKey: args.tenantKey, ...args.record });
    await insertActivityRows(ctx, args.tenantKey, {
      activityId: uniqueActivityId("activity_animal_created"),
      farmId: args.record.farmId,
      eventType: "animal_created",
      source: "animal_record",
      occurredAt: args.record.createdAt,
      recordedAt: new Date().toISOString(),
      title: `Animal ${args.record.tag} added`,
      body: args.record.notes,
      payload: { animal_id: args.record.animalId, tag: args.record.tag, species: args.record.species, status: args.record.status },
      provenance: { source: "animal_record", animal_id: args.record.animalId },
      visibility: "farm",
      targets: [
        { subjectType: "farm", subjectId: args.record.farmId, relationship: "farm" },
        { subjectType: "animal", subjectId: args.record.animalId, relationship: "primary" },
        ...(args.record.herdId ? [{ subjectType: "herd", subjectId: args.record.herdId, relationship: "herd" }] : []),
      ],
      attachments: [],
    });
    return args.record.animalId;
  },
});

export const getAnimal = query({
  args: { tenantKey: v.string(), animalId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("animals")
      .withIndex("by_tenant_key_and_animal_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("animalId", args.animalId))
      .unique();
  },
});

export const listAnimals = query({
  args: { tenantKey: v.string(), farmId: v.string(), herdId: v.optional(v.string()) },
  handler: async (ctx, args) => {
    const rows = args.herdId
      ? await ctx.db
          .query("animals")
          .withIndex("by_tenant_key_and_herd_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("herdId", args.herdId))
          .take(500)
      : await ctx.db
          .query("animals")
          .withIndex("by_tenant_key_and_farm_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("farmId", args.farmId))
          .take(500);
    return rows
      .filter((row) => row.farmId === args.farmId)
      .sort((left, right) => left.tag.localeCompare(right.tag) || left.animalId.localeCompare(right.animalId));
  },
});

export const updateAnimal = mutation({
  args: { tenantKey: v.string(), animalId: v.string(), patch: animalPatch },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("animals")
      .withIndex("by_tenant_key_and_animal_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("animalId", args.animalId))
      .unique();
    if (!existing) throw new Error(`Animal '${args.animalId}' does not exist.`);
    await ctx.db.patch(existing._id, cleanPatch(args.patch));
    return true;
  },
});

export const recordObservation = mutation({
  args: { tenantKey: v.string(), record: observationRecord },
  handler: async (ctx, args) => {
    await ctx.db.insert("observations", { tenantKey: args.tenantKey, ...args.record });
    const paddockTargets = args.record.paddockId
      ? await targetsForPaddock(ctx, args.tenantKey, args.record.paddockId)
      : [];
    await insertActivityRows(ctx, args.tenantKey, {
      activityId: `activity_observation_${args.record.observationId}`,
      farmId: args.record.farmId,
      eventType: {
        weather: "weather_report",
        photo: "image_observation",
        trailcam: "image_observation",
        satellite: "imported_report",
      }[args.record.source] ?? "field_note",
      source: args.record.source,
      occurredAt: args.record.observedAt,
      recordedAt: new Date().toISOString(),
      title: args.record.content.slice(0, 80) || "Observation recorded",
      body: args.record.content,
      payload: { observation_id: args.record.observationId, metrics: args.record.metrics, tags: args.record.tags },
      provenance: { source: "observation", observation_id: args.record.observationId },
      visibility: "farm",
      targets: [
        { subjectType: "farm", subjectId: args.record.farmId, relationship: "farm" },
        ...paddockTargets,
        ...(args.record.herdId ? [{ subjectType: "herd", subjectId: args.record.herdId, relationship: "primary" }] : []),
      ],
      attachments: args.record.mediaUrl
        ? [{
            attachmentId: `attachment_${args.record.observationId}`,
            url: args.record.mediaUrl,
            mediaType: ["photo", "trailcam"].includes(args.record.source) ? "image" : "file",
            thumbnailUrl: args.record.mediaThumbnailUrl,
            metadata: { observation_id: args.record.observationId, ...(args.record.mediaMetadata ?? {}) },
          }]
        : [],
    });
    return args.record.observationId;
  },
});

export const recordActivityEvent = mutation({
  args: { tenantKey: v.string(), record: activityRecord },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("farmActivityEvents")
      .withIndex("by_tenant_key_and_activity_id", (q: any) =>
        q.eq("tenantKey", args.tenantKey).eq("activityId", args.record.activityId),
      )
      .unique();
    if (existing) {
      throw new Error(`Activity '${args.record.activityId}' already exists.`);
    }

    await insertActivityRows(ctx, args.tenantKey, args.record);

    return args.record.activityId;
  },
});

export const listActivityFeed = query({
  args: {
    tenantKey: v.string(),
    farmId: v.string(),
    subjectType: v.string(),
    subjectId: v.string(),
    limit: v.optional(v.number()),
    before: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    return await listActivityFeedForSubject(ctx, args);
  },
});

export const listAnimalActivity = query({
  args: { tenantKey: v.string(), animalId: v.string(), limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    const animal = await ctx.db
      .query("animals")
      .withIndex("by_tenant_key_and_animal_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("animalId", args.animalId))
      .unique();
    if (!animal) return [];
    return await listActivityFeedForSubject(ctx, {
      tenantKey: args.tenantKey,
      farmId: animal.farmId,
      subjectType: "animal",
      subjectId: args.animalId,
      limit: args.limit,
    });
  },
});

export const listRecentObservations = query({
  args: { tenantKey: v.string(), farmId: v.string(), observedAfter: v.string() },
  handler: async (ctx, args) => {
    const observations = await ctx.db
      .query("observations")
      .withIndex("by_tenant_key_farm_and_observed_at", (q: any) =>
        q.eq("tenantKey", args.tenantKey).eq("farmId", args.farmId).gte("observedAt", args.observedAfter),
      )
      .take(500);
    return observations.sort((left, right) => right.observedAt.localeCompare(left.observedAt));
  },
});

export const listPaddockObservations = query({
  args: { tenantKey: v.string(), paddockId: v.string(), observedAfter: v.string() },
  handler: async (ctx, args) => {
    const observations = await ctx.db
      .query("observations")
      .withIndex("by_tenant_key_paddock_and_observed_at", (q: any) =>
        q.eq("tenantKey", args.tenantKey).eq("paddockId", args.paddockId).gte("observedAt", args.observedAfter),
      )
      .take(500);
    return observations.sort((left, right) => right.observedAt.localeCompare(left.observedAt));
  },
});

export const createPipeline = mutation({
  args: { tenantKey: v.string(), record: pipelineRecord },
  handler: async (ctx, args) => {
    await ctx.db.insert("dataPipelines", { tenantKey: args.tenantKey, ...args.record });
    return args.record.pipelineId;
  },
});

export const getPipeline = query({
  args: { tenantKey: v.string(), pipelineId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("dataPipelines")
      .withIndex("by_tenant_key_and_pipeline_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("pipelineId", args.pipelineId))
      .unique();
  },
});

export const listPipelines = query({
  args: { tenantKey: v.string(), farmId: v.string() },
  handler: async (ctx, args) => {
    const pipelines = await ctx.db
      .query("dataPipelines")
      .withIndex("by_tenant_key_and_farm_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("farmId", args.farmId))
      .take(500);
    return pipelines.sort((left, right) => left.name.localeCompare(right.name) || left.createdAt.localeCompare(right.createdAt));
  },
});

export const updatePipeline = mutation({
  args: { tenantKey: v.string(), pipelineId: v.string(), patch: pipelinePatch },
  handler: async (ctx, args) => {
    const pipeline = await ctx.db
      .query("dataPipelines")
      .withIndex("by_tenant_key_and_pipeline_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("pipelineId", args.pipelineId))
      .unique();
    if (!pipeline) throw new Error(`Pipeline '${args.pipelineId}' does not exist.`);
    await ctx.db.patch(pipeline._id, cleanPatch(args.patch));
    return true;
  },
});

export const createFarmerAction = mutation({
  args: { tenantKey: v.string(), record: farmerActionRecord },
  handler: async (ctx, args) => {
    await ctx.db.insert("farmerActions", { tenantKey: args.tenantKey, ...args.record });
    await insertActivityRows(ctx, args.tenantKey, {
      activityId: uniqueActivityId("activity_farmer_action"),
      farmId: args.record.farmId,
      eventType: "farmer_action",
      source: "agent",
      occurredAt: args.record.createdAt,
      recordedAt: new Date().toISOString(),
      title: args.record.summary,
      body: args.record.summary,
      payload: { action_id: args.record.actionId, action_type: args.record.actionType, context: args.record.context },
      provenance: { source: "farmer_action", action_id: args.record.actionId },
      visibility: "farm",
      targets: [{ subjectType: "farm", subjectId: args.record.farmId, relationship: "farm" }],
      attachments: [],
    });
    return args.record.actionId;
  },
});

export const listPendingActions = query({
  args: { tenantKey: v.string(), farmId: v.string() },
  handler: async (ctx, args) => {
    const actions = await ctx.db
      .query("farmerActions")
      .withIndex("by_tenant_key_farm_and_resolved_at", (q: any) =>
        q.eq("tenantKey", args.tenantKey).eq("farmId", args.farmId).eq("resolvedAt", undefined),
      )
      .take(500);
    return actions.sort((left, right) => left.createdAt.localeCompare(right.createdAt));
  },
});

export const resolveFarmerAction = mutation({
  args: { tenantKey: v.string(), actionId: v.string(), resolvedAt: v.string(), resolution: v.string() },
  handler: async (ctx, args) => {
    const action = await ctx.db
      .query("farmerActions")
      .withIndex("by_tenant_key_and_action_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("actionId", args.actionId))
      .unique();
    if (!action) throw new Error(`Farmer action '${args.actionId}' does not exist.`);
    await ctx.db.patch(action._id, { resolvedAt: args.resolvedAt, resolution: args.resolution });
    await insertActivityRows(ctx, args.tenantKey, {
      activityId: uniqueActivityId("activity_farmer_action_resolved"),
      farmId: action.farmId,
      eventType: "farmer_action_resolved",
      source: "agent",
      occurredAt: args.resolvedAt,
      recordedAt: new Date().toISOString(),
      title: `Action resolved: ${action.summary}`,
      body: args.resolution,
      payload: { action_id: args.actionId, resolution: args.resolution },
      provenance: { source: "farmer_action", action_id: args.actionId },
      visibility: "farm",
      targets: [{ subjectType: "farm", subjectId: action.farmId, relationship: "farm" }],
      attachments: [],
    });
    return true;
  },
});

export const createPlan = mutation({
  args: { tenantKey: v.string(), record: planRecord },
  handler: async (ctx, args) => {
    await ctx.db.insert("movementDecisions", { tenantKey: args.tenantKey, ...args.record });
    await insertActivityRows(ctx, args.tenantKey, {
      activityId: uniqueActivityId("activity_grazing_decision"),
      farmId: args.record.farmId,
      eventType: "grazing_decision",
      source: "movement_plan",
      occurredAt: args.record.createdAt,
      recordedAt: new Date().toISOString(),
      title: `Grazing decision: ${args.record.action}`,
      body: args.record.reasoning.join("\n"),
      payload: {
        plan_id: args.record.planId,
        action: args.record.action,
        confidence: args.record.confidence,
        for_date: args.record.forDate,
        source_paddock_id: args.record.sourcePaddockId,
        target_paddock_id: args.record.targetPaddockId,
        status: args.record.status,
      },
      provenance: { source: "movement_decision", plan_id: args.record.planId },
      visibility: "farm",
      targets: [
        { subjectType: "farm", subjectId: args.record.farmId, relationship: "farm" },
        ...(args.record.herdId ? [{ subjectType: "herd", subjectId: args.record.herdId, relationship: "primary" }] : []),
        ...(args.record.sourcePaddockId ? await targetsForPaddock(ctx, args.tenantKey, args.record.sourcePaddockId, "source") : []),
        ...(args.record.targetPaddockId ? await targetsForPaddock(ctx, args.tenantKey, args.record.targetPaddockId, "target") : []),
      ],
      attachments: [],
    });
    return args.record.planId;
  },
});

export const getPlan = query({
  args: { tenantKey: v.string(), planId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("movementDecisions")
      .withIndex("by_tenant_key_and_plan_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("planId", args.planId))
      .unique();
  },
});

export const getLatestPlan = query({
  args: { tenantKey: v.string(), farmId: v.string() },
  handler: async (ctx, args) => {
    const plans = await ctx.db
      .query("movementDecisions")
      .withIndex("by_tenant_key_farm_and_for_date", (q: any) => q.eq("tenantKey", args.tenantKey).eq("farmId", args.farmId))
      .take(500);
    return plans.sort((left, right) => right.forDate.localeCompare(left.forDate) || right.createdAt.localeCompare(left.createdAt))[0] ?? null;
  },
});

export const updatePlanStatus = mutation({
  args: { tenantKey: v.string(), planId: v.string(), status: v.string(), farmerFeedback: v.optional(v.string()) },
  handler: async (ctx, args) => {
    const plan = await ctx.db
      .query("movementDecisions")
      .withIndex("by_tenant_key_and_plan_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("planId", args.planId))
      .unique();
    if (!plan) throw new Error(`Movement decision '${args.planId}' does not exist.`);
    await ctx.db.patch(plan._id, cleanPatch({ status: args.status, farmerFeedback: args.farmerFeedback }));
    const now = new Date().toISOString();
    await insertActivityRows(ctx, args.tenantKey, {
      activityId: uniqueActivityId("activity_grazing_decision_status"),
      farmId: plan.farmId,
      eventType: "grazing_decision_status",
      source: "movement_plan",
      occurredAt: now,
      recordedAt: now,
      title: `Grazing decision ${args.status}`,
      body: args.farmerFeedback ?? "",
      payload: { plan_id: args.planId, status: args.status, feedback: args.farmerFeedback },
      provenance: { source: "movement_decision", plan_id: args.planId },
      visibility: "farm",
      targets: [
        { subjectType: "farm", subjectId: plan.farmId, relationship: "farm" },
        ...(plan.herdId ? [{ subjectType: "herd", subjectId: plan.herdId, relationship: "primary" }] : []),
      ],
      attachments: [],
    });
    return true;
  },
});

export const saveDailyBrief = mutation({
  args: { tenantKey: v.string(), record: briefRecord },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("dailyBriefs")
      .withIndex("by_tenant_key_and_brief_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("briefId", args.record.briefId))
      .unique();
    if (existing) {
      await ctx.db.patch(existing._id, args.record);
    } else {
      await ctx.db.insert("dailyBriefs", { tenantKey: args.tenantKey, ...args.record });
    }
    const plan = await ctx.db
      .query("movementDecisions")
      .withIndex("by_tenant_key_and_plan_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("planId", args.record.recommendationId))
      .unique();
    await insertActivityRows(ctx, args.tenantKey, {
      activityId: uniqueActivityId("activity_daily_brief"),
      farmId: args.record.farmId,
      eventType: "daily_brief",
      source: "briefing",
      occurredAt: args.record.generatedAt,
      recordedAt: new Date().toISOString(),
      title: "Daily brief generated",
      body: args.record.summary,
      payload: {
        brief_id: args.record.briefId,
        recommendation_id: args.record.recommendationId,
        uncertainty_request: args.record.uncertaintyRequest,
        highlights: args.record.highlights,
      },
      provenance: { source: "daily_brief", brief_id: args.record.briefId },
      visibility: "farm",
      targets: [
        { subjectType: "farm", subjectId: args.record.farmId, relationship: "farm" },
        ...(plan?.herdId ? [{ subjectType: "herd", subjectId: plan.herdId, relationship: "primary" }] : []),
      ],
      attachments: [],
    });
    return args.record.briefId;
  },
});

export const getDailyBrief = query({
  args: { tenantKey: v.string(), briefId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("dailyBriefs")
      .withIndex("by_tenant_key_and_brief_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("briefId", args.briefId))
      .unique();
  },
});
