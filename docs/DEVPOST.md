# Devpost submission draft

## Project name

Replicator — Evidence, not vibes.

## Elevator pitch

Replicator is an autonomous multi-agent system that takes an arXiv paper and a hard budget, rebuilds
its quantitative experiments in sandboxed Google Cloud jobs, heals failures, and returns an IAM-signed
evidence report connecting every verdict to code, logs, metrics, figures, cost, and trace spans.

## The problem

Scientific results are expensive to check and cheap to repeat. Researchers lose days locating code,
repairing environments, downloading datasets, and reconciling reported values. General AI assistants
can suggest steps but do not own the asynchronous operational loop or prove where a number came from.

## What it does

Replicator reads paper text and figures with Gemini, extracts quantitative claims, creates a budgeted
experiment plan, generates a contract-bound repository, builds it with Cloud Build, and runs it as a
restricted Cloud Run Job. It diagnoses failures, retries within explicit caps, remembers successful
repairs, verifies numeric and visual evidence, and generates a signed report. A live mission-control UI
shows every autonomous decision and artifact as it happens.

## Google technology

Gemini 3.5 Flash on Vertex AI; Google ADK; Cloud Run services and jobs; Pub/Sub; Firestore; Cloud Storage;
Cloud Build; Artifact Registry; Secret Manager; IAM Credentials; Cloud Trace and Cloud Logging.

## Findings and learnings

Autonomy without evidence makes scientific agents less trustworthy. The strongest design choice was to
make artifacts—not model prose—the source of verdict values. At-least-once delivery, explicit budgets,
separate runner identities, and honest `FAILED` results turned out to be product features, not plumbing.

## Required links before submission

- Hosted project: `TODO_AFTER_DEPLOYMENT`
- Repository: https://github.com/Boweii22/Replicator
- Demo video: `TODO_AFTER_RECORDING`
- Public build article: `TODO_AFTER_PUBLISHING`
- Social post: `TODO_AFTER_POSTING`
