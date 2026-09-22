"""Performance benchmarks for txjsonrpc-ng.

Two independent suites:

  codec  Micro-benchmarks of the JSON serialization/parsing hot path used by
         every request/response.

  e2e    End-to-end JSON-RPC 2.0 calls over a loopback TCP connection, using
         the real Reactor, Netstring framing, Proxy and server.

No third-party benchmark dependency is required.

Usage:
    python benchmarks/bench.py                 # run both suites
    python benchmarks/bench.py --suite codec
    python benchmarks/bench.py --suite e2e
    python benchmarks/bench.py --json          # machine-readable output
    python benchmarks/bench.py --metrics-file metrics.json  # flat baseline
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import timeit

from twisted.internet import defer, reactor, task

from txjsonrpc_ng import jsonrpclib
from txjsonrpc_ng.netstring import jsonrpc

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

SMALL_PAYLOAD = {"jsonrpc": "2.0", "result": 5, "id": 1}
COMPLEX_PAYLOAD = {
    "jsonrpc": "2.0",
    "result": [{"a": ["b", "c", 12, []], "D": "foo"}] * 20,
    "id": 42,
}


class BenchResource(jsonrpc.JSONRPC):
    """Minimal handler exercising the common code paths."""

    def jsonrpc_add(self, a, b):
        return a + b

    def jsonrpc_echo(self, value):
        return value

    def jsonrpc_complex(self):
        return {"a": ["b", "c", 12, []], "D": "foo"}

    def jsonrpc_defer(self, value):
        return defer.succeed(value)


# --------------------------------------------------------------------------- #
# Codec / dispatch micro-benchmarks
# --------------------------------------------------------------------------- #


def _timeit_per_op(stmt, namespace, number=100_000, repeat=7):
    """Return (best, mean) seconds per operation for ``stmt``."""
    timer = timeit.Timer(stmt, globals=namespace)
    times = timer.repeat(repeat=repeat, number=number)
    per_op = [t / number for t in times]
    return min(per_op), statistics.mean(per_op)


def run_codec_suite():
    results = []

    # Build request strings once so parsing benchmarks measure parsing only.
    namespace = {
        "jsonrpclib": jsonrpclib,
        "SMALL_PAYLOAD": SMALL_PAYLOAD,
        "COMPLEX_PAYLOAD": COMPLEX_PAYLOAD,
        "REQUEST_SMALL": jsonrpclib.dumps(
            {"method": "add", "params": [1, 2]},
            id=1,
            version=jsonrpclib.VERSION_2,
        ),
        "REQUEST_COMPLEX": jsonrpclib.dumps(
            {"method": "complex", "params": []},
            id=1,
            version=jsonrpclib.VERSION_2,
        ),
        "BENCH_RESOURCE": BenchResource(),
    }

    scenarios = [
        ("dumps small result (v2)", "jsonrpclib.dumps(SMALL_PAYLOAD);"),
        ("dumps complex result (v2)", "jsonrpclib.dumps(COMPLEX_PAYLOAD);"),
        ("loads small request", "jsonrpclib.loads(REQUEST_SMALL);"),
        ("loads complex request", "jsonrpclib.loads(REQUEST_COMPLEX);"),
    ]

    for name, stmt in scenarios:
        best, mean = _timeit_per_op(stmt, namespace)
        results.append(
            {
                "name": name,
                "unit": "us/op",
                "best": best * 1e6,
                "mean": mean * 1e6,
                "ops_per_sec": 1.0 / mean,
            }
        )

    # Method resolution benchmark (independent of JSON).
    best, mean = _timeit_per_op(
        "BENCH_RESOURCE._getFunction('add');", namespace, number=200_000
    )
    results.append(
        {
            "name": "_getFunction dispatch",
            "unit": "us/op",
            "best": best * 1e6,
            "mean": mean * 1e6,
            "ops_per_sec": 1.0 / mean,
        }
    )
    return results


# --------------------------------------------------------------------------- #
# End-to-end over loopback TCP
# --------------------------------------------------------------------------- #


async def _run_e2e(sequential=500, total=2000, concurrency=64):
    server = jsonrpc.RPCFactory(BenchResource)
    listener = reactor.listenTCP(0, server, interface="127.0.0.1")
    port = listener.getHost().port
    proxy = jsonrpc.Proxy("127.0.0.1", port, version=jsonrpclib.VERSION_2)

    results = []
    try:
        # Warm-up so imports / JIT-ish effects don't pollute timings.
        for _ in range(25):
            await proxy.callRemote("add", 1, 2)

        # --- sequential latency -------------------------------------------- #
        latencies = []
        for _ in range(sequential):
            start = time.perf_counter()
            await proxy.callRemote("add", 1, 2)
            latencies.append(time.perf_counter() - start)

        latencies.sort()
        results.append(
            {
                "name": "sequential call latency",
                "unit": "ms",
                "n": len(latencies),
                "mean": statistics.mean(latencies) * 1e3,
                "p50": latencies[len(latencies) // 2] * 1e3,
                "p95": latencies[int(len(latencies) * 0.95)] * 1e3,
                "p99": latencies[int(len(latencies) * 0.99)] * 1e3,
            }
        )

        # --- concurrent throughput ----------------------------------------- #
        start = time.perf_counter()
        done = 0
        while done < total:
            batch = min(concurrency, total - done)
            await defer.DeferredList(
                [proxy.callRemote("add", 1, 2) for _ in range(batch)]
            )
            done += batch
        elapsed = time.perf_counter() - start

        results.append(
            {
                "name": "concurrent calls",
                "unit": "req/s",
                "n": total,
                "concurrency": concurrency,
                "elapsed_s": elapsed,
                "throughput": total / elapsed,
            }
        )

        # --- complex payload round-trip ------------------------------------ #
        start = time.perf_counter()
        for _ in range(max(50, sequential // 5)):
            await proxy.callRemote("complex")
        elapsed = time.perf_counter() - start
        results.append(
            {
                "name": "complex payload latency",
                "unit": "ms",
                "mean": elapsed / max(50, sequential // 5) * 1e3,
            }
        )
    finally:
        listener.stopListening()

    return {"port": port, "results": results}


# --------------------------------------------------------------------------- #
# Reporting / CLI
# --------------------------------------------------------------------------- #


def _print_codec(results):
    print("\nCodec / dispatch micro-benchmarks")
    print("-" * 62)
    print(f"{'operation':<32}{'best':>10}{'mean':>12}{'ops/s':>10}")
    for r in results:
        print(
            f"{r['name']:<32}{r['best']:>8.2f}us{r['mean']:>10.2f}us"
            f"{r['ops_per_sec']:>10,.0f}"
        )


def _print_e2e(payload):
    print("\nEnd-to-end JSON-RPC over loopback TCP")
    print("-" * 62)
    for r in payload["results"]:
        if r["name"] == "sequential call latency":
            print(
                f"{r['name']} (n={r['n']}): mean {r['mean']:.3f} ms, "
                f"p50 {r['p50']:.3f} ms, p95 {r['p95']:.3f} ms, "
                f"p99 {r['p99']:.3f} ms"
            )
        elif r["name"] == "concurrent calls":
            print(
                f"{r['name']} (n={r['n']}, concurrency={r['concurrency']}): "
                f"{r['throughput']:,.0f} req/s in {r['elapsed_s']:.2f} s"
            )
        elif r["name"] == "complex payload latency":
            print(f"{r['name']}: mean {r['mean']:.3f} ms")


def flatten_metrics(output):
    """Convert the nested benchmark output into a flat, comparable mapping.

    Returns ``{"latency": [...], "throughput": [...]}`` where every entry is
    ``{"name": str, "unit": str, "value": number}``.  This is the canonical
    format consumed by :mod:`benchmarks.report` and stored as the baseline.
    """
    latency = []
    throughput = []

    for r in output.get("codec", []):
        latency.append(
            {"name": f"codec/{r['name']}", "unit": "us", "value": round(r["mean"], 4)}
        )
        throughput.append(
            {
                "name": f"codec/{r['name']}",
                "unit": "ops/s",
                "value": round(r["ops_per_sec"], 2),
            }
        )

    for r in output.get("e2e", {}).get("results", []):
        if r["name"] == "sequential call latency":
            for stat in ("mean", "p50", "p95", "p99"):
                latency.append(
                    {
                        "name": f"e2e/sequential {stat}",
                        "unit": "ms",
                        "value": round(r[stat], 4),
                    }
                )
        elif r["name"] == "concurrent calls":
            throughput.append(
                {
                    "name": "e2e/concurrent calls",
                    "unit": "ops/s",
                    "value": round(r["throughput"], 2),
                }
            )
        elif r["name"] == "complex payload latency":
            latency.append(
                {
                    "name": "e2e/complex payload",
                    "unit": "ms",
                    "value": round(r["mean"], 4),
                }
            )

    return {"latency": latency, "throughput": throughput}


def write_metrics(output, path):
    """Write the flat metrics file consumed by the reporting/CI tooling."""
    with open(path, "w") as handle:
        json.dump(flatten_metrics(output), handle, indent=2)
        handle.write("\n")


def _emit(output, as_json, metrics_file=None):
    if metrics_file:
        write_metrics(output, metrics_file)
    if as_json:
        print(json.dumps(output, indent=2))
        return
    if "codec" in output:
        _print_codec(output["codec"])
    if "e2e" in output:
        _print_e2e(output["e2e"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite",
        choices=["all", "codec", "e2e"],
        default="all",
        help="which benchmark suite to run (default: all)",
    )
    parser.add_argument(
        "--sequential", type=int, default=500, help="sequential calls (e2e)"
    )
    parser.add_argument(
        "--total", type=int, default=2000, help="total concurrent calls (e2e)"
    )
    parser.add_argument(
        "--concurrency", type=int, default=64, help="in-flight calls (e2e)"
    )
    parser.add_argument(
        "--json", action="store_true", help="emit JSON instead of text"
    )
    parser.add_argument(
        "--metrics-file",
        metavar="PATH",
        help="also write the flat metrics JSON (baseline format) to PATH",
    )
    args = parser.parse_args()

    output = {}
    if args.suite in ("all", "codec"):
        output["codec"] = run_codec_suite()

    if args.suite in ("all", "e2e"):

        async def main_e2e(reactor_):
            output["e2e"] = await _run_e2e(
                sequential=args.sequential,
                total=args.total,
                concurrency=args.concurrency,
            )
            _emit(output, args.json, args.metrics_file)

        # ``task.react`` runs the reactor and calls ``sys.exit`` when the
        # coroutine finishes, so reporting must happen inside it.
        task.react(main_e2e)
    else:
        _emit(output, args.json, args.metrics_file)


if __name__ == "__main__":
    main()