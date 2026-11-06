# inference-lab

A one-GPU lab that serves an open-weights model with [vLLM](https://docs.vllm.ai) on k3s, monitors it with Prometheus, Grafana and NVIDIA's DCGM exporter, and benchmarks it to find where it saturates and why.

It runs on one Scaleway `L4-1-24G` instance in Paris (an NVIDIA L4, 24 GB). The model is Mistral 7B Instruct v0.3.

> **Status:** syntax-checked, linted and template-rendered, but not yet run on the GPU. The first `make apply` on the instance is the real test.

## What the benchmark answers

`make bench` runs `vllm bench serve` at concurrency 1, 8, 32, 64 and 128 (512 prompt tokens, 256 output tokens). For each run it saves the client's view (throughput, time to first token, time per output token, end-to-end latency) and asks Prometheus for the server's view of the same window: peak KV cache use, peak running and waiting requests, preemptions and mean GPU utilisation.

So the row where latency jumps also shows the cause. On a 24 GB card the expected limit is the KV cache: once it is full, new requests wait for a batch slot and time to first token climbs. `make verify` prints vLLM's own KV cache sizing from its startup log.

Variants compare serving configurations on the same card:

| Variant | `vllm serve` flags | Question |
|---|---|---|
| `bf16` | none | Baseline. |
| `fp8` | `--quantization fp8` | Smaller weights leave more memory for KV cache. How much more concurrency? |
| `fp8-kv` | `--kv-cache-dtype fp8` | Keep bf16 weights, halve the cache's size per token instead. |

## Cost

The instance costs €0.79 per hour (Scaleway's price list, November 2026). A working session of a few hours costs a few euros. Destroy the instance between sessions. The Hugging Face cache is on the instance, so each rebuild downloads the weights again (about 15 GB).

## Prerequisites

- A Scaleway API key in `.env` or the environment: `SCW_ACCESS_KEY`, `SCW_SECRET_KEY`, `SCW_DEFAULT_PROJECT_ID`. The Makefile loads `.env`, which is git-ignored.
- Your own address in `terraform/terraform.tfvars`, also git-ignored: `ssh_allowed_cidr = "203.0.113.7/32"`. Only this address can reach port 22. If your address changes, update the file and run `make infra` again.
- Terraform 1.9 or later, ansible-core, `make`, and Python 3 (for the report).
- The public half of your SSH key in `keys/lab.pub`. Terraform registers it with the project, and Scaleway installs it for `root` at first boot; Scaleway's own tutorials log in as `root`. SSH goes through the Proton Pass agent (`~/.ssh/proton-pass-agent.sock`), which serves the keys in the `SSH Keys` vault.
- GPU quota on the Scaleway project. Check the console's quotas page first.

## Run it

```sh
make deps                        # kubernetes.core collection, terraform init
make infra                       # instance, public IP, security group (SSH only)
make apply                       # NVIDIA toolkit, k3s, monitoring, vLLM (bf16)
make verify                      # GPU, scheduling, a chat completion, scraping
make bench                       # results/bf16/c*.json

make apply VARIANT=fp8           # swap the model server to another variant
make verify VARIANT=fp8
make bench VARIANT=fp8

make report                      # results/README.md, one table per variant
make tunnel                      # Grafana :3000, Prometheus :9090, vLLM :8000
make destroy
```

`make tunnel` prints the Grafana admin password, which Ansible generates into `.secrets/grafana-admin`. Grafana has two dashboards: vLLM's own (vendored from the vLLM repository at the pinned tag) and NVIDIA's DCGM exporter dashboard.

Alerts are defined in `roles/vllm/templates/vllm.yml.j2`: server down, requests queueing, KV cache over 90%, preemptions, and GPU temperature. They show in Prometheus and Alertmanager; no receiver is configured.

## Layout

| Path | Contents |
|---|---|
| `terraform/` | The Scaleway instance, its IP, security group and SSH key. |
| `roles/nvidia` | Requires a working driver (the image ships it); installs the container toolkit if missing. |
| `roles/k3s` | k3s, helm, and the Python client the `kubernetes.core` modules need. |
| `roles/monitoring` | NVIDIA device plugin, DCGM exporter, kube-prometheus-stack, the vLLM dashboard. |
| `roles/vllm` | The vLLM Deployment, Service, ServiceMonitor and alert rules. |
| `roles/bench` | One benchmark Job per concurrency level, plus the Prometheus queries for its window. |
| `scripts/report.py` | Results to Markdown tables. Tested in `tests/`. |
| `playground/ray/` | Laptop-sized Ray and Ray Serve exercises (CPU only), to learn what Ray adds before it goes in front of vLLM. |
| `results/` | Committed benchmark results. |

Every version is pinned in `inventory/group_vars/all.yml`, and `make preflight` rejects anything that is not an exact release.

## Checks

```sh
make syntax   # ansible-playbook --syntax-check
make lint     # ansible-lint (production profile), yamllint, terraform fmt
make test     # report.py
```
