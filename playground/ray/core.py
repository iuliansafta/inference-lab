# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["ray[serve]==2.59.0"]
# ///
import os
import time

import ray

TASKS = 8


@ray.remote
def square(x: int) -> tuple[int, int]:
    time.sleep(1)
    return x * x, os.getpid()


@ray.remote
class Counter:
    def __init__(self) -> None:
        self.total = 0

    def add(self, n: int) -> int:
        self.total += n
        return self.total


@ray.remote(num_gpus=1)
def needs_a_gpu() -> str:
    return "scheduled and ran"


def main() -> None:
    ray.init()
    print("cluster resources:", ray.cluster_resources())

    print(f"\n1. Tasks: {TASKS} one-second calls, run in parallel by worker processes")
    start = time.monotonic()
    results = ray.get([square.remote(i) for i in range(TASKS)])
    print(f"   squares {[r for r, _ in results]}")
    print(f"   {len({pid for _, pid in results})} worker processes, {time.monotonic() - start:.1f}s wall time (sequential would take {TASKS}s)")

    print("\n2. Actor: one process that keeps its state between calls")
    counter = Counter.remote()
    for n in (5, 10, 20):
        print(f"   add({n}) -> total {ray.get(counter.add.remote(n))}")

    print("\n3. Resources: a task that asks for a GPU")
    ready, _ = ray.wait([needs_a_gpu.remote()], timeout=5)
    print("   " + (ray.get(ready[0]) if ready else "still pending after 5s: no node offers a GPU, so Ray never schedules it"))

    input("\nDashboard: http://127.0.0.1:8265 (Jobs, Actors, Cluster tabs). Press Enter to shut down.")
    ray.shutdown()


if __name__ == "__main__":
    main()
