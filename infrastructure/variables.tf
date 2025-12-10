variable "do_token" {
  description = "DigitalOcean Personal Access Token"
  type        = string
  sensitive   = true
}

variable "pvt_key_path" {
  description = "Path to your public SSH key (e.g. ../volkov_key.pub)"
  type        = string
  default     = "../volkov_key.pub"
}

variable "region" {
  description = "DigitalOcean Region"
  type        = string
  default     = "ams3" # Amsterdam (Offshore)
}
