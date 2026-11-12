"""Build the static leaderboard page (docs/index.html) from a results directory.

Usage: uv run python scripts/make_site.py [results/v0.2] [docs/index.html]

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
    "rtk": ("rtk: compresses shell command output", "tool"),
    "caveman": ("caveman: terse-answer plugin", "tool"),
    "noop-baseurl": ("Control: ANTHROPIC_BASE_URL set to Anthropic's URL", "control"),
    "headroom-passthrough": ("Control: headroom proxy with optimization off", "control"),
    "rtk-v1.2.0": ("rtk v1.2.0", "tool"),
    "caveman-v4.1.0": ("caveman v4.1.0", "tool"),
    "headroom": ("headroom: context-compression proxy", "tool"),
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


def forest_svg(arms: dict) -> str:
    """Relative cost per solved task vs baseline, with 95% CIs."""
    rows = [a for a in ARM_ORDER if a in arms and "vs_baseline" in arms[a]]
    lo, hi = -0.4, 0.7
    w, left, right, row_h, top = 640, 110, 20, 34, 28
    h = top + row_h * len(rows) + 30
    span = w - left - right

    def x(v: float) -> float:
        return left + (max(lo, min(hi, v)) - lo) / (hi - lo) * span

    out = [
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="fp-title" class="forest">',
        '<title id="fp-title">Cost per solved task relative to baseline, with 95% confidence intervals</title>',
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


def build(results: Path) -> str:
    summary, info = load(results)
    arms = summary["arms"]
    m = summary["manifest"]
    name = m.get("name", results.name)
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

        def rel_cell(key: str, s=s) -> str:
            if key not in s:
                return '<td class="num muted">—</td>'
            v = s[key]
            return f'<td class="num">{pct(v["point"])} <span class="ci">({pct(v["ci95"][0])} to {pct(v["ci95"][1])})</span></td>'

        verdict = s.get("verdict", "control" if kind == "control" else "reference")
        rows.append(
            f'<tr class="{kind}"><th scope="row"><code>{html.escape(a)}</code><div class="desc">{html.escape(desc)}</div></th>'
            f'<td class="num">{html.escape(info["arm_versions"].get(a, "—"))}</td>'
            f'<td class="num">{s["solved"]}/{s["runs"]}</td>'
            f'<td class="num">{usd(s["cost_per_solved"])} <span class="ci">({usd(c1)}–{usd(c2)})</span></td>'
            f"{rel_cell('vs_baseline')}{rel_cell('vs_noop_hook')}"
            f'<td class="verdict">{html.escape(verdict)}</td></tr>'
        )

    nf = summary["noise_floor_noop_vs_baseline"]
    boot = summary["bootstrap"]
    dates = ", ".join(info["dates"])
    cc = ", ".join(info["claude_code"])
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TokenTrial leaderboard</title>
<meta name="description" content="Dollars per correctly solved task, with and without token-saving tools for coding agents.">
<style>
:root {{
  --bg:#fbfbfa; --fg:#1d1d1b; --muted:#6b6b66; --line:#e4e3df; --card:#ffffff;
  --tool:#2f5fb3; --control:#8a8a84; --ref:#1d1d1b; --band:rgba(138,138,132,.13); --accent:#2f5fb3;
  color-scheme: light;
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#161615; --fg:#ecebe7; --muted:#9b9a94; --line:#2e2e2b; --card:#1d1d1b;
    --tool:#7aa2e8; --control:#8a8a84; --ref:#ecebe7; --band:rgba(160,160,152,.14); --accent:#7aa2e8;
    color-scheme: dark; }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg);
  font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:1040px; margin:0 auto; padding:40px 20px 64px; }}
h1 {{ font-size:28px; margin:0 0 4px; letter-spacing:-.01em; }}
h2 {{ font-size:18px; margin:40px 0 12px; }}
.sub {{ color:var(--muted); margin:0 0 24px; }}
a {{ color:var(--accent); }}
code {{ font:13px ui-monospace,SFMono-Regular,Menlo,monospace; }}
.facts {{ display:flex; flex-wrap:wrap; gap:8px 24px; padding:14px 16px; border:1px solid var(--line);
  border-radius:8px; background:var(--card); font-size:14px; }}
.facts b {{ font-weight:600; }}
.scroll {{ overflow-x:auto; border:1px solid var(--line); border-radius:8px; background:var(--card); }}
table {{ border-collapse:collapse; width:100%; min-width:820px; font-size:14px; }}
th, td {{ padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
thead th {{ font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); font-weight:600; }}
tbody tr:last-child th, tbody tr:last-child td {{ border-bottom:0; }}
td.num {{ font-variant-numeric:tabular-nums; white-space:nowrap; }}
.ci {{ color:var(--muted); font-size:12.5px; }}
.desc {{ color:var(--muted); font-size:12.5px; font-weight:400; }}
tbody th {{ min-width:200px; }}
.muted {{ color:var(--muted); }}
tr.tool th code {{ color:var(--tool); font-weight:600; }}
.verdict {{ font-size:13px; }}
.forest {{ width:100%; max-width:680px; height:auto; display:block; }}
.forest .band {{ fill:var(--band); }}
.forest .grid {{ stroke:var(--line); }}
.forest .zero {{ stroke:var(--muted); stroke-dasharray:3 3; }}
.forest .tick {{ fill:var(--muted); font-size:11px; text-anchor:middle; }}
.forest .label {{ fill:var(--fg); font:12px ui-monospace,Menlo,monospace; text-anchor:end; }}
.forest .ci {{ stroke-width:2.5; stroke-linecap:round; }}
.forest .ci.tool {{ stroke:var(--tool); }} .forest .pt.tool {{ fill:var(--tool); }}
.forest .ci.control {{ stroke:var(--control); }} .forest .pt.control {{ fill:var(--control); }}
.forest .ci.reference {{ stroke:var(--ref); }} .forest .pt.reference {{ fill:var(--ref); }}
.note {{ color:var(--muted); font-size:13.5px; }}
ul {{ padding-left:20px; }} li {{ margin:4px 0; }}
footer {{ margin-top:48px; color:var(--muted); font-size:13px; border-top:1px solid var(--line); padding-top:16px; }}
</style>
</head>
<body>
<main>
<h1>TokenTrial leaderboard</h1>
<p class="sub">Does a token-saving tool lower what a coding agent costs per <em>correctly solved</em> task?
Results for run <code>{html.escape(name)}</code>.</p>

<div class="facts">
  <span><b>Date</b> {html.escape(dates)}</span>
  <span><b>Agent</b> Claude Code {html.escape(cc)}, headless</span>
  <span><b>Model</b> <code>{html.escape(m["model"])}</code></span>
  <span><b>Design</b> {len(m["task_ids"])} tasks × {len(m["arms"])} arms × {m["repeats"]} repeats = {total_runs} runs</span>
  <span><b>Solved</b> {total_solved}/{total_runs}</span>
  <span><b>Total cost</b> ${total_cost:.2f} API-equivalent (verified list prices)</span>
</div>

<h2>Cost per solved task</h2>
<div class="scroll">
<table>
<thead><tr><th>Arm</th><th>Version</th><th>Solved</th><th>Cost per solved task (95% CI)</th>
<th>vs <code>baseline</code></th><th>vs <code>noop-hook</code></th><th>Verdict</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
</div>
<p class="note">Noise floor (<code>noop</code> vs <code>baseline</code>): {pct(nf["point"])}
({pct(nf["ci95"][0])} to {pct(nf["ci95"][1])}). A tool counts as saving money only if its interval
excludes zero and its point estimate lies outside the noise floor.</p>

<h2>Relative to baseline</h2>
{forest_svg(arms)}
<p class="note">Dots are point estimates; lines are 95% CIs. The shaded band is the noise floor.</p>

<h2>What is behind the numbers</h2>
<ul>
<li><b>rtk</b> compressed pytest and git output. On the tasks where it compressed the most, the agent
re-ran commands with <code>rtk bypass</code> and took more turns, and each extra turn re-reads the
cached context. See <a href="{blob}/FINDINGS.md#why-rtk-cost-more">FINDINGS</a>.</li>
<li><b>caveman</b>: Claude Code {html.escape(cc)} skips a small background title-generation call whenever
<em>any</em> SessionStart hook is configured. caveman registers one, which explains its apparent
saving in the pilot. The <code>noop-hook</code> arm reproduces that side effect; against it caveman's
effect is about zero. See <a href="{blob}/FINDINGS.md#why-cavemans-pilot-saving-disappeared">FINDINGS</a>.</li>
</ul>

<h2>Limitations</h2>
<ul>
<li>One model (Haiku 5.5) and one Claude Code version, which does not recognize this model ID. That is the same for every arm.</li>
<li>Small-to-medium synthetic tasks. Haiku solved nearly all of them, so the comparison rests on cost, not solve rate.</li>
<li>Pinned tool versions (rtk v1.1.0, caveman v4.0.1); newer releases were not tested.</li>
<li>Costs are API-equivalent: runs used a Claude Code subscription and usage was priced at list prices.</li>
</ul>

<h2>Data and method</h2>
<ul>
<li><a href="{blob}/FINDINGS.md">Findings write-up</a> ·
<a href="{blob}/summary.md">summary.md</a> · <a href="{blob}/summary.json">summary.json</a></li>
<li><a href="{raw_tree}">Raw data</a>: <a href="{blob}/raw/records.jsonl">records.jsonl</a> (one line per run),
<a href="{blob}/raw/manifest.json">manifest.json</a>, <a href="{blob}/raw/logs.tar.gz">logs.tar.gz</a> (agent transcripts; home path and username scrubbed)</li>
<li><a href="{REPO}/blob/{BRANCH}/src/tokentrial/data/pricing.toml">Price table</a> with source URLs and check dates</li>
<li>CIs: {boot["method"]} bootstrap, {boot["resamples"]:,} resamples, paired by task.</li>
<li>Reproduce: <code>uv sync &amp;&amp; uv run tokentrial install-arms &amp;&amp; uv run tokentrial run --repeats {m["repeats"]} --seed {m["seed"]} --out runs/{html.escape(name)} --arm baseline --arm noop --arm noop-hook --arm rtk --arm caveman</code>
then <code>uv run tokentrial report --runs runs/{html.escape(name)}</code>.</li>
</ul>

<footer>Generated by <code>scripts/make_site.py</code> from <code>{html.escape(rel)}/summary.json</code>.
<a href="{REPO}">Source on GitHub</a> · MIT license.</footer>
</main>
</body>
</html>
"""


def main() -> None:
    results = Path(sys.argv[1] if len(sys.argv) > 1 else "results/v0.2")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/index.html")
    out.write_text(build(results))
    (out.parent / ".nojekyll").touch()
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
