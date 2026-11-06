# Scaleway credentials for Terraform. Git-ignored.
-include .env
export SCW_ACCESS_KEY SCW_SECRET_KEY SCW_DEFAULT_ORGANIZATION_ID SCW_DEFAULT_PROJECT_ID

VARIANT ?= bf16
PLAY = ansible-playbook -e vllm_variant=$(VARIANT)
# Same flags as ansible_ssh_common_args in inventory/hosts.yml.
SSH_OPTS = -o IdentityAgent=~/.ssh/proton-pass-agent.sock -o IdentityFile=keys/lab.pub -o IdentitiesOnly=yes \
	-o UserKnownHostsFile=.secrets/known_hosts -o StrictHostKeyChecking=accept-new
HOST = root@$$(terraform -chdir=terraform output -raw public_ip)

.PHONY: deps infra destroy preflight syntax check apply verify bench report tunnel ssh test lint

deps:
	ansible-galaxy collection install -r requirements.yml
	terraform -chdir=terraform init
infra:
	mkdir -p .secrets
	terraform -chdir=terraform apply
# The known_hosts file goes too: a rebuild can reuse the address with a new host key.
destroy:
	terraform -chdir=terraform destroy
	rm -f .secrets/known_hosts
preflight:
	$(PLAY) playbooks/preflight.yml
syntax:
	$(PLAY) playbooks/site.yml playbooks/verify.yml playbooks/bench.yml --syntax-check
check:
	$(PLAY) playbooks/site.yml --check --diff
apply:
	$(PLAY) playbooks/site.yml
verify:
	$(PLAY) playbooks/verify.yml
bench:
	$(PLAY) playbooks/bench.yml
report:
	python3 scripts/report.py results > results/README.md
	@echo "Wrote results/README.md"
tunnel:
	@echo "Grafana http://localhost:3000 (admin / $$(cat .secrets/grafana-admin))"
	@echo "Prometheus http://localhost:9090 · vLLM http://localhost:8000/v1"
	ssh $(SSH_OPTS) -N -L 3000:127.0.0.1:30300 -L 9090:127.0.0.1:30090 -L 8000:127.0.0.1:30800 $(HOST)
ssh:
	ssh $(SSH_OPTS) $(HOST)
test:
	python3 -m unittest discover -s tests -v
lint:
	uvx --from ansible-lint ansible-lint
	uvx yamllint .
	terraform -chdir=terraform fmt -check -recursive
