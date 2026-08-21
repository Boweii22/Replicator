# Security and governance

## Trust boundaries

- PDFs, paper text, repository files, README instructions, datasets, and generated code are untrusted.
- Reader prompts wrap paper content in explicit delimiters and scan for instruction override, role
  impersonation, and credential-exfiltration patterns without echoing suspicious source text to logs.
- Generated experiments execute only in Cloud Run Jobs under `replicator-runner`, never in an agent.

## Identity and access

- Pub/Sub push uses OIDC and private Cloud Run workers; only the push identity has `run.invoker`.
- The public API owns no external tokens. Runtime, builder, runner, scheduler, and push identities differ.
- Runner access is object-creation-only on the evidence bucket. It cannot read prior evidence.
- Reports use IAM `signBlob`; Google manages the private signing key.
- GitHub and Hugging Face secret containers exist in Secret Manager; values are never in Terraform or Git.

## Failure and cost containment

- User budgets cap attempts, projected cost, and job-minutes before every dispatch.
- Cloud Run platform retries are disabled for experiments so they cannot bypass Replicator accounting.
- Pub/Sub has dead-letter policies. A scheduled janitor marks stale nonterminal runs `FAILED_SYSTEM`.
- Artifact writes use generation-match/create-only semantics to prevent silent evidence replacement.

## Network posture

The current Terraform does not yet enforce VPC Service Controls or domain-restricted egress. Experiment
containers need package/dataset access during the hackathon. The documented production hardening path is
a VPC connector plus an egress proxy allowlisting PyPI, GitHub, Hugging Face, arXiv, and declared dataset
hosts. Do not claim network allowlisting is deployed until that policy is added and shown in Cloud Console.
