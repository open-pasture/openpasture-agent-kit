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
  paddockIds: v.array(v.string()),
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
  paddockIds: v.optional(v.array(v.string())),
  herdIds: v.optional(v.array(v.string())),
  waterSources: v.optional(v.array(v.any())),
  notes: v.optional(v.string()),
});

const paddockRecord = v.object({
  paddockId: v.string(),
  farmId: v.string(),
  name: v.string(),
  geometry: v.any(),
  areaHectares: v.optional(v.number()),
  notes: v.string(),
  status: v.string(),
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
  tags: v.array(v.string()),
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

async function appendFarmReference(
  ctx: any,
  tenantKey: string,
  farmId: string,
  field: "paddockIds" | "herdIds",
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

export const getPaddock = query({
  args: { tenantKey: v.string(), paddockId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("paddocks")
      .withIndex("by_tenant_key_and_paddock_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("paddockId", args.paddockId))
      .unique();
  },
});

export const listPaddocks = query({
  args: { tenantKey: v.string(), farmId: v.string() },
  handler: async (ctx, args) => {
    const paddocks = await ctx.db
      .query("paddocks")
      .withIndex("by_tenant_key_and_farm_id", (q: any) => q.eq("tenantKey", args.tenantKey).eq("farmId", args.farmId))
      .take(500);
    return paddocks.sort((left, right) => left.name.localeCompare(right.name));
  },
});

export const createPaddock = mutation({
  args: { tenantKey: v.string(), record: paddockRecord },
  handler: async (ctx, args) => {
    await ctx.db.insert("paddocks", { tenantKey: args.tenantKey, ...args.record });
    await appendFarmReference(ctx, args.tenantKey, args.record.farmId, "paddockIds", args.record.paddockId);
    return args.record.paddockId;
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
    return true;
  },
});

export const recordObservation = mutation({
  args: { tenantKey: v.string(), record: observationRecord },
  handler: async (ctx, args) => {
    await ctx.db.insert("observations", { tenantKey: args.tenantKey, ...args.record });
    return args.record.observationId;
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
    return true;
  },
});

export const createPlan = mutation({
  args: { tenantKey: v.string(), record: planRecord },
  handler: async (ctx, args) => {
    await ctx.db.insert("movementDecisions", { tenantKey: args.tenantKey, ...args.record });
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
