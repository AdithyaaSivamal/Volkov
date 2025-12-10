# System Architecture

**Project Volkov** is an autonomous Cyber Threat Intelligence (CTI) pipeline designed to monitor high-risk adversarial environments (Russian Crimeware & State-Sponsored Actors) without exposing the analyst's infrastructure to attribution or counter-attacks.

---

## 1. The "Ghost" Protocol Design Philosophy
This system was architected with a specific threat model in mind: **Presumption of Compromise.**

When scraping hostile actors (Ransomware gangs, Hacktivist auxiliaries), we assume the collection node will eventually be identified, fingerprinted, or targeted. Therefore, the architecture prioritizes **non-attribution** and **prevention of lateral movement** over convenience.

### Core Tenets
* **Ephemeral Infrastructure:** The collection node ("Ghost") is defined entirely in Terraform. It can be destroyed and re-provisioned in <3 minutes to rotate IP reputation or sanitize a compromised environment.
* **Strict Air Gap:** There is **zero network connectivity** between the Collection Node (Amsterdam) and the Analyst Node (US).
* **Data Diode Pattern:** Data flows one way: `Dirty -> Clean`. The Ghost node has no credentials to access the Analyst Node, and the Analyst Node never connects directly to targets.
* **Store-and-Forward:** We utilize an asynchronous object storage dead drop (S3) to decouple collection from analysis. This breaks the TCP/IP chain, preventing correlation attacks.

---

## 2. High-Level Topology

<img width="744" height="652" alt="image" src="https://github.com/user-attachments/assets/8338b743-9265-4b34-a57b-be8b83b76eed" />

The system is segmented into three isolated zones with strict trust boundaries.

### Zone 1: The Ghost (Collection Node)
* **Infrastructure:** DigitalOcean Droplet (Debian 12), provisioned via Terraform in an offshore jurisdiction (Amsterdam).
* **Role:** High-risk data acquisition.
* **Connectivity:**
    * **Outbound:** Tor Network (SOCKS5), Telegram MTProto (443), S3 API.
    * **Inbound:** **Blocked (Drop All)**. SSH access is restricted to key-based auth on a non-standard port, monitored by Fail2Ban.
* **Components:**
    * **Scraper Engine:** A Python-based asynchronous loop utilizing a **Strategy Pattern** to handle diverse data sources (Telegram Channels, Onion Sites, RSS Feeds).
    * **Tor Sidecar:** A Dockerized Tor proxy responsible for routing all `.onion` traffic, ensuring the host IP is never leaked to ransomware leak sites.
    * **Self-Defense Module:** A system-level watchdog (`auditd` + Python) that monitors file integrity and auth logs, treating the collector itself as a sensor.

### Zone 2: The Airlock (Transport Layer)
* **Infrastructure:** S3-Compatible Object Storage (Filebase/Decentralized).
* **Role:** Asynchronous buffer.
* **Security:**
    * JSON payloads are serialized and pushed by the Ghost.
    * Files are pulled and deleted by the Analyst.
    * This acts as a "Protocol Break," ensuring that a remote code execution (RCE) exploit on the Ghost cannot tunnel traffic back to the home lab.

### Zone 3: The Analyst (Processing Node)
* **Infrastructure:** On-Premise Proxmox Container (LXC).
* **Role:** Secure ingestion, enrichment, and visualization.
* **Components:**
    * **Ingestor Service:** A polling service that retrieves data from the Airlock.
    * **Enrichment Engine:** Performs "Just-in-Time" intelligence gathering:
        * **Geospatial:** Maps Victim Names -> Physical HQ locations (Wikidata/Nominatim).
        * **Infrastructure:** Maps C2 IPs -> ASNs and Hosting Providers (RDAP).
        * **Classification:** Tags victims by Industry Sector and Organization Type.
    * **Time-Series Database:** InfluxDB v2 (Flux) for high-performance storage of event streams.
    * **Command Center:** Grafana visualization layer.

---

## 3. Data Pipeline & Logic

<img width="626" height="642" alt="image" src="https://github.com/user-attachments/assets/7fbeb3ab-d871-48af-a00d-d7167fc5baac" />

The system processes intelligence in four distinct stages:

### Stage A: Dynamic Targeting (The "Hunter")
Instead of using static target lists, the Ghost dynamically acquires targets at runtime:
1.  **Ransomware:** Queries upstream repositories (e.g., `ransomwatch`) to fetch the latest live `.onion` mirrors for groups like LockBit and Qilin.
2.  **C2 Infrastructure:** Ingests high-fidelity indicators from community feeds (ThreatFox) to track active command-and-control servers.
3.  **Discovery:** Uses "Snowball Sampling" on Telegram—parsing forwarded messages to discover new, relevant channels automatically.

### Stage B: Polymorphic Collection
The scraper utilizes a **Strategy Pattern** to parse different data formats using a unified interface:
* **`hacktivist` Strategy:** regex-based extraction of DDoS targets (IPs/Domains) and Russian operational slang (`цель`, `атака`).
* **`market` Strategy:** NLP-lite extraction of "For Sale" listings, categorizing items (Access vs. Data) and extracting prices.
* **`onion_general` Strategy:** HTML parsing of Tor leak sites to extract victim names.

### Stage C: Ingestion & Enrichment
The Analyst node performs CPU-intensive enrichment locally to avoid tipping off targets:
1.  **Sanitization:** Strips non-printable characters and HTML entities to prevent dashboard injection attacks.
2.  **Attribution:** Normalizes actor names (e.g., "lockbit3" == "LockBit 3.0").
3.  **Geolocation:** Converts "Company Name" to "Lat/Lon" coordinates using a waterfall approach (Nominatim API -> Wikidata Fallback).

### Stage D: Visualization
Data is presented in two operational views:
1.  **Tactical Dashboard:** Real-time feed of victims, active DDoS targets, and underground market listings.
2.  **Strategic Dashboard:** Long-term trend analysis of Russian APT activity, C2 infrastructure heatmaps, and MITRE ATT&CK technique prevalence.

---

## 4. Security Controls

| Control Layer | Implementation | Purpose |
| :--- | :--- | :--- |
| **Network** | UFW Deny-All Inbound | Prevents scanning/exploitation of the collector. |
| **Identity** | SSH Key-Only / Root Disabled | Mitigates brute-force attacks. |
| **Application** | Docker Containerization | Isolates scraper dependencies from the host OS. |
| **Anonymity** | Local SOCKS5 Tor Proxy | Prevents correlation of collection traffic. |
| **Integrity** | `auditd` File Watches | Detects tampering with source code or environment variables. |
| **Monitoring** | Internal Watchdog | Reports failed auth attempts (Fail2Ban) to the dashboard. |

---

## 5. Future Scalability
* **Queueing:** Replace S3 Polling with **RabbitMQ** or **Kafka** for higher throughput.
* **LLM Integration:** Replace Regex parsing with local LLM (Llama-3) for sentiment analysis of Russian chatter.
* **STIX/TAXII:** Export enriched data in standard STIX 2.1 format for integration with enterprise TIPs (MISP/OpenCTI).
