# Scaleway injects the project's SSH keys into root at first boot, so the key
# must exist before the server does.
resource "scaleway_iam_ssh_key" "lab" {
  name       = "inference-lab"
  public_key = trimspace(file(var.ssh_public_key_file))
}

resource "scaleway_instance_ip" "lab" {}

# Only SSH is open. Grafana, Prometheus and the vLLM API are reached through
# `make tunnel`.
resource "scaleway_instance_security_group" "lab" {
  name                    = "inference-lab"
  inbound_default_policy  = "drop"
  outbound_default_policy = "accept"

  inbound_rule {
    action   = "accept"
    protocol = "TCP"
    port     = 22
    ip_range = var.ssh_allowed_cidr
  }
}

resource "scaleway_instance_server" "lab" {
  name              = "inference-lab"
  type              = var.instance_type
  image             = var.image
  ip_id             = scaleway_instance_ip.lab.id
  security_group_id = scaleway_instance_security_group.lab.id

  root_volume {
    volume_type = "sbs_volume"
    size_in_gb  = var.root_volume_gb
  }

  depends_on = [scaleway_iam_ssh_key.lab]
}
