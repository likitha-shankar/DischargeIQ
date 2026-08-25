#!/usr/bin/env python3
"""
scripts/build_demo_fallback.py

Builds a self-contained offline fallback for the demo. Owner: Likitha Shankar.

WHY THIS EXISTS
---------------
Vertex serves Gemini through dynamic shared quota, which has no reserved
capacity and no reset window: a 429 during a live demo is possible at any
moment and nothing we do prevents it. docs/DEMO_SCRIPT.md already warns that a
single analysis needs six calls in a row.

So this renders pipeline outputs that were generated EARLIER, while capacity
was available, into one HTML file that needs no backend, no network and no
API key. If the live path 429s mid-demo, open the file and keep talking.

It is a fallback, not a fake. Every word in the output came from a real
pipeline run against the committed demo fixture, and the page says so on its
face, with the generation timestamp, so nobody can mistake it for a live
result.

Usage:
    python scripts/build_demo_fallback.py
    python scripts/build_demo_fallback.py --out docs/demo_fallback.html

Reads evaluation/corpus_outputs/*.json. Makes NO API calls.
"""

import argparse
import html
import json
import re
from datetime import date
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]

# Tab order and labels exactly as the app shows them. The demo script walks
# these in order, so a fallback in a different order would trip up the
# presenter mid-sentence.
_TABS = [
    ("What happened", "diagnosis_explanation"),
    ("Medications", "medication_rationale"),
    ("Appointments", "_appointments"),
    ("Warning signs", "escalation_guide"),
    ("Recovery", "recovery_trajectory"),
    ("Discharge Check", "_simulator"),
]

# Fixtures worth including, in demo order. Names match the demo script table.
_FIXTURES = ["heart_failure_01", "copd_01", "hip_replacement_01"]


def _esc(text) -> str:
    """HTML-escape any value, including None."""
    return html.escape(str(text or ""))


