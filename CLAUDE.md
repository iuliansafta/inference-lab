# CLAUDE.md

One Scaleway GPU instance (Terraform) configured by Ansible: k3s, NVIDIA device plugin and DCGM exporter, kube-prometheus-stack, and vLLM serving one model. `make bench` measures it. The layout and Makefile verbs follow `../vps-infra` and `../nas-infra`; keep them aligned.

## Context

- `docs/DESIGN.md`: why each choice was made, what was checked against upstream sources, and what is open until the first run on hardware. Read it before changing the design.
- `NOTES.local.md` (git-ignored, may be absent): private notes. Read them before you write to a tracked file.

## Commands

- `make syntax`, `make lint`, `make test` run without the instance.
- `make preflight` / `apply` / `verify` / `bench` take `VARIANT=<key of vllm_variants>` (default `bf16`).
- `make infra` / `destroy` wrap Terraform. The inventory reads the host's address from `terraform output`, so nothing else holds it.

## Things that are easy to get wrong

- **GPU runtime.** The node's default runtime stays runc. Every pod that needs the GPU sets `runtimeClassName: nvidia`, which k3s creates once it finds the NVIDIA toolkit at startup. The vLLM image sets `NVIDIA_VISIBLE_DEVICES=all`, so a pod under the nvidia runtime sees the GPU even without a `nvidia.com/gpu` limit; only the vLLM server requests it.
- **One GPU.** The Deployment uses `Recreate`, and the vllm role waits on `rollout status`, not on the Available condition, which the old pod still reports during a variant change.
- **Two interpreters.** Plays that use `kubernetes.core` set `ansible_python_interpreter` to the venv the k3s role creates. Tasks delegated to localhost override it back to `ansible_playbook_python`, or they look for the venv on the laptop.
- **Benchmark windows.** The Prometheus queries in `roles/bench/tasks/run.yml` cover exactly one run, measured from job start to completion. The 5s scrape interval in the monitoring role is what makes a two-minute window meaningful.
- **Counters get `_total`.** vLLM registers `vllm:num_preemptions`; Prometheus sees `vllm:num_preemptions_total`.
- **Result keys.** `scripts/report.py` reads the keys `vllm bench serve --save-result` writes in `vllm/benchmarks/serve.py` at the pinned tag. Check them when bumping `vllm_version`, along with the vendored `roles/monitoring/files/vllm-dashboard.json`.
