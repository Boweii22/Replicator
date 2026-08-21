# Architecture

```mermaid
flowchart LR
  U["Mission Control UI"] --> API["Cloud Run · API + SSE"]
  API -->|"replication.requested · IDs only"| PS[("Pub/Sub")]
  PS --> R["Reader · Gemini multimodal"]
  R --> P["Planner · ADK"]
  P --> C["Coder · ADK"]
  C --> E["Executor · heal loop"]
  E --> J["Cloud Run Jobs · sandboxed"]
  J --> V["Verifier · numeric + vision"]
  V --> O["Reporter · signed evidence graph"]
  R & P & C & E & V & O --> F[("Firestore · state + memory")]
  J & O --> G[("Cloud Storage · immutable artifacts")]
  R & P & C & E & V & O --> T["Cloud Trace + structured logs"]
  SM["Secret Manager"] -.-> C
```

Every arrow across a service boundary is replay-safe. Workers transactionally claim the event ID,
reload canonical state, perform one bounded side effect, persist its evidence, and only then emit the
next ID-only event. Experiment code never runs in an agent service.

