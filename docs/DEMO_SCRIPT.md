# Four-minute demo script

## 0:00–0:30 — The problem

“A paper can publish in minutes and take a researcher a week to check. Replicator turns scientific
claims into background jobs and returns evidence—not a confident paragraph.” Show the mission-control
home screen and the fail-closed label.

## 0:30–1:05 — Start

Paste the locked demo paper URL, set attempts/time/cost, and start. Say that messages contain IDs only;
Firestore owns state. Briefly show the `.run.app` URL and Cloud Run service in Google Cloud Console.

## 1:05–2:15 — Autonomous action

Follow the live decision stream: reader extracts claims and figures; planner chooses a bounded strategy;
coder emits an immutable source hash; Cloud Build creates the experiment; executor launches a restricted
Cloud Run Job. Show one genuine dependency failure, its error signature, diagnosis, patch, and retry.

## 2:15–3:15 — Evidence

Open the evidence ledger. For each claim, show paper value, obtained value, tolerance, verdict, metrics,
logs, and figure comparison. Open the IAM-signed report manifest and Cloud Trace correlation.

## 3:15–3:45 — Memory and production architecture

Show the repair-memory entry and the architecture PNG. Explain OIDC push, separate runner identity,
budget enforcement, dead letters, and the scheduled janitor.

## 3:45–4:00 — Close

“Replicator does not make science look reproducible. It makes reproducibility inspectable.” Show total
cost/runtime and the signed badge.

## Recording checklist

- One continuous take; browser clock visible.
- Show `.run.app`, Cloud Run execution, Vertex model log, GCS metrics, and Cloud Trace.
- Never use the calibration fixture as proof of reproducing a published paper.
