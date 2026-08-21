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
experiment plan, generates a contract-bound repository, validates it before build, builds it with Cloud
Build, and runs it as a restricted Cloud Run Job. It diagnoses failures, retries within explicit caps,
remembers repairs, verifies numeric and visual evidence, and generates a signed report. A live
mission-control UI shows every autonomous decision and artifact as it happens.

## Google technology

Gemini 3.5 Flash on Vertex AI; Google ADK; Cloud Run services and jobs; Pub/Sub; Firestore; Cloud Storage;
Cloud Build; Artifact Registry; Container Analysis; Secret Manager; IAM Credentials; Cloud Trace and
Cloud Logging.

## Live evidence

- Hosted project: https://replicator-api-821279770160.europe-west1.run.app
- Successful end-to-end sandbox run: `85f4fdf96b874bd19e3ba2053d3fde98`
- Signed report: https://replicator-api-821279770160.europe-west1.run.app/replications/85f4fdf96b874bd19e3ba2053d3fde98/report
- Trace ID: `4976c9c3f9df40d895a5a078a13d218c`
- Verified experiment image: `sha256:00a015e7053cfd92a4794803613110bbd28e675278b7e6f301fc08aaa63c8e86`
- Cloud Run execution: `rep-85f4fdf9-881c97ef-t8hjl` (completed successfully in 54.31 seconds)
- Accounted mission spend: `$0.10`; job runtime: `1.48 minutes`
- Honest scientific result: `0/8 claims reproduced`; every failed verdict links to generated code,
  stdout, and measured metrics rather than fabricated evidence.
- Autonomous recovery evidence: run `7a25f948740e40edaf7bc5b5d7d195b3` captured invalid dataset
  responses and an invalid generated script, then motivated the deployed pre-build syntax and source
  policy gate.

## Findings and learnings

Autonomy without evidence makes scientific agents less trustworthy. The strongest design choice was to
make artifacts—not model prose—the source of verdict values. At-least-once delivery, explicit budgets,
separate runner identities, pre-build source validation, and honest `FAILED` results are product
features, not plumbing. A scientifically negative verdict can still prove the autonomous system works.

## Submission links

- Repository: https://github.com/Boweii22/Replicator
- Demo video: record and upload before submission
- Public build article: publish from `docs/BLOG_DRAFT.md`
- Social post: publish from `docs/SOCIAL_DRAFT.md`
