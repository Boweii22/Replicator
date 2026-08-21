# Judging evidence matrix

## Innovation & operational utility — 40%

- The agent completes an asynchronous scientific replication workflow rather than returning advice.
- It extracts claims, plans within a user budget, generates runnable code, builds an image, launches a
  restricted job, verifies artifacts, and publishes a report without follow-up prompts.
- Failed attempts are useful output. Stable error signatures become cross-replication repair memory.
- `services/demo.py` proves the complete evidence path locally using a real calculation and artifact.

## Architectural discipline — 30%

- IDs-only Pub/Sub events; Firestore is canonical state.
- Transactional event claims plus failure release make at-least-once delivery recoverable.
- Agent services never execute generated scientific code. Cloud Run Jobs use a separate identity.
- Budget checks execute before dispatch. Platform retries are disabled so attempts cannot evade caps.
- Reports are signed with a Google-managed service-account key through IAM Credentials.
- Paper/repository text is delimited, scanned, escaped, and treated as untrusted input.
- Dead-letter policy and a scheduled janitor resolve poisoned messages and stalled runs.

## Demo & production readiness — 30%

- `scripts/run_local.ps1` starts the complete local calibration experience.
- `scripts/deploy.sh` bootstraps and deploys a fresh GCP project.
- `docs/architecture.png` is the submission architecture asset.
- The live dashboard exposes agent decisions, constraints, evidence, and final report.
- Automated tests cover contracts, redelivery, budget enforcement, healing, signing, and reporting.

## Claims we must not make before deployment

- Do not claim a real arXiv result was reproduced until its GCS metrics and report exist.
- Do not claim the Terraform deployment was verified until `scripts/deploy.sh` succeeds in the target project.
- Do not claim Gemini/ADK live calls were observed until Vertex logs and Cloud Trace are captured.