def _render_text(raw: str) -> str:
    """
    Render an agent's plain-text output as HTML.

    Agents emit plain text with "- " bullets and "**Week 1:**" headers. This
    preserves that structure rather than dumping a <pre> block, because the
    fallback has to look like the product during a demo, not like a log file.

    Args:
        raw: The agent's text output.

    Returns:
        HTML fragment.
    """
    out, in_list = [], False
    for line in str(raw or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        header = re.match(r"^\*\*(.+?)\*\*:?$", stripped)
        tier = stripped in ("CALL 911 IMMEDIATELY", "GO TO THE ER TODAY",
                            "CALL YOUR DOCTOR")
        if header or tier:
            if in_list:
                out.append("</ul>")
                in_list = False
            label = header.group(1) if header else stripped
            css = "tier" if tier else "wk"
            out.append(f'<h3 class="{css}">{_esc(label)}</h3>')
            continue
        if stripped.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_esc(stripped[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        out.append(f"<p>{_esc(stripped)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _render_appointments(extraction: dict) -> str:
    """Render the follow-up list, or say plainly that the document had none."""
    appointments = extraction.get("follow_up_appointments") or []
    if not appointments:
        return ('<p class="empty">This discharge document did not list any '
                "follow-up appointments.</p>")
    rows = []
    for appointment in appointments:
        who = _esc(appointment.get("provider") or appointment.get("specialty") or "Provider")
        when = _esc(appointment.get("date") or "Date not given")
        why = _esc(appointment.get("reason") or "")
        rows.append(f"<tr><td><strong>{who}</strong></td><td>{when}</td><td>{why}</td></tr>")
    return ("<table><thead><tr><th>Who</th><th>When</th><th>Why</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def _render_simulator(output: dict) -> str:
    """Render the Discharge Check tab: gap score and missed concepts."""
    sim = output.get("patient_simulator") or {}
    if not sim:
        return '<p class="empty">Discharge Check did not run for this document.</p>'
    score = sim.get("overall_gap_score", 0)
    parts = [
        '<p class="notice">These are questions a patient might ask that this '
        "document does not answer. They are for discussion with a care team, "
        "not medical advice.</p>",
        f'<p class="score">Gap score: <strong>{_esc(score)}</strong> out of 10 '
        "<span>(higher means more unanswered questions)</span></p>",
        f"<p>{_esc(sim.get('simulator_summary'))}</p>",
    ]
    unanswered = [c for c in sim.get("missed_concepts") or []
                  if not c.get("answered_by_doc")]
    if unanswered:
        parts.append("<h3>Not answered by this document</h3>")
        for concept in unanswered:
            sev = _esc(concept.get("severity") or "minor")
            parts.append(
                f'<div class="gap {sev}"><span class="sev">{sev}</span>'
                f"<strong>{_esc(concept.get('question'))}</strong>"
                f"<p>{_esc(concept.get('gap_summary'))}</p></div>"
            )
    return "\n".join(parts)


def _render_case(stem: str, output: dict) -> str:
    """Render one fixture as a tabbed panel."""
    extraction = output.get("extraction") or {}
    meta = output.get("_review_meta") or {}
    diagnosis = _esc(extraction.get("primary_diagnosis") or stem)
    generated = _esc(meta.get("generated_at") or "unknown")
    status = _esc(output.get("pipeline_status"))

    tabs, panels = [], []
    for index, (label, key) in enumerate(_TABS):
        active = " active" if index == 0 else ""
        tabs.append(f'<button class="tab{active}" data-target="{stem}-{index}">'
                    f"{_esc(label)}</button>")
        if key == "_appointments":
            body = _render_appointments(extraction)
        elif key == "_simulator":
            body = _render_simulator(output)
        else:
            body = _render_text(output.get(key))
        panels.append(f'<section class="panel{active}" id="{stem}-{index}">{body}</section>')

    fk = output.get("fk_scores") or {}
    grades = ", ".join(f"{a}: {(v or {}).get('fk_grade')}" for a, v in sorted(fk.items()))
    return f"""
<article class="case" id="case-{stem}">
  <header>
    <h2>{diagnosis}</h2>
    <p class="meta">Fixture <code>{_esc(stem)}.pdf</code> &middot;
       pipeline status <code>{status}</code> &middot;
       generated {generated}</p>
    <p class="meta">Readability (Flesch-Kincaid grade): {_esc(grades)}</p>
  </header>
  <nav class="tabs">{''.join(tabs)}</nav>
  {''.join(panels)}
</article>"""


_CSS = """
:root{--bg:#ffffff;--fg:#12211c;--muted:#5c6f68;--line:#dbe5e0;--teal:#1FA47F;
--card:#f6faf8;--crit:#b3261e;--mod:#a06000;--min:#3a6b5c;}
:root:not([data-theme="light"]){}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
--bg:#0d1512;--fg:#e6efe9;--muted:#9fb3aa;--line:#26332e;--teal:#5DCAA5;
--card:#131e1a;--crit:#f2b8b5;--mod:#e6c07a;--min:#8fd3bb;}}
:root[data-theme="dark"]{--bg:#0d1512;--fg:#e6efe9;--muted:#9fb3aa;--line:#26332e;
--teal:#5DCAA5;--card:#131e1a;--crit:#f2b8b5;--mod:#e6c07a;--min:#8fd3bb;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}
.wrap{max-width:900px;margin:0 auto;padding:24px 20px 64px}
.banner{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--teal);
border-radius:8px;padding:14px 16px;margin-bottom:24px}
.banner strong{color:var(--teal)}
h1{font-size:1.6rem;margin:0 0 4px}
h2{font-size:1.3rem;margin:0 0 4px}
h3{font-size:1rem;margin:20px 0 8px}
h3.tier{color:var(--teal);letter-spacing:.04em}
h3.wk{color:var(--fg)}
.meta{color:var(--muted);font-size:.85rem;margin:2px 0}
.case{border:1px solid var(--line);border-radius:10px;padding:18px;margin-bottom:28px;
background:var(--card)}
.tabs{display:flex;flex-wrap:wrap;gap:6px;margin:16px 0;border-bottom:1px solid var(--line);
padding-bottom:8px}
.tab{background:none;border:1px solid var(--line);color:var(--muted);cursor:pointer;
padding:6px 12px;border-radius:999px;font-size:.85rem;font-family:inherit}
.tab.active{background:var(--teal);color:#fff;border-color:var(--teal)}
.panel{display:none}
.panel.active{display:block}
ul{padding-left:20px;margin:8px 0}
li{margin:4px 0}
table{width:100%;border-collapse:collapse;font-size:.92rem;display:block;overflow-x:auto}
th,td{text-align:left;padding:8px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600}
.notice{background:var(--bg);border:1px solid var(--line);border-radius:8px;
padding:10px 12px;font-size:.88rem;color:var(--muted)}
.score{font-size:1.05rem}
.score span{color:var(--muted);font-size:.85rem;font-weight:400}
.gap{border-left:3px solid var(--line);padding:8px 12px;margin:10px 0;background:var(--bg);
border-radius:0 6px 6px 0}
.gap .sev{display:inline-block;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;
margin-bottom:4px}
.gap.critical{border-left-color:var(--crit)} .gap.critical .sev{color:var(--crit)}
.gap.moderate{border-left-color:var(--mod)} .gap.moderate .sev{color:var(--mod)}
.gap.minor{border-left-color:var(--min)} .gap.minor .sev{color:var(--min)}
.gap p{margin:4px 0 0;font-size:.92rem}
.empty{color:var(--muted);font-style:italic}
code{font-size:.85em;background:var(--bg);padding:1px 5px;border-radius:4px;
border:1px solid var(--line)}
"""

_JS = """
document.querySelectorAll('.tabs').forEach(function(nav){
  nav.addEventListener('click', function(e){
    var btn = e.target.closest('.tab'); if(!btn) return;
    var card = nav.closest('.case');
    card.querySelectorAll('.tab').forEach(function(b){b.classList.remove('active');});
    card.querySelectorAll('.panel').forEach(function(p){p.classList.remove('active');});
    btn.classList.add('active');
    var panel = document.getElementById(btn.dataset.target);
    if(panel) panel.classList.add('active');
  });
});
"""


def build(outputs_dir: Path) -> str:
    """
    Assemble the fallback page from whatever fixtures have saved outputs.

    Args:
        outputs_dir: Directory holding pipeline output JSON.

    Returns:
        A complete HTML document as a string.

    Note:
        Missing fixtures are skipped and listed on the page rather than
        silently omitted. A presenter needs to know what is NOT in their
        safety net before they are standing in front of people.
    """
    cases, missing = [], []
    for stem in _FIXTURES:
        path = outputs_dir / f"{stem}.json"
        if not path.exists():
            missing.append(stem)
            continue
        output = json.load(open(path))
        if output.get("pipeline_status") in (None, "partial", "rejected"):
            missing.append(f"{stem} ({output.get('pipeline_status')})")
            continue
        cases.append(_render_case(stem, output))

    warn = ""
    if missing:
        warn = ('<p class="meta">Not included (no clean output on disk): '
                f"{_esc(', '.join(missing))}. Regenerate with "
                "<code>scripts/run_corpus_for_review.py</code> while quota "
                "allows.</p>")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DischargeIQ Demo Fallback</title><style>{_CSS}</style></head>
<body><div class="wrap">
<div class="banner">
  <strong>Offline demo fallback.</strong> Real pipeline output, captured
  earlier and rendered from saved JSON. No backend, no network, no API key.
  Use this if a live analysis returns 429 mid-demo: Vertex serves Gemini on
  dynamic shared quota, so capacity is never guaranteed.
  <span class="meta">Built {date.today().isoformat()}.</span>
</div>
<h1>DischargeIQ</h1>
<p class="meta">Generated demo fixtures. No real or program-provided patient
data appears here.</p>
{warn}
{''.join(cases)}
</div><script>{_JS}</script></body></html>"""


def main() -> None:
    """Write the fallback page next to the demo script."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", type=Path,
                        default=_REPO / "evaluation" / "corpus_outputs")
    parser.add_argument("--out", type=Path,
                        default=_REPO / "docs" / "demo_fallback.html")
    args = parser.parse_args()

    page = build(args.outputs)
    args.out.write_text(page, encoding="utf-8")
    print(f"wrote {args.out} ({len(page) // 1024} KB)")
    print("Open it directly in a browser. It needs nothing else.")


if __name__ == "__main__":
    main()
