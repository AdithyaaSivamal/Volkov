#!/bin/bash

# ==============================================================================
# ROLE:        Ghost VPS cloud-init script
# DESCRIPTION: Bootstraps a hardened, ephemeral Debian VPS for CTI collection.
#              Designed to be deployed via Terraform and destroyed periodically.
#
# SECURITY POSTURE:
#   1. Identity:   Creates 'volkov_op' user; Disables Root login & Password Auth.
#   2. Network:    UFW Firewall defaults to DENY INCOMING (except SSH).
#   3. Isolation:  Dockerized environment for scrapers (Tor/Telegram).
#   4. Auditing:   Configures Auditd to monitor file tampering & secret access.
#
# USAGE:       Injected automatically by Terraform into DigitalOcean Droplets.
# WARNING:     This script creates a lock-out environment. Ensure SSH keys are
#              correctly propagated via Terraform before applying.
# ==============================================================================

# --- 1. SYSTEM PREP ---
export DEBIAN_FRONTEND=noninteractive
apt-get update && apt-get upgrade -y
# Install dependencies including Security Tools (Auditd, Fail2Ban)
apt-get install -y ufw fail2ban curl unzip smbclient git python3-pip auditd

# --- 2. CREATE OPERATOR USER ---
# We never run as root.
useradd -m -s /bin/bash volkov_op
usermod -aG sudo volkov_op

# --- 3. SSH KEY MIGRATION ---
# DigitalOcean injects keys into /root/.ssh/authorized_keys.
# We move them to the operator and lock down root.
mkdir -p /home/volkov_op/.ssh
cp /root/.ssh/authorized_keys /home/volkov_op/.ssh/
chown -R volkov_op:volkov_op /home/volkov_op/.ssh
chmod 700 /home/volkov_op/.ssh
chmod 600 /home/volkov_op/.ssh/authorized_keys

# --- 4. SSH HARDENING ---
# Disable Root Login & Password Auth
sed -i 's/^PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh

# --- 5. FIREWALL (UFW) ---
# Default: Deny Incoming, Allow Outgoing
ufw default deny incoming
ufw default allow outgoing
# Allow SSH (Port 22)
ufw allow 22/tcp
# Enable
ufw --force enable

# --- 6. DOCKER INSTALLATION ---
curl -fsSL https://get.docker.com | sh
usermod -aG docker volkov_op

# --- 7. APPLICATION STRUCTURE ---
mkdir -p /opt/volkov/buffer
mkdir -p /app/data
chown -R volkov_op:volkov_op /opt/volkov
chown -R volkov_op:volkov_op /app

# --- 8. SECURITY MONITORING (Auditd) ---
# Apply "Industry Grade" syscall rules
# Watch critical files (Code & Secrets)
auditctl -a always,exit -F arch=b64 -F path=/home/volkov_op/scraper.py -F perm=wa -F key=volkov_code_tamper
auditctl -a always,exit -F arch=b64 -F path=/home/volkov_op/.env -F perm=war -F key=secret_access

# Persist Audit Rules
auditctl -l > /etc/audit/rules.d/volkov.rules
systemctl restart auditd

echo "[+] Volkov Ghost Node Provisioned Successfully"
