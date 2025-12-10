output "ghost_ip" {
  description = "Public IP of the Ghost Node"
  value       = digitalocean_droplet.ghost.ipv4_address
}

output "ssh_command" {
  description = "Command to connect"
  value       = "ssh -i ../volkov_key volkov_op@${digitalocean_droplet.ghost.ipv4_address}"
}
