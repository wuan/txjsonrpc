# Benchmarks

Performance tooling for `txjsonrpc-ng`. There are two scripts:

| File | Purpose |
| --- | --- |
| `bench.py` | Runs the benchmarks and writes the raw results / flat metrics file. |
| `report.py` | Compares a run against a baseline (Markdown) and renders the gh-pages dashboard (HTML). |

They have no extra dependencies beyond the project's (Twisted) and the dev
environment.

## Running locally

```bash
# Both suites, human-readable output
poetry run python benchmarks/bench.py

# Just one suite
poetry run python benchmarks/bench.py --suite codec
poetry run python benchmarks/bench.py --suite e2e

# Machine-readable output and the flat metrics file used as a baseline
poetry run python benchmarks/bench.py --json --metrics-file metrics.json
```

Useful options:

| Option | Default | Meaning |
| --- | --- | --- |
| `--suite` | `all` | `codec`, `e2e`, or `all`. |
| `--sequential` | `500` | Sequential calls measured for latency percentiles (e2e). |
| `--total` | `2000` | Total concurrent calls measured (e2e). |
| `--concurrency` | `64` | In-flight calls per batch (e2e). |
| `--json` | off | Print the nested result document. |
| `--metrics-file PATH` | — | Write the flat metrics JSON (baseline format). |

### What is measured

- **`codec`** — pure `timeit` micro-benchmarks of the hot path: `jsonrpclib.dumps` /
  `loads` for small and large payloads, plus `BaseSubhandler._getFunction`
  dispatch.
- **`e2e`** — real Twisted reactor, Netstring framing and `Proxy` against an
  in-process server over loopback TCP: sequential latency (mean / p50 / p95 /
  p99), concurrent throughput (req/s), and a complex-payload round trip.

Note that `Proxy.callRemote` opens a new TCP connection per call, so the e2e
numbers include per-call connect overhead. This is a real characteristic of the
current design; compare runs against each other rather than in the abstract.

## Comparing and reporting

```bash
# Markdown comparison (regressions are flagged beyond --threshold, default 5%)
poetry run python benchmarks/report.py compare \
    --baseline baseline.json --current current.json --label main --output comment.md

# Render/refresh the dashboard and append to its history
poetry run python benchmarks/report.py html \
    --current metrics.json --history history.json \
    --output index.html --commit "$(git rev-parse HEAD)"
```

The flat metrics file (produced by `--metrics-file` and used as the baseline)
looks like:

```json
{
  "latency":    [{"name": "e2e/sequential mean", "unit": "ms", "value": 0.45}],
  "throughput": [{"name": "e2e/concurrent calls", "unit": "ops/s", "value": 6000.0}]
}
```

`report.py compare` treats latency units (`ns`/`us`/`ms`/`s`) as *lower is
better* and `ops/s` as *higher is better*, so regressions are detected in both
directions.

## Continuous integration

`.github/workflows/benchmark.yml` runs two jobs on a single fixed target
(`ubuntu-latest`, Python 3.12) so results stay comparable:

- **`pull-request`** — triggered on pull requests. Fetches the baseline from
  `gh-pages:data/metrics.json`, runs the benchmarks, and creates or updates a
  single sticky PR comment (header `txjsonrpc-benchmark`) with the comparison.
  Results are also attached as artifacts and written to the job summary. This
  job is skipped for PRs from forks, which only get a read-only token.
- **`main`** — triggered on pushes to `main` (and manually via
  `workflow_dispatch`). Runs the benchmarks and deploys the dashboard
  (`index.html`, `data/metrics.json`, `data/history.json`) to the `gh-pages`
  branch.

### gh-pages layout

The deployed site is self-contained:

```
index.html          # dashboard: latest tables + inline-SVG trend charts
data/metrics.json   # latest run; the baseline fetched by the PR job
data/history.json   # bounded history (default 100 runs) backing the charts
```

### Repository setting

GitHub Pages must serve from the **`gh-pages` branch** for the dashboard to be
published:

**Settings → Pages → Build and deployment → Source: "Deploy from a branch" →
Branch: `gh-pages` / `(root)`.**

The branch is created automatically by the first `main` run.

## Interpreting results

Benchmarks run on shared CI runners, so absolute numbers are noisy. Treat them
as trend indicators; the dashboard charts are more meaningful than any single
run, and the PR comment threshold (`--threshold`, default ±5%) is intentionally
lenient.