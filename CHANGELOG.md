# Changelog

## 0.1.0-alpha

- verified the real Hermes connector path with an end-to-end smoke run that creates a farm, records an observation, generates a morning brief, and searches knowledge
- added Hermes-compatible tool wrappers so plugin tools work when Hermes injects metadata like `task_id`
- implemented recurring morning-brief scheduling with `apscheduler` and runtime wiring for farm bootstrap and delivery injection
- changed seed knowledge loading to bootstrap automatically on first run, with explicit skip and reload controls through `OPENPASTURE_LOAD_SEED`
- hardened the alpha runtime around missing `FIRECRAWL_API_KEY`, weather API failures, and clearer session-time notices for incomplete configuration
- updated self-hosting and README docs to reflect the current alpha workflow, included skills, and known limitations
- documented the OSS/cloud repository boundary, current cloud handoff baseline, and maintainer validation expectations
