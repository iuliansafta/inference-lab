# Design

Why the lab is built the way it is, what was checked while building it, and what is still open. Written on 2026-11-03, before the first run on hardware.

## Goal

Show LLM inference infrastructure end to end on European cloud: provision a GPU host from code, serve an open-weights model, observe it, and answer one capacity question with evidence. How many concurrent requests can one 24 GB GPU serve before latency degrades, what limits it, and how much do fp8 weights or an fp8 KV cache move that limit?

The output is a results table and a short write-up, not a production service. Everything is torn down between sessions.

## Decisions

| Decision | Why |
|---|---|
| Scaleway `L4-1-24G` in `fr-par-1` | €0.79 per hour, billed per minute, European provider. One NVIDIA L4 (Ada, 24 GB) supports bf16 and fp8. |
| Mistral 7B Instruct v0.3 | Not gated on Hugging Face, so no token is needed. Made by a European company. Fits a 24 GB card in bf16 with room left for KV cache. |
| k3s set up by Ansible, not Scaleway's managed Kubernetes (Kapsule) | Provisioning the GPU node from code is part of what the lab shows. Kapsule would hide it. |
| Default runtime stays runc; GPU pods set `runtimeClassName: nvidia` | Explicit per pod. k3s creates the `nvidia` RuntimeClass when it finds the NVIDIA toolkit at startup. |
| Deployment strategy `Recreate` | There is one GPU. The old pod must release it before the new one starts. |
| `--max-model-len 32768` | Mistral's own limit. An 8k cap is too small: first-round prompts on the first 100 ARC-AGI-1 evaluation tasks reach 12,757 tokens, and vLLM refuses a prompt over the cap. Refinement prompts reach 49,089 tokens, and 5 of those 100 tasks go over even 32,768. A long prompt can claim most of the KV cache, but samples of one prompt share its blocks. |
| Benchmark runs inside the cluster as a Job, from the same vLLM image | No network between client and server distorts latency, and the client version matches the server. |
| Prometheus queries per run window, 5s scrape interval | `vllm bench serve` sees only the client side. The server-side peaks (KV cache, waiting requests, preemptions) for the same window explain where latency jumps. Without a short scrape interval a two-minute run has too few samples. |
| Concurrency 1, 8, 32, 64, 128 | 64 and 128 are above the estimated cache capacity (next section), so the saturation point falls inside the sweep. |
| Variants `bf16`, `fp8`, `fp8-kv` | Two different ways to free memory for KV cache: smaller weights, or a smaller cache per token. |
| Grafana, Prometheus and vLLM only through an SSH tunnel | The security group opens port 22 only. |

## KV cache estimate

This is arithmetic, not a measurement.

- Mistral 7B has 32 layers, 8 KV heads and a head size of 128. In bf16, one token of cache takes 2 (K and V) × 32 × 8 × 128 × 2 bytes = 128 KiB.
- The L4 has about 22.5 GiB usable. At `--gpu-memory-utilization 0.90` vLLM may use about 20 GiB. The weights take about 13.5 GiB, and activations and CUDA graphs take another 1 to 2 GiB.
- That leaves about 5 GiB of cache, so about 40k tokens. At 512 + 256 tokens per request, that is roughly 50 requests at once.

vLLM logs its real cache size at startup (`KV cache size`, `Maximum concurrency`). `make verify` prints those lines. Record them with the results.

## Checked while building

Checked against the source on 2026-11-03:

- **vLLM v0.32.0.** Metric names from `vllm/v1/metrics/loggers.py`. Counters get `_total` in Prometheus. `vllm bench serve` flags and the result keys (`request_throughput`, `output_throughput`, `p<N>_<metric>_ms`, `failed`) from `vllm/benchmarks/serve.py`. The `random` dataset does not need pandas or datasets, which the image does not install. The image entrypoint is `vllm serve`. The dashboard was vendored from `examples/observability/prometheus_grafana/grafana.json`.
- **Helm charts.** `nvidia-device-plugin` 0.20.1, `dcgm-exporter` 4.8.4 and `kube-prometheus-stack` 92.17.1 were rendered with `helm template` and the role's values.
- **k3s.** NVIDIA runtime detection and RuntimeClasses follow the k3s documentation, section "NVIDIA Container Runtime". The pinned version is v1.37.1+k3s1.
- **Scaleway.** The image `ubuntu_noble_gpu_os_13_nvidia` accepts `L4-1-24G` in `fr-par-1`, according to the marketplace API. Terraform provider 2.89.0 validates. Scaleway's tutorials log in as `root`.
- **Repository.** `make syntax`, `make lint` (ansible-lint production profile, yamllint, terraform fmt) and `make test` pass.

## Open until the first run

- Whether the benchmark Job works under the nvidia runtime without a GPU limit.
- Whether `--quantization fp8` starts on the L4. `fp8-kv` is the fallback.
- Whether the GPU image ships the NVIDIA container toolkit. The role installs it if missing.
- Whether a second `make apply` reports `changed=0`.
- Whether a new Scaleway account needs a GPU quota increase or a deposit. The pricing page does not say.

## Next

1. Run the full loop for `bf16`, `fp8` and `fp8-kv`, then commit `results/`.
2. Record vLLM's startup cache size next to the estimate above, and explain any gap.
3. Write up where each variant saturates and why, with Grafana screenshots.
4. Serve the same model through Ray Serve on KubeRay and run the same benchmark. Many LLM platforms put Ray Serve in front of vLLM to manage replicas, so the comparison shows what that layer costs in latency and what its metrics add or hide. Start this after the `bf16` run works, not before.
