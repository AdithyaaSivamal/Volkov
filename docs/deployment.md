
# 🛠️ Volkov Deployment Guide

This guide details the step-by-step procedure to deploy the full **Volkov CTI Pipeline**, from the cloud collection node to the on-premise analyst station.

## 📋 Prerequisites

### Infrastructure
* **Cloud Provider:** DigitalOcean (for the Ghost Node).
* **On-Premise:** Proxmox Server or Dedicated Linux Box (Ubuntu 22.04+ recommended).
* **Storage:** S3-Compatible Bucket (Filebase, AWS, or MinIO).

### API Credentials
1.  **Telegram:** `API_ID` and `API_HASH` (Get from my.telegram.org).
2.  **S3:** `ACCESS_KEY` and `SECRET_KEY`.
3.  **ThreatFox/Ransomwatch:** (Optional) API keys if rate limits are hit.

---

## ☁️ Phase 1: The Ghost Node (Collection)

The Ghost Node is designed to be **ephemeral**. It can be destroyed and redeployed in minutes.

### 1. Provisioning
Use the Terraform scripts in `infrastructure/` to spin up the Droplet.
```bash
cd infrastructure
terraform init
terraform apply -var="do_token=${DO_PAT}"
````

### 2\. Configuration

SSH into the new VPS. Create the environment file in the application directory.

```bash
mkdir -p /app/data
nano /app/.env
```

**Required Variables:**

```ini
TG_API_ID=123456
TG_API_HASH=abcdef1234567890...
TG_PHONE=+15550001234
S3_ENDPOINT=[https://s3.filebase.com](https://s3.filebase.com)
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_BUCKET=volkov-dead-drop-01
```

### 3\. Deployment

Launch the collection stack.

```bash
cd /app
docker compose -f docker-compose.ghost.yml up -d --build
```

### 4\. Authentication (First Run Only)

You must interactively authenticate with Telegram once to generate the session file.

```bash
docker compose -f docker-compose.ghost.yml run --rm ghost_scraper
# Enter phone code and 2FA password when prompted.
```

### 5\. Activate Self-Defense

Enable the system-level watchdog.

```bash
sudo cp scripts/volkov-security.service /etc/systemd/system/
sudo systemctl enable --now volkov-security
```

-----

## 🏠 Phase 2: The Analyst Node (Processing)

This node should reside behind a strict firewall (e.g., FortiGate) with **no inbound access**.

### 1\. Database & Dashboard Stack

Deploy InfluxDB and Grafana using Docker.

```bash
cd analyst
docker compose up -d
```

### 2\. Ingestor Setup

Install Python dependencies on the host (or in a dedicated LXC).

```bash
pip3 install -r analyst/requirements.txt
```

*(Ensure `ingestor.py` and `volkov_enrich.py` are in the same directory).*

### 3\. Execution

Start the ingestion loop. It is recommended to run this as a Systemd service (similar to the Ghost watchdog) for persistence.

```bash
python3 src/ingestor.py
```

-----

## 📊 Phase 3: Dashboard Configuration

1.  Access Grafana at `http://<ANALYST_IP>:3000`.
2.  Login (Default: `admin` / `admin`).
3.  Add Data Source: **InfluxDB (Flux)**.
      * URL: `http://influxdb:8086`
      * Organization: `volkov_intel`
      * Token: `(Your configured admin token)`
4.  Import Dashboards:
      * Upload JSON files from `analyst/dashboards/`.

## 🔄 Maintenance & Updates

  * **Ghost Rotation:** It is recommended to destroy and re-provision the Ghost VPS every 30 days to rotate the IP address.
  * **Session Management:** If the Telegram session invalidates, repeat Phase 1, Step 4.

<!-- end list -->


