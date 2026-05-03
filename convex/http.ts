import { anyApi, httpActionGeneric as httpAction, httpRouter } from "convex/server";

function json(data: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(data), {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
}

function bearerToken(request: Request) {
  const header = request.headers.get("authorization") ?? "";
  const [scheme, token] = header.split(/\s+/, 2);
  return scheme?.toLowerCase() === "bearer" && token ? token : null;
}

function requireTenantKey(request: Request, payload: { tenantKey?: unknown }) {
  const tenantKey = bearerToken(request) ?? payload.tenantKey;
  if (typeof tenantKey !== "string" || !tenantKey.trim()) {
    return null;
  }

  const configuredKey = process.env.OPENPASTURE_CONVEX_STORE_KEY?.trim();
  if (configuredKey && tenantKey !== configuredKey) {
    return null;
  }

  return tenantKey.trim();
}

const queryOperations = new Set([
  "farms.list",
  "farms.get",
  "landUnits.get",
  "landUnits.list",
  "herds.list",
  "observations.recent",
  "observations.byPaddock",
  "pipelines.get",
  "pipelines.list",
  "farmerActions.pending",
  "plans.get",
  "plans.latest",
  "dailyBriefs.get",
]);

const functionByOperation: Record<string, unknown> = {
  "farms.list": anyApi.farmStore.listFarms,
  "farms.get": anyApi.farmStore.getFarm,
  "farms.create": anyApi.farmStore.createFarm,
  "farms.update": anyApi.farmStore.updateFarm,
  "landUnits.get": anyApi.farmStore.getLandUnit,
  "landUnits.list": anyApi.farmStore.listLandUnits,
  "landUnits.upsert": anyApi.farmStore.upsertLandUnit,
  "landUnits.update": anyApi.farmStore.updateLandUnit,
  "herds.create": anyApi.farmStore.createHerd,
  "herds.list": anyApi.farmStore.listHerds,
  "herds.updatePosition": anyApi.farmStore.updateHerdPosition,
  "observations.record": anyApi.farmStore.recordObservation,
  "observations.recent": anyApi.farmStore.listRecentObservations,
  "observations.byPaddock": anyApi.farmStore.listPaddockObservations,
  "pipelines.create": anyApi.farmStore.createPipeline,
  "pipelines.get": anyApi.farmStore.getPipeline,
  "pipelines.list": anyApi.farmStore.listPipelines,
  "pipelines.update": anyApi.farmStore.updatePipeline,
  "farmerActions.create": anyApi.farmStore.createFarmerAction,
  "farmerActions.pending": anyApi.farmStore.listPendingActions,
  "farmerActions.resolve": anyApi.farmStore.resolveFarmerAction,
  "plans.create": anyApi.farmStore.createPlan,
  "plans.get": anyApi.farmStore.getPlan,
  "plans.latest": anyApi.farmStore.getLatestPlan,
  "plans.updateStatus": anyApi.farmStore.updatePlanStatus,
  "dailyBriefs.save": anyApi.farmStore.saveDailyBrief,
  "dailyBriefs.get": anyApi.farmStore.getDailyBrief,
};

const http = httpRouter();

http.route({
  path: "/store",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    const payload = (await request.json()) as {
      tenantKey?: unknown;
      operation?: unknown;
      args?: Record<string, unknown>;
    };
    const tenantKey = requireTenantKey(request, payload);
    if (!tenantKey) {
      return json({ error: "Unauthorized" }, { status: 401 });
    }
    if (typeof payload.operation !== "string") {
      return json({ error: "operation is required" }, { status: 400 });
    }

    const functionRef = functionByOperation[payload.operation];
    if (!functionRef) {
      return json({ error: `Unsupported store operation: ${payload.operation}` }, { status: 400 });
    }

    const args = { tenantKey, ...(payload.args ?? {}) };
    const result = queryOperations.has(payload.operation)
      ? await ctx.runQuery(functionRef as any, args)
      : await ctx.runMutation(functionRef as any, args);
    return json({ ok: true, result });
  }),
});

export default http;
