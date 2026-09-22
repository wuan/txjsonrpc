"""Compare and render txjsonrpc-ng benchmark results.

This is the reporting half of the benchmarking tooling.  It consumes the flat
metrics files produced by ``benchmarks/bench.py --metrics-file`` and can:

  compare  Produce a Markdown report (with regressions highlighted) comparing a
           current run against a baseline.  Used for the pull-request comment.
  html     Render a self-contained dashboard (tables + inline SVG trend charts)
           and update a history file.  Used for the gh-pages deployment.

The metrics file format is::

    {
      "latency":    [{"name": str, "unit": "us"|"ms", "value": float}, ...],
      "throughput": [{"name": str, "unit": "ops/s", "value": float}, ...]
    }
"""

from __future__ import annotations

import argparse
import datetime as _dt
import html
import json
from typing import Dict, List, Optional


LATENCY_UNITS = {"ns", "us", "ms", "s"}

#: Percentage change beyond which a metric is called out as a regression /
#: improvement in the Markdown report.
REGRESSION_THRESHOLD = 5.0


# --------------------------------------------------------------------------- #
# Loading / formatting helpers
# --------------------------------------------------------------------------- #


def load_json(path: Optional[str]):
    if not path:
        return None
    try:
        with open(path) as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def entries_by_name(metrics) -> Dict[tuple, dict]:
    """Index metrics by ``(group, name)`` so latency/throughput don't collide."""
    entries: Dict[tuple, dict] = {}
    for group in ("latency", "throughput"):
        for entry in (metrics or {}).get(group, []):
            entries[(group, entry["name"])] = entry
    return entries


def direction(unit: str) -> str:
    """Return ``"lower"`` or ``"higher"`` for what counts as an improvement."""
    return "lower" if unit in LATENCY_UNITS else "higher"


def pct_change(baseline: float, current: float) -> Optional[float]:
    if baseline in (0, None):
        return None
    return (current - baseline) / baseline * 100.0


def is_regression(change: Optional[float], unit: str, threshold: float) -> bool:
    if change is None:
        return False
    if direction(unit) == "lower":
        return change > threshold
    return change < -threshold


def fmt(value: float, unit: str) -> str:
    if unit == "ops/s":
        return f"{value:,.0f} ops/s"
    return f"{value:,.2f} {unit}"


def fmt_change(change: Optional[float]) -> str:
    if change is None:
        return "n/a"
    return f"{change:+.1f}%"


# --------------------------------------------------------------------------- #
# Markdown (pull request comment / job summary)
# --------------------------------------------------------------------------- #


def _markdown_table(rows, baseline: bool) -> str:
    if baseline:
        header = "| Metric | Baseline | Current | Change |\n| --- | ---: | ---: | ---: |"
    else:
        header = "| Metric | Current |\n| --- | ---: |"
    lines = [header]
    for row in rows:
        if baseline:
            lines.append(
                f"| {row['name']} | {row['baseline']} | {row['current']} | "
                f"{row['change']} {row['marker']} |"
            )
        else:
            lines.append(f"| {row['name']} | {row['current']} |")
    return "\n".join(lines)


def compare_markdown(
    baseline,
    current,
    label: str = "main",
    threshold: float = REGRESSION_THRESHOLD,
) -> str:
    base_entries = entries_by_name(baseline) if baseline else {}
    cur_entries = entries_by_name(current)

    regressions = 0
    improvements = 0
    compared = 0

    lines: List[str] = ["## Performance benchmark", ""]

    if not baseline:
        lines.append(
            "No baseline found on `gh-pages` yet. Once this branch is merged, "
            "the first deploy from `main` will establish one and subsequent "
            "runs will be compared against it."
        )
        lines.append("")

    # Preserve the order the benchmark emits (group by latency/throughput).
    for group in ("latency", "throughput"):
        title = "Latency (lower is better)" if group == "latency" else (
            "Throughput (higher is better)"
        )
        lines.append(f"### {title}")
        lines.append("")

        rows = []
        for entry in (current or {}).get(group, []):
            name = entry["name"]
            unit = entry["unit"]
            cur_value = entry["value"]
            row = {
                "name": name,
                "current": fmt(cur_value, unit),
                "baseline": "-",
                "change": "-",
                "marker": "",
            }
            other = base_entries.get((group, name))
            if other:
                change = pct_change(other.get("value"), cur_value)
                row["baseline"] = fmt(other.get("value"), other["unit"])
                row["change"] = fmt_change(change)
                compared += 1
                if is_regression(change, unit, threshold):
                    regressions += 1
                    row["marker"] = "🔴"
                elif change is not None and is_regression(
                    -change, unit, threshold
                ):
                    improvements += 1
                    row["marker"] = "🟢"
                else:
                    row["marker"] = "⚪"
            rows.append(row)

        lines.append(_markdown_table(rows, baseline=bool(baseline)))
        lines.append("")

    if baseline and compared:
        lines.append(
            f"**{compared} metrics compared** vs `{label}` "
            f"(threshold ±{threshold:.0f}%): "
            f"🔴 {regressions} regression(s), 🟢 {improvements} improvement(s)."
        )
    lines.append("")
    lines.append(
        "<sub>Generated by `benchmarks/report.py`. Numbers come from a shared "
        "CI runner and are intended for trend detection, not absolute "
        "comparison.</sub>"
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# HTML dashboard
# --------------------------------------------------------------------------- #


def _sparkline(values: List[float], width: int = 280, height: int = 70) -> str:
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    pad = 6
    n = len(values)
    points = []
    for i, value in enumerate(values):
        x = pad + (width - 2 * pad) * (i / (n - 1) if n > 1 else 0.0)
        y = height - pad - (height - 2 * pad) * ((value - lo) / span)
        points.append((x, y))
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" />' for x, y in points
    )
    return (
        f'<svg class="spark" viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="none" role="img" '
        f'aria-label="trend from {lo:.4g} to {hi:.4g}">'
        f'<polyline points="{polyline}" />{dots}</svg>'
    )


