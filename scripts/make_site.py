"""Build the static leaderboard page (docs/index.html) from one or more results directories.

Usage: uv run python scripts/make_site.py docs/index.html results/v0.3-sonnet results/v0.3-haiku results/v0.2

The first directory after the output path is the featured result; later ones follow in order.

The page only restates what is already in the repo: summary.json and the raw records.
Raw-data links point at the files in the GitHub repository; nothing is copied.
"""

from __future__ import annotations

import collections
import html
import json
import sys
from pathlib import Path

REPO = "https://github.com/bishtashish708/tokentrial"
BRANCH = "main"

ARM_INFO = {
    "baseline": ("Unmodified Claude Code", "reference"),
    "noop": ("Control: same install steps, changes nothing", "control"),
    "noop-hook": ("Control: a do-nothing SessionStart hook", "control"),
    "rtk": ("rtk v1.1.0: compresses shell command output", "tool"),
    "caveman": ("caveman v4.0.1: terse-answer plugin", "tool"),
    "noop-baseurl": ("Control: ANTHROPIC_BASE_URL set to Anthropic's URL", "control"),
    "headroom-passthrough": ("Control: headroom proxy with optimization off", "control"),
    "rtk-v1.2.0": ("rtk v1.2.0: compresses shell command output", "tool"),
    "caveman-v4.1.0": ("caveman v4.1.0: terse-answer plugin", "tool"),
    "headroom": ("headroom 0.42.0: context-compression proxy", "tool"),
}
ARM_ORDER = [
    "baseline",
    "noop",
    "noop-hook",
    "noop-baseurl",
    "headroom-passthrough",
    "rtk",
    "rtk-v1.2.0",
    "caveman",
    "caveman-v4.1.0",
    "headroom",
]


def pct(x: float) -> str:
    v = round(x * 100)
    return f"{'+' if v > 0 else '−' if v < 0 else '±'}{abs(v)}%"


def usd(x: float) -> str:
    return f"${x:.4f}"


