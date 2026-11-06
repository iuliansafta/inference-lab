variable "zone" {
  type    = string
  default = "pl-waw-2"
}

variable "instance_type" {
  type    = string
  default = "L4-1-24G"
}

variable "image" {
  type    = string
  default = "ubuntu_noble_gpu_os_13_nvidia"
}

# The vLLM image is about 10 GB and the model weights about 15 GB per variant.
variable "root_volume_gb" {
  type    = number
  default = 150
}

variable "ssh_public_key_file" {
  type    = string
  default = "../keys/lab.pub"
}

variable "ssh_allowed_cidr" {
  type        = string
  description = "Who may reach port 22, such as 203.0.113.7/32. Set it in terraform/terraform.tfvars."
}
