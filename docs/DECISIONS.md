# Architecture decisions

## ADR-001 — IDs-only messages

Pub/Sub messages contain entity IDs and trace context, never mutable entity bodies. A worker reads
canonical state from Firestore and claims `event_id` in a transaction before side effects. This makes
redelivery safe and keeps Firestore the source of truth.

## ADR-002 — Configurable Gemini model ID

The deployment default is `gemini-3.5-flash`, matching the event requirement. `MODEL_ID` is a deploy
input because Vertex model aliases and allowlists change. The application must log the resolved model
on every span and report; it may never silently fall back to a different model.

## ADR-003 — Honest local mode

Local mode exercises orchestration contracts but labels agent output `local-contract`; it does not
pretend to have extracted or reproduced a claim. Only artifacts produced by a successful experiment
job may populate an obtained value or a `REPRODUCED` verdict.

## ADR-004 — Coder invocation

The coder is a separately packaged ADK agent invoked by planner and executor work. It is not subscribed
to an extra public topic in the required topic list. This preserves the prescribed topology while
keeping attempts and patches addressable and independently traceable.