def _html_table(rows, baseline: bool) -> str:
    if baseline:
        head = "<tr><th>Metric</th><th>Previous</th><th>Current</th><th>Change</th></tr>"
    else:
        head = "<tr><th>Metric</th><th>Current</th></tr>"
    body = []
    for row in rows:
        if baseline:
            body.append(
                "<tr>"
                f"<td>{html.escape(row['name'])}</td>"
                f"<td class='num'>{html.escape(row['baseline'])}</td>"
                f"<td class='num'>{html.escape(row['current'])}</td>"
                f"<td class='num {row['cls']}'>{html.escape(row['change'])}</td>"
                "</tr>"
            )
        else:
            body.append(
                "<tr>"
                f"<td>{html.escape(row['name'])}</td>"
                f"<td class='num'>{html.escape(row['current'])}</td>"
                "</tr>"
            )
    return f"<table><thead>{head}</thead><tbody>{''.join(body)}</tbody></table>"


def _section(history: List[dict], group: str) -> str:
    """Build the table + charts for one metric group from history."""
    title = "Latency (lower is better)" if group == "latency" else (
        "Throughput (higher is better)"
    )
    previous = history[-2] if len(history) > 1 else None
    current = history[-1] if history else None
    if current is None:
        return f"<section><h2>{title}</h2><p>No data.</p></section>"

    prev_entries = entries_by_name(previous["metrics"]) if previous else {}

    current_entries = (current["metrics"] or {}).get(group, [])
    rows = []
    for entry in current_entries:
        name = entry["name"]
        unit = entry["unit"]
        row = {
            "name": name,
            "current": fmt(entry["value"], unit),
            "baseline": "-",
            "change": "-",
            "cls": "",
        }
        other = prev_entries.get((group, name))
        if other:
            change = pct_change(other.get("value"), entry["value"])
            row["baseline"] = fmt(other["value"], other["unit"])
            row["change"] = fmt_change(change)
            if is_regression(change, unit, REGRESSION_THRESHOLD):
                row["cls"] = "bad"
            elif change is not None and is_regression(
                -change, unit, REGRESSION_THRESHOLD
            ):
                row["cls"] = "good"
        rows.append(row)

    charts = []
    for entry in current_entries:
        name = entry["name"]
        unit = entry["unit"]
        values = []
        for run in history:
            for past in (run["metrics"] or {}).get(group, []):
                if past["name"] == name:
                    values.append(past["value"])
                    break
        latest = values[-1] if values else 0.0
        charts.append(
            '<figure class="chart">'
            f"<figcaption>{html.escape(name)} "
            f"<span>{html.escape(fmt(latest, unit))}</span></figcaption>"
            f"{_sparkline(values)}"
            "</figure>"
        )

    return (
        "<section>"
        f"<h2>{title}</h2>"
        f"{_html_table(rows, baseline=bool(prev_entries))}"
        f'<div class="charts">{"".join(charts)}</div>'
        "</section>"
    )


def render_html(history: List[dict], commit: str = "", generated_at: str = "") -> str:
    generated_at = generated_at or _dt.datetime.now(_dt.timezone.utc).isoformat(
        timespec="seconds"
    )
    short_commit = commit[:10] if commit else "unknown"
    body = _section(history, "latency") + _section(history, "throughput")

    runs = len(history)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>txjsonrpc-ng performance</title>
