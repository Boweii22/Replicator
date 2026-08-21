# Replicator

**Evidence, not vibes.** Replicator is an autonomous scientific replication system: give it an arXiv
paper and a hard budget; it extracts quantitative claims, plans and runs sandboxed experiments,
self-heals failures, and returns a signed evidence graph connecting every verdict to code, logs,
metrics, figures, cost, and trace spans.

![Replicator Google Cloud architecture](docs/architecture.png)

![Replicator Mission Control release UI](docs/ui-release.png)

> Status: release candidate. The complete API → reader → planner/coder → executor/healer → verifier →
> signed reporter chain, Mission Control UI, production Google Cloud adapters, Terraform, and CI gates
> are implemented. Live paper evidence remains deliberately unclaimed until the target GCP rollout is
> explicitly authorized and observed.

## Why it matters

Reproducing one result can take a researcher days. Existing assistants can suggest code; Replicator
owns the asynchronous operational loop and is rewarded for finding honest failures. Its durable failure
memory means a broken dependency repaired for one paper becomes evidence-backed operational knowledge
for the next.

## Spin-up in 5 commands

```powershell
git clone https://github.com/Boweii22/Replicator.git replicator
cd replicator
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
.\.venv\Scripts\uvicorn services.api.main:app --reload --port 8080
```

Open `http://localhost:8080`. Use **Run evidence-backed calibration** for the local artifact-backed
calibration, or use the API docs at `/docs`. Real arXiv execution requires the cloud deployment.

## Cloud deployment

Authenticate `gcloud`, select a billed project, then run the deployment wrapper:

```powershell
.\scripts\deploy.ps1 -ProjectId YOUR_PROJECT -Region europe-west1
```

Secret *containers* are provisioned, but secret values are deliberately never handled by Terraform.
Add versions using Secret Manager after apply.

## What runs where on Google Cloud

| Component | Google Cloud product | Responsibility |
|---|---|---|
| API and agent workers | Cloud Run services | Intake, ADK decisions, SSE, verification, reporting |
| Experiment sandboxes | Cloud Run Jobs | Capped, ephemeral execution outside agent containers |
| Event backbone | Pub/Sub | IDs-only events, authenticated push, retries and dead letters |
| Canonical state and memory | Firestore | Transactional idempotency, attempts, verdicts, learned fixes |
| Evidence artifacts | Cloud Storage | PDFs, immutable code, logs, metrics, figures and reports |
| Images | Artifact Registry + Cloud Build | Reproducible service and experiment images |
| Models | Vertex AI | Gemini 3.5 Flash multimodal reasoning and structured output |
| Secrets | Secret Manager | GitHub/Hugging Face credentials; no committed keys |
| Audit trail | Cloud Trace + Cloud Logging | One trace per replication; correlated structured events |

## Safety invariants

- A verdict value must reference an actual `metrics.json` artifact.
- Pub/Sub redelivery cannot duplicate side effects: workers claim `event_id` transactionally.
- Paper and repository content are untrusted data, never instructions.
- Budgets are typed inputs and enforced before dispatch and retry.
- Experiment runners use a separate identity with object-create-only artifact access.

See [architecture decisions](docs/DECISIONS.md) and the Terraform in `infra/`.

Submission materials: [judging evidence](docs/JUDGING.md), [demo script](docs/DEMO_SCRIPT.md),
[Devpost draft](docs/DEVPOST.md), [article draft](docs/BLOG_DRAFT.md), and
[social draft](docs/SOCIAL_DRAFT.md). The locked reproduction portfolio is in
[demo papers](docs/DEMO_PAPERS.md).

## Implementation ledger

| Capability | State |
|---|---|
| API, budgets, SSE mission stream | Implemented and tested |
| Secure arXiv PDF ingestion | Implemented and tested |
| PDF text and embedded-image extraction | Implemented and tested |
| Google ADK reader + Gemini structured quantitative claims | Implemented; live Vertex proof pending |
| Budget-aware experiment planning and runner contract | Implemented and tested |
| Capped executor fail → diagnose → repair → retry loop | Implemented with runner interfaces and tests |
| Deterministic experiment bundles and Cloud Build request | Implemented and tested |
| Restricted Cloud Run Jobs adapter and Gemini code repairer | Implemented; live GCP test pending |
| Artifact-backed numerical verifier and tamper-evident reporter | Implemented and tested |
| Gemini multimodal scientific figure assessment | Implemented; live Vertex test pending |
| Evidence ledger UI and report endpoint | Implemented and tested |
| Firestore-backed cloud API and idempotent reader push worker | Implemented; live GCP test pending |
| Fresh-project Cloud Build + Terraform deployment script | Implemented; Terraform validated |
| Planner → executor → verifier → IAM-signed reporter cloud workers | Implemented and contract-tested |
| Pub/Sub failure redelivery claim release | Implemented and tested |
| Live Google Cloud deployment and captured proof | Requires target project authentication |

No row marked “next” is represented as working in the interface or submission materials.
