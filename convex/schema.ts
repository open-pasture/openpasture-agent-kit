import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  farms: defineTable({
    tenantKey: v.string(),
    farmId: v.string(),
    name: v.string(),
    timezone: v.string(),
    boundary: v.optional(v.any()),
    location: v.optional(v.any()),
    herdIds: v.array(v.string()),
    waterSources: v.array(v.any()),
    notes: v.string(),
    createdAt: v.string(),
  })
    .index("by_tenant_key", ["tenantKey"])
    .index("by_tenant_key_and_farm_id", ["tenantKey", "farmId"]),

  landUnits: defineTable({
    tenantKey: v.string(),
    landUnitId: v.string(),
    farmId: v.string(),
    parentId: v.optional(v.string()),
    unitType: v.union(
      v.literal("farm"),
      v.literal("pasture"),
      v.literal("paddock"),
      v.literal("section"),
      v.literal("no_graze_zone"),
      v.literal("water_area"),
    ),
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
  })
    .index("by_tenant_key_and_land_unit_id", ["tenantKey", "landUnitId"])
    .index("by_tenant_key_and_farm_id", ["tenantKey", "farmId"])
    .index("by_tenant_key_farm_and_type", ["tenantKey", "farmId", "unitType"])
    .index("by_tenant_key_farm_and_parent", ["tenantKey", "farmId", "parentId"]),

  herds: defineTable({
    tenantKey: v.string(),
    herdId: v.string(),
    farmId: v.string(),
    species: v.string(),
    count: v.number(),
    currentPaddockId: v.optional(v.string()),
    animalUnits: v.optional(v.number()),
    notes: v.string(),
  })
    .index("by_tenant_key_and_herd_id", ["tenantKey", "herdId"])
    .index("by_tenant_key_and_farm_id", ["tenantKey", "farmId"]),

  animals: defineTable({
    tenantKey: v.string(),
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
  })
    .index("by_tenant_key_and_animal_id", ["tenantKey", "animalId"])
    .index("by_tenant_key_and_farm_id", ["tenantKey", "farmId"])
    .index("by_tenant_key_and_herd_id", ["tenantKey", "herdId"])
    .index("by_tenant_key_farm_and_tag", ["tenantKey", "farmId", "tag"])
    .index("by_tenant_key_farm_and_status", ["tenantKey", "farmId", "status"]),

  observations: defineTable({
    tenantKey: v.string(),
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
  })
    .index("by_tenant_key_and_observation_id", ["tenantKey", "observationId"])
    .index("by_tenant_key_farm_and_observed_at", ["tenantKey", "farmId", "observedAt"])
    .index("by_tenant_key_paddock_and_observed_at", ["tenantKey", "paddockId", "observedAt"]),

  farmActivityEvents: defineTable({
    tenantKey: v.string(),
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
  })
    .index("by_tenant_key_and_activity_id", ["tenantKey", "activityId"])
    .index("by_tenant_key_farm_and_occurred_at", ["tenantKey", "farmId", "occurredAt"]),

  farmActivityTargets: defineTable({
    tenantKey: v.string(),
    activityId: v.string(),
    farmId: v.string(),
    subjectType: v.string(),
    subjectId: v.string(),
    relationship: v.string(),
    occurredAt: v.string(),
  })
    .index("by_tenant_key_and_activity_id", ["tenantKey", "activityId"])
    .index("by_tenant_key_subject_and_occurred_at", ["tenantKey", "subjectType", "subjectId", "occurredAt"])
    .index("by_tenant_key_farm_and_occurred_at", ["tenantKey", "farmId", "occurredAt"]),

  farmActivityAttachments: defineTable({
    tenantKey: v.string(),
    attachmentId: v.string(),
    activityId: v.string(),
    url: v.string(),
    mediaType: v.string(),
    fileName: v.optional(v.string()),
    contentType: v.optional(v.string()),
    metadata: v.any(),
  })
    .index("by_tenant_key_and_attachment_id", ["tenantKey", "attachmentId"])
    .index("by_tenant_key_and_activity_id", ["tenantKey", "activityId"]),

  dataPipelines: defineTable({
    tenantKey: v.string(),
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
  })
    .index("by_tenant_key_and_pipeline_id", ["tenantKey", "pipelineId"])
    .index("by_tenant_key_and_farm_id", ["tenantKey", "farmId"]),

  farmerActions: defineTable({
    tenantKey: v.string(),
    actionId: v.string(),
    farmId: v.string(),
    actionType: v.string(),
    summary: v.string(),
    context: v.any(),
    createdAt: v.string(),
    resolvedAt: v.optional(v.string()),
    resolution: v.optional(v.string()),
  })
    .index("by_tenant_key_and_action_id", ["tenantKey", "actionId"])
    .index("by_tenant_key_farm_and_resolved_at", ["tenantKey", "farmId", "resolvedAt"]),

  movementDecisions: defineTable({
    tenantKey: v.string(),
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
  })
    .index("by_tenant_key_and_plan_id", ["tenantKey", "planId"])
    .index("by_tenant_key_farm_and_for_date", ["tenantKey", "farmId", "forDate"]),

  dailyBriefs: defineTable({
    tenantKey: v.string(),
    briefId: v.string(),
    farmId: v.string(),
    generatedAt: v.string(),
    summary: v.string(),
    recommendationId: v.string(),
    uncertaintyRequest: v.optional(v.string()),
    highlights: v.array(v.string()),
  })
    .index("by_tenant_key_and_brief_id", ["tenantKey", "briefId"])
    .index("by_tenant_key_and_farm_id", ["tenantKey", "farmId"]),
});
