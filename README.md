
# VOLKOV: Autonomous CTI Pipeline

![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![Infrastructure](https://img.shields.io/badge/Infra-Terraform-purple)
![License](https://img.shields.io/badge/License-MIT-green)

**Volkov** is an autonomous, air-gapped Cyber Threat Intelligence (CTI) pipeline designed to monitor, attribute, and visualize global and Russia-specific cyber threats.

It leverages a **Store-and-Forward** architecture to maintain a strict air gap between the collection infrastructure (The Ghost) and the analysis environment (The Analyst). The system aggregates intelligence from Tor leak sites, Telegram channels, and C2 feeds into a unified visualization suite.

---

## 🏗️ Architecture

The system is split into three isolated zones to prevent attribution and lateral movement from threat actors.

![System Architecture](docs/images/volkov_architecture.png)
*(See `docs/architecture.md` for detailed network diagrams)*

### 1. The Ghost (Collection Node)
* **Location:** DigitalOcean VPS (Amsterdam)
* **Role:** A disposable, hardened "listening post" that scrapes hostile environments.
* **Capabilities:**
    * **Hybrid Scraping:** Simultaneous ingestion of Telegram channels (MTProto) and Tor `.onion` leak sites (SOCKS5).
    * **Dynamic Targeting:** Auto-fetches active ransomware URLs from upstream repositories (Ransomwatch) to handle infrastructure churn.
    * **Self-Defense:** Monitors its own `auditd` logs to detect and ban intrusion attempts.
* **Exfiltration:** Pushes encrypted JSON packets to an S3 "Dead Drop." No inbound ports are open.

### 2. The Airlock (Transport Layer)
* **Technology:** S3-compatible Object Storage (Filebase/Decentralized)
* **Role:** Acts as a one-way data diode. The Ghost pushes data here; the Analyst pulls it. The two nodes never communicate directly.

### 3. The Analyst (Processing Node)
* **Location:** On-Premise Proxmox Lab (Texas)
* **Role:** Secure ingestion, enrichment, and visualization.
* **Enrichment Engine:**
    * **Geospatial:** Converts C2 IPs and Victim HQs into physical coordinates (Nominatim/IPWhois).
    * **Firmographics:** Classifies victims by Sector (Finance, Gov, Health) and Org Type.
    * **TTP Analysis:** Extracts MITRE ATT&CK techniques from unstructured text.

---

## 🖥️ Operational Dashboards

The intelligence output is organized into two primary Grafana dashboards:

### 🌎 Dashboard 1: General Threat Tracking
A tactical view of the global ransomware and cybercrime landscape.
* **Victim Feed:** Live stream of new victims posted by major ransomware cartels (LockBit, Qilin, 8Base, Play).
* **Kinetic Map:** "Swoosh" map visualizing attack vectors (Attacker Origin $\to$ Victim HQ).
* **Underground Market:** Listings from crimeware forums selling access, databases, and military documents.

### 🇷🇺 Dashboard 2: Russian Operations Center
A specialized strategic view focused on Russian state and hybrid threats, organized into three operational rows:

* **Row 1: Russian APTs & Hacktivism**
    * Aggregates strategic reporting (CISA/Mandiant) on APT28/29/Sandworm.
    * Tracks operational orders and DDoS targets from hacktivist groups like **NoName057(16)** and **Killnet**.
* **Row 2: C2 Infrastructure**
    * Live map of active Command & Control servers (Cobalt Strike, Sliver, Metasploit).
    * breakdown of malware tooling currently deployed by threat actors.
* **Row 3: Internal Defense (Auditd)**
    * **Self-Monitoring:** Real-time watchdog panel showing failed SSH logins and file tampering attempts on the collection infrastructure itself.

---

## 📂 Repository Structure

```text
project_volkov/
├── docs/                 # Architectural documentation & Threat Models
├── infrastructure/       # Terraform & Cloud-Init scripts for Ghost VPS
├── ghost/                # COLLECTION ENGINE
│   ├── src/              # Scrapers (Telegram, Tor, RSS, C2)
│   └── Dockerfile        # Hardened container definition
├── analyst/              # INTELLIGENCE ENGINE
│   ├── src/              # Ingestor, Enrichment, & Normalization logic
│   └── dashboards/       # Grafana JSON models (Dashboards)
└── scripts/              # Dev tools, simulations, and backfill utilities
````

-----

## 🚀 Getting Started

### Prerequisites

  * **DigitalOcean Account** (for the Ghost VPS)
  * **Proxmox/Docker Environment** (for the Analyst Node)
  * **Telegram API Keys** (for scraping)
  * **S3 Bucket** (Filebase or AWS)

### Deployment

Detailed deployment instructions are available in the **[Deployment Guide](https://www.google.com/search?q=docs/deployment.md)**.

**Quick Start (Analyst Node):**

```bash
cd analyst
docker compose up -d
# Access Grafana at http://localhost:3000
```

-----

## 🛡️ Security & OpSec

This tool is designed for **Passive Intelligence Collection**.

  * **No Active Scanning:** The scraper never "touches" target infrastructure beyond standard HTTP requests.
  * **Identity Protection:** All Tor traffic is routed through a localized SOCKS5 proxy.
  * **Data Sanitization:** Input text is sanitized to prevent dashboard XSS or injection attacks.

-----

## ⚖️ Legal Disclaimer

*This project is for educational and defensive research purposes only. The author is not responsible for any misuse of the information or code provided herein. Scraping data from the dark web carries inherent risks; ensure you comply with all local laws and terms of service.*

```
```