def load(results: Path) -> tuple[dict, dict]:
    summary = json.loads((results / "summary.json").read_text())
    versions: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    meta = collections.Counter()
    for line in (results / "raw" / "records.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        versions[r["arm"]][r.get("arm_version") or "—"] += 1
        init = r.get("claude_init") or {}
        meta[("claude_code", init.get("claude_code_version"))] += 1
        meta[("date", (r.get("started_at") or "")[:10])] += 1
    info = {
        "arm_versions": {a: ", ".join(sorted(c)) for a, c in versions.items()},
        "claude_code": sorted({v for (k, v) in meta if k == "claude_code" and v}),
        "dates": sorted({v for (k, v) in meta if k == "date" and v}),
    }
    return summary, info


def forest_svg(arms: dict, sid: str) -> str:
    """Relative cost per solved task vs baseline, with 95% CIs."""
    rows = [a for a in ARM_ORDER if a in arms and "vs_baseline" in arms[a]]
    lo, hi = -0.4, 0.7
    w, left, right, row_h, top = 640, 110, 20, 34, 28
    h = top + row_h * len(rows) + 30
    span = w - left - right

    def x(v: float) -> float:
        return left + (max(lo, min(hi, v)) - lo) / (hi - lo) * span

    out = [
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="fp-{sid}" class="forest">',
        f'<title id="fp-{sid}">Cost per solved task relative to baseline, with 95% confidence intervals</title>',
    ]
    nf = arms.get("noop", {}).get("vs_baseline")
    if nf:
        a, b = nf["ci95"]
        out.append(
            f'<rect x="{x(a):.1f}" y="{top - 8}" width="{x(b) - x(a):.1f}" '
            f'height="{row_h * len(rows) + 4}" class="band"><title>Noise floor: noop vs baseline CI</title></rect>'
        )
    for t in (-0.4, -0.2, 0, 0.2, 0.4, 0.6):
        out.append(
            f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{top - 10}" y2="{h - 22}" '
            f'class="{"zero" if t == 0 else "grid"}"/>'
        )
        out.append(f'<text x="{x(t):.1f}" y="{h - 6}" class="tick">{pct(t)}</text>')
    for i, a in enumerate(rows):
        y = top + i * row_h + row_h / 2 - 6
        v = arms[a]["vs_baseline"]
        c1, c2 = v["ci95"]
        kind = ARM_INFO.get(a, ("", "tool"))[1]
        out.append(f'<text x="{left - 12}" y="{y + 4}" class="label">{html.escape(a)}</text>')
        out.append(f'<line x1="{x(c1):.1f}" x2="{x(c2):.1f}" y1="{y}" y2="{y}" class="ci {kind}"/>')
        out.append(
            f'<circle cx="{x(v["point"]):.1f}" cy="{y}" r="5" class="pt {kind}">'
            f"<title>{html.escape(a)}: {pct(v['point'])} ({pct(c1)} to {pct(c2)})</title></circle>"
        )
    out.append("</svg>")
    return "\n".join(out)


FINDINGS = f"{REPO}/blob/{BRANCH}/results/v0.3/FINDINGS.md"
FINDINGS_V02 = f"{REPO}/blob/{BRANCH}/results/v0.2/FINDINGS.md"


def section(results: Path, featured: bool) -> str:
    summary, info = load(results)
    arms = summary["arms"]
    m = summary["manifest"]
    name = m.get("name", results.name)
    sid = name.replace("/", "-").replace(".", "")
    rel = results.as_posix()
    blob = f"{REPO}/blob/{BRANCH}/{rel}"
    raw_tree = f"{REPO}/tree/{BRANCH}/{rel}/raw"
    total_runs = summary["n_records"]
    total_solved = sum(a["solved"] for a in arms.values())
    total_cost = sum(a["mean_cost_per_run"] * a["runs"] for a in arms.values())

    rows = []
    for a in ARM_ORDER:
        if a not in arms:
            continue
        s = arms[a]
        desc, kind = ARM_INFO.get(a, (a, "tool"))
        c1, c2 = s["cost_per_solved_ci95"]

        def rel_cell(key: str, s=s, label: str = "") -> str:
            if key not in s:
                return '<td class="num muted">—</td>'
            v = s[key]
            pre = f'<code class="ctl">{html.escape(label)}</code> ' if label else ""
            return (
                f'<td class="num">{pre}{pct(v["point"])} '
                f'<span class="ci">({pct(v["ci95"][0])} to {pct(v["ci95"][1])})</span></td>'
            )

        verdict = s.get("verdict", "control" if kind == "control" else "reference")
        rows.append(
            f'<tr class="{kind}"><th scope="row"><code>{html.escape(a)}</code><div class="desc">{html.escape(desc)}</div></th>'
            f'<td class="num">{s["solved"]}/{s["runs"]}</td>'
            f'<td class="num">{usd(s["cost_per_solved"])} <span class="ci">({usd(c1)}–{usd(c2)})</span></td>'
            f"{rel_cell('vs_baseline')}{rel_cell('vs_matched_control', label=s.get('matched_control') or '')}"
            f'<td class="verdict">{html.escape(verdict)}</td></tr>'
        )

    nf = summary["noise_floor_noop_vs_baseline"]
    dates = ", ".join(info["dates"])
    cc = ", ".join(info["claude_code"])
    tag = "h2" if featured else "h3"
    return f"""
<section id="{sid}">
<{tag}><code>{html.escape(name)}</code>: <code>{html.escape(m["model"])}</code></{tag}>
<div class="facts">
  <span><b>Date</b> {html.escape(dates)}</span>
  <span><b>Agent</b> Claude Code {html.escape(cc)}, headless</span>
  <span><b>Design</b> {len(m["task_ids"])} tasks × {len(m["arms"])} arms × {m["repeats"]} repeats = {total_runs} runs</span>
  <span><b>Solved</b> {total_solved}/{total_runs}</span>
  <span><b>Total cost</b> ${total_cost:.2f} API-equivalent</span>
</div>
<div class="scroll">
<table>
<thead><tr><th>Arm</th><th>Solved</th><th>Cost per solved task (95% CI)</th>
<th>vs <code>baseline</code></th><th>vs matched control</th><th>Verdict</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
</div>
<p class="note">Noise floor (<code>noop</code> vs <code>baseline</code>): {pct(nf["point"])}
({pct(nf["ci95"][0])} to {pct(nf["ci95"][1])}).</p>
{forest_svg(arms, sid)}
<p class="note">Relative to baseline. Dots are point estimates, lines 95% CIs, the shaded band the noise floor.
Data: <a href="{blob}/summary.md">summary.md</a> · <a href="{blob}/summary.json">summary.json</a> ·
<a href="{raw_tree}">raw records and transcripts</a> (home path and username scrubbed).</p>
</section>"""


STYLE = """
:root {
  --bg:#fbfbfa; --fg:#1d1d1b; --muted:#6b6b66; --line:#e4e3df; --card:#ffffff;
  --tool:#2f5fb3; --control:#8a8a84; --ref:#1d1d1b; --band:rgba(138,138,132,.13); --accent:#2f5fb3;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root { --bg:#161615; --fg:#ecebe7; --muted:#9b9a94; --line:#2e2e2b; --card:#1d1d1b;
    --tool:#7aa2e8; --control:#8a8a84; --ref:#ecebe7; --band:rgba(160,160,152,.14); --accent:#7aa2e8;
    color-scheme: dark; }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }
main { max-width:1040px; margin:0 auto; padding:40px 20px 64px; }
h1 { font-size:28px; margin:0 0 4px; letter-spacing:-.01em; }
h2 { font-size:19px; margin:44px 0 12px; }
h3 { font-size:16px; margin:36px 0 10px; }
.sub { color:var(--muted); margin:0 0 24px; }
a { color:var(--accent); }
code { font:13px ui-monospace,SFMono-Regular,Menlo,monospace; }
code.ctl { color:var(--muted); font-size:12px; }
.facts { display:flex; flex-wrap:wrap; gap:8px 24px; padding:14px 16px; border:1px solid var(--line);
  border-radius:8px; background:var(--card); font-size:14px; margin-bottom:12px; }
.facts b { font-weight:600; }
.scroll { overflow-x:auto; border:1px solid var(--line); border-radius:8px; background:var(--card); }
table { border-collapse:collapse; width:100%; min-width:860px; font-size:14px; }
th, td { padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }
thead th { font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); font-weight:600; }
tbody tr:last-child th, tbody tr:last-child td { border-bottom:0; }
td.num { font-variant-numeric:tabular-nums; white-space:nowrap; }
.ci { color:var(--muted); font-size:12.5px; }
.desc { color:var(--muted); font-size:12.5px; font-weight:400; }
tbody th { min-width:200px; }
.muted { color:var(--muted); }
tr.tool th code { color:var(--tool); font-weight:600; }
.verdict { font-size:13px; }
.forest { width:100%; max-width:680px; height:auto; display:block; margin-top:8px; }
.forest .band { fill:var(--band); }
.forest .grid { stroke:var(--line); }
.forest .zero { stroke:var(--muted); stroke-dasharray:3 3; }
.forest .tick { fill:var(--muted); font-size:11px; text-anchor:middle; }
.forest .label { fill:var(--fg); font:12px ui-monospace,Menlo,monospace; text-anchor:end; }
.forest .ci { stroke-width:2.5; stroke-linecap:round; }
.forest .ci.tool { stroke:var(--tool); } .forest .pt.tool { fill:var(--tool); }
.forest .ci.control { stroke:var(--control); } .forest .pt.control { fill:var(--control); }
.forest .ci.reference { stroke:var(--ref); } .forest .pt.reference { fill:var(--ref); }
.note { color:var(--muted); font-size:13.5px; }
ul { padding-left:20px; } li { margin:4px 0; }
footer { margin-top:48px; color:var(--muted); font-size:13px; border-top:1px solid var(--line); padding-top:16px; }
"""


def build(sets: list[Path]) -> str:
    featured, *rest = sets
    sections = section(featured, True)
    others = "\n".join(section(p, False) for p in rest)
    srcs = ", ".join(f"<code>{html.escape(p.as_posix())}/summary.json</code>" for p in sets)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TokenTrial leaderboard</title>
<meta name="description" content="Dollars per correctly solved task, with and without token-saving tools for coding agents.">
<style>{STYLE}</style>
</head>
<body>
<main>
<h1>TokenTrial leaderboard</h1>
<p class="sub">Does a token-saving tool lower what a coding agent costs per <em>correctly solved</em> task?
Each tool is compared with baseline and with a <em>matched control</em> that reproduces its side
effects on Claude Code without the tool itself. Write-up: <a href="{FINDINGS}">v0.3 FINDINGS</a>.</p>

<h2>v0.3 in brief</h2>
<ul>
<li><b>No tool saved money beyond the noise floor</b> on either model.</li>
<li><b>caveman v4.1.0 cost 25% more on Sonnet 5.5</b> (95% CI +12% to +44%) than its control. Its
SessionStart hook adds about 1,850 tokens of instructions to every session, and Sonnet's output, already
short, didn't get shorter. On Haiku 5.5, where output fell about 17%, it was −8% (CI −19% to +5%).</li>
<li><b>rtk's penalty replicated where rtk does the most work.</b> Averaged over 18 tasks it's +4–5%
(inconclusive), but on the four Bash-heavy tasks identified in v0.2 it was +38% for v1.1.0 on Haiku
(CI +9% to +81%) and +36% for v1.2.0 on Sonnet (CI +5% to +114%).</li>
<li><b>headroom had no measurable effect</b> against a pass-through proxy (Haiku −6%, Sonnet −2%). It
compressed requests in every run but removed only about 2% of input tokens.</li>
<li><b>Claude Code updated itself mid-run</b> (2.1.252 → 2.1.322) after 447 of the 810 Haiku runs; all
Sonnet runs used 2.1.322. 2.1.322 no longer makes the background title call that skewed caveman's pilot result.
See FINDINGS for the version-split analysis.</li>
</ul>

{sections}

<h2>Earlier and per-model results</h2>
{others}

<h2>Limitations</h2>
<ul>
<li>Synthetic small-to-medium tasks; both models solved nearly all of them, so the comparison rests on cost.</li>
<li>Claude Code changed version during the Haiku run; arms were affected roughly equally (36–45 of each arm's 90 runs on 2.1.322).</li>
<li>Default tool configurations and pinned versions; one agent (Claude Code).</li>
<li>Costs are API-equivalent: runs used a Claude Code subscription, priced at verified list prices
(<a href="{REPO}/blob/{BRANCH}/src/tokentrial/data/pricing.toml">price table</a>).</li>
</ul>

<h2>Method and reproduction</h2>
<ul>
<li>CIs: task-then-run hierarchical bootstrap, 10,000 resamples, paired by task.</li>
<li>Reproduce v0.3 (after <code>uv sync &amp;&amp; uv run tokentrial install-arms</code>):<br>
Haiku: <code>uv run tokentrial run --model claude-haiku-5-5 --repeats 5 --seed 3 --out runs/v0.3-haiku --arm baseline --arm noop --arm noop-hook --arm headroom-passthrough --arm rtk --arm rtk-v1.2.0 --arm caveman --arm caveman-v4.1.0 --arm headroom</code><br>
Sonnet: <code>uv run tokentrial run --model claude-sonnet-5-5 --repeats 3 --seed 3 --out runs/v0.3-sonnet --arm baseline --arm noop --arm noop-hook --arm headroom-passthrough --arm rtk-v1.2.0 --arm caveman-v4.1.0 --arm headroom</code><br>
then <code>uv run tokentrial report --runs runs/v0.3-haiku</code> (and the same for <code>runs/v0.3-sonnet</code>).</li>
<li>v0.2 write-up: <a href="{FINDINGS_V02}">FINDINGS</a>.</li>
</ul>

<footer>Generated by <code>scripts/make_site.py</code> from {srcs}.
<a href="{REPO}">Source on GitHub</a> · MIT license.</footer>
</main>
</body>
</html>
"""


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/index.html")
    sets = [Path(p) for p in sys.argv[2:]] or [
        Path("results/v0.3-sonnet"),
        Path("results/v0.3-haiku"),
        Path("results/v0.2"),
    ]
    out.write_text(build(sets))
    (out.parent / ".nojekyll").touch()
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
