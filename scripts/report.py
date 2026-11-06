#!/usr/bin/env python3
"""Turn results/<variant>/c<N>.json into one Markdown table per variant.

Each row puts the client's view (throughput, latency percentiles from
`vllm bench serve`) next to the server's view of the same run (KV cache and
queue peaks from Prometheus), so the row where latency jumps also shows why.
"""

import json
import sys
from pathlib import Path

COLUMNS = [
    ("Concurrency", lambda r: str(r["concurrency"])),
    ("Req/s", lambda r: f"{r['bench']['request_throughput']:.2f}"),
    ("Output tok/s", lambda r: f"{r['bench']['output_throughput']:.0f}"),
    ("TTFT p50 (ms)", lambda r: f"{r['bench']['p50_ttft_ms']:.0f}"),
    ("TTFT p95 (ms)", lambda r: f"{r['bench']['p95_ttft_ms']:.0f}"),
    ("TPOT p95 (ms)", lambda r: f"{r['bench']['p95_tpot_ms']:.1f}"),
    ("E2E p95 (s)", lambda r: f"{r['bench']['p95_e2el_ms'] / 1000:.1f}"),
    ("KV cache peak", lambda r: server(r, "kv_cache_peak", "{:.0%}")),
    ("Running peak", lambda r: server(r, "running_peak", "{:.0f}")),
    ("Waiting peak", lambda r: server(r, "waiting_peak", "{:.0f}")),
    ("Preemptions", lambda r: server(r, "preemptions", "{:.0f}")),
    ("GPU util", lambda r: server(r, "gpu_util_mean", "{:.0f}%")),
    ("Failed", lambda r: str(r["bench"]["failed"])),
]


def server(record, key, fmt):
    value = record["server"].get(key)
    return "n/a" if value is None else fmt.format(value)


def load(results_dir):
    variants = {}
    for path in sorted(Path(results_dir).glob("*/c*.json")):
        record = json.loads(path.read_text())
        variants.setdefault(record["variant"], []).append(record)
    for records in variants.values():
        records.sort(key=lambda r: r["concurrency"])
    return variants


def render(variants):
    out = []
    for variant, records in sorted(variants.items()):
        out.append(f"## {variant}\n")
        out.append("| " + " | ".join(name for name, _ in COLUMNS) + " |")
        out.append("|" + "---:|" * len(COLUMNS))
        for record in records:
            out.append("| " + " | ".join(cell(record) for _, cell in COLUMNS) + " |")
        out.append("")
    return "\n".join(out)


def main():
    results_dir = sys.argv[1] if len(sys.argv) > 1 else "results"
    variants = load(results_dir)
    if not variants:
        sys.exit(f"no results under {results_dir}/<variant>/c<N>.json; run `make bench` first")
    print("# Results\n")
    print(render(variants))


if __name__ == "__main__":
    main()