<style>
:root {{ color-scheme: light dark; }}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 2rem 1rem; font: 15px/1.5 -apple-system, BlinkMacSystemFont,
  "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  max-width: 1100px; margin-inline: auto;
}}
h1 {{ margin: 0 0 .25rem; font-size: 1.6rem; }}
h2 {{ margin: 2rem 0 .75rem; font-size: 1.2rem; }}
.meta {{ color: #6b7280; margin: 0 0 1.5rem; }}
table {{ border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }}
th, td {{ padding: .45rem .6rem; border-bottom: 1px solid #0002; text-align: left; }}
th {{ font-weight: 600; border-bottom-width: 2px; }}
td.num, th:not(:first-child) {{ text-align: right; }}
td.good {{ color: #15803d; }}
td.bad {{ color: #b91c1c; }}
.charts {{ display: grid; gap: 1rem; grid-template-columns:
  repeat(auto-fill, minmax(280px, 1fr)); margin-top: 1.25rem; }}
.chart {{ margin: 0; padding: .6rem .75rem; border: 1px solid #0002;
  border-radius: 8px; }}
.chart figcaption {{ font-size: .85rem; display: flex;
  justify-content: space-between; gap: .5rem; }}
.chart figcaption span {{ color: #6b7280; white-space: nowrap; }}
.spark {{ width: 100%; height: 70px; display: block; margin-top: .4rem; }}
.spark polyline {{ fill: none; stroke: #2563eb; stroke-width: 2;
  vector-effect: non-scaling-stroke; }}
.spark circle {{ fill: #2563eb; }}
footer {{ margin-top: 2.5rem; color: #6b7280; font-size: .85rem; }}
</style>
</head>
<body>
<h1>txjsonrpc-ng performance</h1>
<p class="meta">Latest run <code>{html.escape(short_commit)}</code> &middot;
generated {html.escape(generated_at)} &middot; {runs} run(s) in history</p>
{body}
<footer>Values come from a shared CI runner; use the trends, not the absolutes.</footer>
</body>
</html>
"""


def append_history(history: List[dict], current, commit: str, timestamp: str, max_runs: int):
    history.append(
        {
            "commit": commit,
            "timestamp": timestamp,
            "metrics": current,
        }
    )
    return history[-max_runs:]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _cmd_compare(args) -> int:
    current = load_json(args.current)
    if current is None:
        print(f"error: could not read current metrics: {args.current}", flush=True)
        return 2
    baseline = load_json(args.baseline)
    markdown = compare_markdown(
        baseline, current, label=args.label, threshold=args.threshold
    )
    if args.output:
        with open(args.output, "w") as handle:
            handle.write(markdown + "\n")
    print(markdown)
    return 0


def _cmd_html(args) -> int:
    current = load_json(args.current)
    if current is None:
        print(f"error: could not read current metrics: {args.current}", flush=True)
        return 2
    history = load_json(args.history) or []
    timestamp = args.generated_at or _dt.datetime.now(_dt.timezone.utc).isoformat(
        timespec="seconds"
    )
    history = append_history(history, current, args.commit, timestamp, args.max_runs)
    if args.history:
        with open(args.history, "w") as handle:
            json.dump(history, handle, indent=2)
            handle.write("\n")
    with open(args.output, "w") as handle:
        handle.write(render_html(history, commit=args.commit, generated_at=timestamp))
    print(f"wrote {args.output} ({len(history)} run(s) in history)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    compare = sub.add_parser("compare", help="Markdown comparison report")
    compare.add_argument("--baseline", help="baseline metrics JSON (optional)")
    compare.add_argument("--current", required=True, help="current metrics JSON")
    compare.add_argument("--label", default="main", help="baseline label")
    compare.add_argument(
        "--threshold", type=float, default=REGRESSION_THRESHOLD,
        help="regression threshold in percent (default: %(default)s)",
    )
    compare.add_argument("--output", help="write the Markdown report to this file")
    compare.set_defaults(func=_cmd_compare)

    page = sub.add_parser("html", help="Render the gh-pages dashboard")
    page.add_argument("--current", required=True, help="current metrics JSON")
    page.add_argument("--history", help="history JSON (read and updated in place)")
    page.add_argument("--output", required=True, help="output index.html")
    page.add_argument("--commit", default="", help="commit SHA to display")
    page.add_argument("--generated-at", default="", help="ISO timestamp override")
    page.add_argument(
        "--max-runs", type=int, default=100, help="history entries to keep"
    )
    page.set_defaults(func=_cmd_html)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())