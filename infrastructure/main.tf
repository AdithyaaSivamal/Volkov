terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

provider "digitalocean" {
  token = var.do_token
}

# 1. SSH Key
# Uploads your local public key to DigitalOcean so it can be injected
resource "digitalocean_ssh_key" "volkov_key" {
  name       = "Volkov Ops Key"
  public_key = file(var.pvt_key_path)
}

# 2. The Ghost Droplet
resource "digitalocean_droplet" "ghost" {
  image  = "debian-12-x64"
  name   = "volkov-ghost-node-v1"
  region = var.region
  size   = "s-1vcpu-1gb" # $6/mo tier

  # Security Features
  ipv6               = true
  monitoring         = true
  private_networking = true

  # Attach Key
  ssh_keys = [
    digitalocean_ssh_key.volkov_key.fingerprint
  ]

  # Inject the Bash Script
  user_data = file("user_data.sh")

  # Tagging for Asset Management
  tags = ["volkov", "production", "cti"]
}
