import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import report  # noqa: E402


def record(variant, concurrency, ttft_p95, kv_peak, waiting_peak, failed=0, gpu=None):
    # Keys as written by `vllm bench serve --save-result` (vllm/benchmarks/serve.py
    # at v0.32.0) and by roles/bench/tasks/run.yml.
    return {
        "variant": variant,
        "concurrency": concurrency,
        "bench": {
            "completed": concurrency * 6 - failed,
            "failed": failed,
            "request_throughput": concurrency * 0.4,
            "output_throughput": concurrency * 100.0,
            "p50_ttft_ms": ttft_p95 / 2,
            "p95_ttft_ms": ttft_p95,
            "p95_tpot_ms": 25.0,
            "p95_e2el_ms": 9000.0,
        },
        "server": {
            "kv_cache_peak": kv_peak,
            "running_peak": min(concurrency, 50),
            "waiting_peak": waiting_peak,
            "preemptions": 0.0,
            "gpu_util_mean": gpu,
        },
    }


class ReportTest(unittest.TestCase):
    def write(self, root, records):
        for r in records:
            path = Path(root) / r["variant"] / f"c{r['concurrency']}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(r))

    def rows(self, text):
        return [line for line in text.splitlines() if line.startswith("| ") and "Concurrency" not in line]

    def test_rows_read_as_a_load_curve(self):
        # Files sort as c128, c32, c8 by name. The table must climb in load,
        # or the point where latency jumps lands in the wrong place.
        with tempfile.TemporaryDirectory() as root:
            self.write(root, [record("bf16", c, 100, 0.5, 0) for c in (128, 32, 8)])
            rows = self.rows(report.render(report.load(root)))
        self.assertEqual([row.split(" | ")[0] for row in rows], ["| 8", "| 32", "| 128"])

    def test_saturation_shows_beside_the_latency_it_explains(self):
        # The point of the lab: the row where TTFT jumps must also show the
        # full KV cache and the queue that caused it.
        with tempfile.TemporaryDirectory() as root:
            self.write(root, [record("bf16", 128, 4000, 0.99, 78)])
            row = self.rows(report.render(report.load(root)))[0].split(" | ")
        header = [name for name, _ in report.COLUMNS]
        self.assertEqual(row[header.index("TTFT p95 (ms)")], "4000")
        self.assertEqual(row[header.index("KV cache peak")], "99%")
        self.assertEqual(row[header.index("Waiting peak")], "78")

    def test_failed_requests_are_never_hidden(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, [record("fp8", 64, 300, 0.7, 0, failed=3)])
            row = self.rows(report.render(report.load(root)))[0]
        self.assertTrue(row.endswith("| 3 |"))

    def test_missing_server_metrics_say_so(self):
        # A series Prometheus did not have (e.g. DCGM down) must read n/a, not 0.
        with tempfile.TemporaryDirectory() as root:
            self.write(root, [record("bf16", 1, 50, 0.1, 0, gpu=None)])
            row = self.rows(report.render(report.load(root)))[0].split(" | ")
        self.assertEqual(row[[name for name, _ in report.COLUMNS].index("GPU util")], "n/a")

    def test_each_variant_gets_its_own_table(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, [record("bf16", 8, 100, 0.2, 0), record("fp8", 8, 80, 0.1, 0)])
            text = report.render(report.load(root))
        self.assertLess(text.index("## bf16"), text.index("## fp8"))


if __name__ == "__main__":
    unittest.main()
