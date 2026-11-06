# Ray playground

Three small scripts to learn what Ray does before the lab puts Ray Serve in front of vLLM. Everything runs on a laptop CPU, with no GPU and no cluster. `uv` installs Ray 2.59.0 the first time a script runs; each script declares its own dependencies.

Run the scripts from this directory. Ray packages the current directory for its workers, so starting from the repository root would copy the whole repository into Ray's object store.

```sh
cd playground/ray
```

## 1. Tasks, actors and resources

```sh
uv run core.py
```

The script starts a one-machine Ray cluster and shows Ray's three basic ideas:

1. **Tasks.** A function decorated with `@ray.remote` runs in a pool of worker processes. Eight one-second calls finish in about 1.5 seconds instead of 8.
2. **Actors.** A class decorated with `@ray.remote` becomes one long-lived process that keeps its state between calls. A loaded model is an actor: the weights load once, then the actor serves many requests.
3. **Resources.** A task that asks for `num_gpus=1` stays pending, because no node in this cluster offers a GPU. Ray places work only where the requested resources are free. That rule is how a real cluster keeps two models off the same GPU.

Before you press Enter, open the dashboard at <http://127.0.0.1:8265>. The **Cluster** tab shows the node and its resources, and the **Actors** tab shows the `Counter` actor.

Try this:

- Set `TASKS = 32`. Each task takes one CPU, so on a 16-CPU laptop they run in two waves and the wall time is about 3 seconds (2 seconds of work plus starting 16 worker processes). Resources limit parallelism, not your code.
- Change `num_gpus=1` to `num_cpus=1`. The pending task now runs.

## 2. Ray Serve: replicas, slots and queueing

Terminal 1:

```sh
uv run serve_app.py
```

Terminal 2:

```sh
uv run load.py            # concurrency 1, 4, 8, 16, 32
```

`serve_app.py` serves a fake model. Each request "generates" 50 tokens at 20 ms per token, so it takes 1 second when nothing waits. Two deployments make up the app:

- `FakeModel` runs as 2 replicas. Each replica accepts at most 4 requests at once (`max_ongoing_requests=4`).
- `Gateway` receives HTTP requests and calls `FakeModel` through a handle, the way an agent calls a model.

So the app holds 2 × 4 = 8 requests at once. Measured on this laptop:

```text
concurrency |    p50 |    p95 | replicas | requests per replica
          1 |  1.01s |  1.01s |        2 | 2 2
          4 |  1.01s |  1.02s |        2 | 9 7
          8 |  1.01s |  1.02s |        2 | 16 16
         16 |  2.19s |  2.58s |        2 | 32 32
         32 |  4.56s |  5.63s |        2 | 64 64
```

Latency stays flat up to 8 concurrent requests, then doubles and quadruples. Requests above the capacity wait in Ray's router for a free slot. The lab's benchmark looks for the same shape on the GPU, where the slots are the sequences that fit in vLLM's KV cache.

Try this (stop the server with Ctrl+C between runs):

- `REPLICAS=1 uv run serve_app.py`, then `REPLICAS=4 ...`. Predict where the latency jumps before you run `load.py`.
- Set `SLOTS_PER_REPLICA = 8` in `serve_app.py`. That is what the lab's `fp8-kv` variant tries to do on the GPU: make each request's cache smaller so more requests fit in one engine.
- `REPLICAS=auto uv run serve_app.py`, then `uv run load.py 2 32 32 32`. Watch the **Serve** tab in the dashboard. Serve starts with 1 replica and adds replicas up to 4 while requests queue:

  ```text
  concurrency |    p50 |    p95 | replicas | requests per replica
            2 |  1.01s |  1.02s |        1 | 8
           32 |  2.56s |  9.78s |        4 | 54 25 25 24
           32 |  2.30s |  3.31s |        4 | 32 32 32 32
  ```

  The 9.8-second p95 in the second row is the cost of scaling up while requests wait. A fake replica starts in a second. A real LLM replica must load gigabytes of weights onto a GPU first, which takes minutes, so many LLM deployments fix the replica count to the number of GPUs instead of autoscaling.
- Wait 30 seconds without traffic, then run `uv run load.py 1`. Serve has started to remove replicas.

## How the fake maps to a real deployment

| In the playground | In a real LLM deployment |
|---|---|
| One `FakeModel` replica | One vLLM engine. It would request `ray_actor_options={"num_gpus": 1}`, or more GPUs with tensor parallelism. |
| `max_ongoing_requests` | How many sequences fit in the engine's KV cache at once. |
| `asyncio.sleep` per token | Decoding. The slots progress at the same time, like vLLM's continuous batching. |
| `Gateway` calling a handle | An agent or orchestrator calling the model inside the same Ray app. |
| Requests waiting in Ray's router | `vllm:num_requests_waiting`, except that the queue now lives in Ray. |

The last row is the question for the lab's Ray phase. If Serve caps a replica below what the engine can hold, the queue forms in Ray, and vLLM's waiting-requests metric reads zero while users wait. Which metrics show the cause then is something to measure, not assume.

## Cleanup

Ctrl+C stops the server and its Ray cluster. Serve prints a `KeyboardInterrupt` traceback when it stops; that is expected. If a Ray process is left over:

```sh
uv run --with 'ray[serve]==2.59.0' ray stop --force
```

Ray 2.59 also writes an authentication token to `~/.ray/auth_token` the first time it starts.
