import hashlib
import hmac
import html
import json
import os
from urllib.parse import quote

from packages.schemas.models import Claim, Replication, ReportManifest, Verdict, VerdictStatus


def _artifact_link(replication_id: str, uri: str, index: int) -> str:
    href = f"/replications/{replication_id}/artifact?uri={quote(uri, safe='')}"
    kind = "Figure" if uri.lower().endswith((".png", ".jpg", ".jpeg", ".svg")) else "Artifact"
    return f'<a class="artifact-link" href="{href}" target="_blank">{kind} {index} <span>↗</span></a>'


def render_report(replication: Replication, claims: list[Claim], verdicts: list[Verdict]) -> str:
    by_claim = {verdict.claim_id: verdict for verdict in verdicts}
    counts = {status.value: 0 for status in VerdictStatus}
    for verdict in verdicts:
        counts[verdict.status.value] += 1
    tested = counts["REPRODUCED"] + counts["PARTIAL"] + counts["FAILED"]
    reproduced = counts["REPRODUCED"]
    headline = (
        f"{reproduced} of {tested} tested claims reproduced."
        if tested
        else "No claims were experimentally tested."
    )
    cards: list[str] = []
    figure_sections: list[str] = []
    for claim in sorted(claims, key=lambda item: item.index):
        verdict = by_claim.get(claim.id)
        status = verdict.status.value if verdict else VerdictStatus.NOT_ATTEMPTED.value
        obtained = "—" if not verdict or verdict.obtained_value is None else f"{verdict.obtained_value:g}"
        reported = "—" if claim.reported_value is None else f"{claim.reported_value:g}"
        unit = html.escape(claim.unit or "")
        reasoning = verdict.reasoning if verdict else "No completed attempt produced evidence."
        evidence = verdict.evidence_links if verdict else []
        links = "".join(_artifact_link(replication.id, uri, index + 1) for index, uri in enumerate(evidence))
        cards.append(
            f'''<article class="claim-card">
              <header><span class="claim-number">{claim.index + 1:02}</span><strong class="verdict {status.lower()}">{status.replace('_', ' ')}</strong></header>
              <h2>{html.escape(claim.text)}</h2>
              <div class="measurement"><div><span>Paper reported</span><b>{reported} {unit}</b></div><i>→</i><div><span>Replicator measured</span><b>{obtained} {unit}</b></div></div>
              <p>{html.escape(reasoning)}</p>
              <footer>{links or '<span class="no-artifact">No experimental artifact produced</span>'}</footer>
            </article>'''
        )
        reproduced_figure = next(
            (uri for uri in evidence if uri != claim.figure_gcs_uri and uri.lower().endswith((".png", ".jpg", ".jpeg"))),
            None,
        )
        if claim.figure_gcs_uri and reproduced_figure:
            paper_src = f"/replications/{replication.id}/artifact?uri={quote(claim.figure_gcs_uri, safe='')}"
            ours_src = f"/replications/{replication.id}/artifact?uri={quote(reproduced_figure, safe='')}"
            figure_sections.append(
                f'''<section class="compare"><div><span>FIGURE EVIDENCE · CLAIM {claim.index + 1:02}</span><h2>Paper figure vs. reproduced output</h2></div><div class="overlay"><img src="{paper_src}" alt="Paper figure"><img class="ours" src="{ours_src}" alt="Reproduced figure"></div><label>Overlay reproduced figure <input type="range" min="0" max="100" value="50" oninput="this.closest('.compare').style.setProperty('--mix', this.value + '%')"></label></section>'''
            )
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    trace_link = (
        f'<a href="https://console.cloud.google.com/traces/list?project={quote(project)}&tid={replication.trace_id}" target="_blank">Inspect reasoning trace ↗</a>'
        if project
        else f"Trace <code>{html.escape(replication.trace_id[:12])}</code>"
    )
    styles = """
      :root{--paper:#f3f0e8;--surface:#fffdf7;--ink:#10100f;--blue:#5546ff;--lime:#c8ff45;--amber:#ffb629;--red:#ee5353;--line:#171715;--muted:#66645e}*{box-sizing:border-box}body{margin:0;color:var(--ink);background:linear-gradient(rgba(16,16,15,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(16,16,15,.035) 1px,transparent 1px),var(--paper);background-size:30px 30px;font-family:Manrope,system-ui,sans-serif}.topbar{height:70px;padding:0 max(24px,4vw);display:flex;align-items:center;justify-content:space-between;background:rgba(243,240,232,.95);border-bottom:2px solid var(--ink)}.brand{display:flex;align-items:center;gap:10px;font-weight:800}.brand i{width:38px;height:38px;display:grid;place-items:center;color:white;background:var(--blue);border:2px solid var(--ink);border-radius:50%;font:700 16px 'DM Mono';font-style:normal}.topbar>a{padding:9px 13px;color:white;background:var(--ink);border-radius:999px;text-decoration:none;font-size:11px;font-weight:700}.wrap{width:min(1180px,calc(100% - 40px));margin:0 auto}.hero{padding:64px 0 36px}.eyebrow{color:#3527d6;font:700 10px 'DM Mono';letter-spacing:.13em}.hero h1{max-width:970px;margin:18px 0 22px;font-size:clamp(38px,5vw,68px);line-height:1;letter-spacing:-.055em}.verdict-banner{display:grid;grid-template-columns:1fr repeat(4,130px);border:2px solid var(--ink);box-shadow:7px 7px 0 var(--ink);background:var(--surface)}.verdict-banner>div{padding:20px;border-left:1.5px solid var(--ink)}.verdict-banner>div:first-child{border-left:0;background:var(--lime)}.verdict-banner span{display:block;color:var(--muted);font:700 9px 'DM Mono';letter-spacing:.07em;text-transform:uppercase}.verdict-banner b{display:block;margin-top:5px;font-size:25px}.meta{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}.meta span,.meta a{padding:9px 12px;color:var(--ink);background:var(--surface);border:1.5px solid var(--ink);border-radius:999px;text-decoration:none;font:600 10px 'DM Mono'}.section-title{display:flex;align-items:end;justify-content:space-between;margin:54px 0 18px}.section-title span,.compare>div span{color:#3527d6;font:700 10px 'DM Mono';letter-spacing:.12em}.section-title h2,.compare h2{margin:5px 0 0;font-size:28px}.claim-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.claim-card{display:flex;flex-direction:column;padding:22px;background:var(--surface);border:2px solid var(--ink);box-shadow:5px 5px 0 var(--ink)}.claim-card header{display:flex;justify-content:space-between;align-items:center}.claim-number{font:800 20px 'DM Mono'}.verdict{padding:7px 9px;border:1.5px solid var(--ink);border-radius:999px;font:700 9px 'DM Mono'}.verdict.reproduced{background:var(--lime)}.verdict.partial{background:var(--amber)}.verdict.failed{color:white;background:var(--red)}.verdict.not_attempted{background:#ddd8ce}.claim-card h2{margin:20px 0;min-height:58px;font-size:16px;line-height:1.45}.measurement{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center;padding:14px;background:#ebe7dc;border:1.5px solid var(--ink)}.measurement span{display:block;color:var(--muted);font-size:9px}.measurement b{display:block;margin-top:3px;font:700 15px 'DM Mono'}.claim-card>p{color:#494740;font-size:12px;line-height:1.55}.claim-card footer{display:flex;flex-wrap:wrap;gap:7px;margin-top:auto;padding-top:8px}.artifact-link{padding:8px 10px;color:white;background:var(--blue);border:1.5px solid var(--ink);text-decoration:none;font-size:10px;font-weight:700}.no-artifact{color:var(--muted);font-size:10px}.compare{--mix:50%;margin:50px 0;padding:26px;background:var(--surface);border:2px solid var(--ink);box-shadow:7px 7px 0 var(--ink)}.overlay{display:grid;max-width:800px;margin-top:20px;background:#ebe7dc;border:1.5px solid var(--ink)}.overlay img{grid-area:1/1;width:100%;height:auto}.overlay .ours{clip-path:inset(0 calc(100% - var(--mix)) 0 0)}.compare label{display:block;margin-top:12px;font-size:11px}.compare input{width:min(800px,100%)}.report-footer{margin-top:60px;padding:30px 0 50px;border-top:2px solid var(--ink);display:flex;justify-content:space-between;color:var(--muted);font:9px 'DM Mono'}@media(max-width:850px){.verdict-banner{grid-template-columns:1fr 1fr}.verdict-banner>div:first-child{grid-column:1/-1}.claim-grid{grid-template-columns:1fr}}@media(max-width:520px){.verdict-banner{grid-template-columns:1fr 1fr}.hero{padding-top:38px}.claim-card{padding:16px}.measurement{grid-template-columns:1fr}.measurement>i{display:none}.report-footer{display:grid;gap:10px}}
    """
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Replicator evidence report</title><link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;600;700;800&display=swap" rel="stylesheet"><style>{styles}</style></head><body><header class="topbar"><div class="brand"><i>R</i>Replicator <small>/ EVIDENCE REPORT</small></div><a href="/?run={replication.id}">Return to mission</a></header><main class="wrap"><section class="hero"><span class="eyebrow">SIGNED REPLICATION OUTCOME</span><h1>{html.escape(replication.title or 'Untitled paper')}</h1><div class="verdict-banner"><div><span>Outcome</span><b>{headline}</b></div><div><span>Reproduced</span><b>{reproduced}</b></div><div><span>Partial</span><b>{counts['PARTIAL']}</b></div><div><span>Failed</span><b>{counts['FAILED']}</b></div><div><span>Not attempted</span><b>{counts['NOT_ATTEMPTED']}</b></div></div><div class="meta"><span>Run {html.escape(replication.id[:10].upper())}</span><span>${replication.spent.usd:.2f} accounted</span><span>{replication.spent.job_minutes:.1f} job-minutes</span>{trace_link}</div></section><section><div class="section-title"><div><span>CLAIM-BY-CLAIM EVIDENCE</span><h2>What held up—and what did not.</h2></div><b>{len(claims)} claims</b></div><div class="claim-grid">{''.join(cards)}</div></section>{''.join(figure_sections)}<footer class="report-footer"><span>Generated by Replicator · Evidence, not vibes.</span><span>Run {html.escape(replication.id)}</span></footer></main></body></html>'''


def create_manifest(
    replication_id: str, report: bytes, verdicts: list[Verdict], signing_key: bytes | None = None
) -> ReportManifest:
    manifest = ReportManifest(
        replication_id=replication_id,
        report_sha256=hashlib.sha256(report).hexdigest(),
        verdict_ids=sorted(verdict.id for verdict in verdicts),
        evidence_uris=sorted({uri for verdict in verdicts for uri in verdict.evidence_links}),
    )
    if signing_key:
        canonical = json.dumps(manifest.model_dump(mode="json"), sort_keys=True).encode()
        manifest.signature = hmac.new(signing_key, canonical, hashlib.sha256).hexdigest()
        manifest.signature_algorithm = "HMAC-SHA256"
    return manifest


def render_badge(reproduced: int, total: int) -> str:
    label = html.escape(f"Replicator: {reproduced}/{total} claims reproduced")
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="280" height="28" role="img" aria-label="{label}"><rect width="280" height="28" rx="4" fill="#10100f"/><text x="12" y="19" fill="#c8ff45" font-family="monospace" font-size="12">{label}</text></svg>'
