import hashlib
import hmac
import html
import json

from packages.schemas.models import Claim, ReportManifest, Replication, Verdict, VerdictStatus


def render_report(replication: Replication, claims: list[Claim], verdicts: list[Verdict]) -> str:
    by_claim = {v.claim_id: v for v in verdicts}
    rows = []
    for claim in sorted(claims, key=lambda c: c.index):
        verdict = by_claim.get(claim.id)
        status = verdict.status if verdict else VerdictStatus.NOT_ATTEMPTED
        obtained = "—" if not verdict or verdict.obtained_value is None else f"{verdict.obtained_value:g}"
        reasoning = verdict.reasoning if verdict else "No completed attempt produced evidence."
        links = " ".join(f'<a href="{html.escape(uri, quote=True)}">artifact</a>' for uri in (verdict.evidence_links if verdict else []))
        rows.append(f"<tr><td>{claim.index + 1}</td><td>{html.escape(claim.text)}</td><td>{claim.reported_value if claim.reported_value is not None else '—'}</td><td>{obtained}</td><td><strong>{status}</strong></td><td>{html.escape(reasoning)}</td><td>{links}</td></tr>")
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>Replication report</title><style>body{{font:15px system-ui;max-width:1200px;margin:40px auto;color:#142019}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccd7d0;padding:10px;text-align:left;vertical-align:top}}th{{background:#eaf5ee}}</style></head><body><p>REPLICATOR / EVIDENCE REPORT</p><h1>{html.escape(replication.title or "Untitled paper")}</h1><p>Run <code>{html.escape(replication.id)}</code> · Spend ${replication.spent.usd:.2f} · {replication.spent.job_minutes:.1f} job-minutes</p><table><thead><tr><th>#</th><th>Claim</th><th>Paper</th><th>Obtained</th><th>Verdict</th><th>Reasoning</th><th>Evidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table></body></html>'''


def create_manifest(replication_id: str, report: bytes, verdicts: list[Verdict], signing_key: bytes | None = None) -> ReportManifest:
    manifest = ReportManifest(replication_id=replication_id,
        report_sha256=hashlib.sha256(report).hexdigest(),
        verdict_ids=sorted(v.id for v in verdicts),
        evidence_uris=sorted({uri for v in verdicts for uri in v.evidence_links}))
    if signing_key:
        canonical = json.dumps(manifest.model_dump(mode="json"), sort_keys=True).encode()
        manifest.signature = hmac.new(signing_key, canonical, hashlib.sha256).hexdigest()
        manifest.signature_algorithm = "HMAC-SHA256"
    return manifest


def render_badge(reproduced: int, total: int) -> str:
    label = html.escape(f"Replicator: {reproduced}/{total} claims reproduced")
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="280" height="28" role="img" aria-label="{label}"><rect width="280" height="28" rx="4" fill="#0b1713"/><text x="12" y="19" fill="#baff35" font-family="monospace" font-size="12">{label}</text></svg>'
