# /// script
# requires-python = ">=3.12"
# ///
import json
import statistics
import sys
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

URL = "http://127.0.0.1:8000/?tokens=50"
ROUNDS = 4


def one_request(_: int) -> tuple[float, str]:
    start = time.monotonic()
    with urllib.request.urlopen(URL, timeout=120) as response:
        body = json.load(response)
    return time.monotonic() - start, body["replica"]


def run(concurrency: int) -> None:
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(one_request, range(concurrency * ROUNDS)))
    latencies = sorted(seconds for seconds, _ in results)
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    per_replica = Counter(replica for _, replica in results)
    print(
        f"{concurrency:>11} | {statistics.median(latencies):>5.2f}s | {p95:>5.2f}s | "
        f"{len(per_replica):>8} | {' '.join(str(n) for n in sorted(per_replica.values(), reverse=True))}"
    )


def main() -> None:
    levels = [int(arg) for arg in sys.argv[1:]] or [1, 4, 8, 16, 32]
    print("concurrency |    p50 |    p95 | replicas | requests per replica")
    for concurrency in levels:
        run(concurrency)


if __name__ == "__main__":
    main()
