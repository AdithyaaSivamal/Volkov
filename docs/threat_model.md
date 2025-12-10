
# 🛡️ Volkov Threat Model & Security Architecture

**Version:** 1.0
**Date:** 2025-12-09
**Author:** Adithyaa

## 1. System Overview
Volkov is a high-risk intelligence collection system. It actively interacts with criminal infrastructure (Tor hidden services) and monitors hostile actors. As such, the system is designed with a **"Presumption of Compromise"** for the collection node.

---

## 2. Trust Boundaries

| Zone | Trust Level | Description |
| :--- | :--- | :--- |
| **The Internet** | Untrusted (0) | Hostile environment containing malware, exploits, and surveillance. |
| **Ghost VPS** | Low Trust (1) | The "Dirty" node. We assume this node will eventually be detected or attacked. It contains NO credentials for the home lab. |
| **S3 Airlock** | Medium Trust (5) | The handover point. Data is encrypted at rest. Write-only for Ghost, Read-only for Analyst. |
| **Analyst Node** | High Trust (10) | The "Clean" node. Located on-premise. Protected by hardware firewall. Contains historical intelligence database. |

---

## 3. Threat Scenarios & Mitigations

### 🔴 Threat A: Attribution & Deanonymization
**Risk:** Threat actors identifying the researcher's physical location or identity.
* **Attack Vector:** Traffic correlation, IP leakage, browser fingerprinting.
* **Mitigation 1 (Tor Proxy):** All interactions with `.onion` sites are routed through a localized SOCKS5 Tor proxy container. The Python script has no direct route to the internet for these requests.
* **Mitigation 2 (VPS Layer):** The scraper runs on a cloud VPS, not a residential IP. Attribution stops at the cloud provider.
* **Mitigation 3 (OpSec):** No personal accounts are used. Telegram accounts are registered via anonymous numbers (+888) or burner SIMs.

### 🔴 Threat B: Lateral Movement (The "Backhaul" Attack)
**Risk:** A compromised Ghost VPS being used to attack the Home Lab.
* **Attack Vector:** An exploit in the scraper allows RCE (Remote Code Execution) on the VPS. The attacker tries to pivot to the database.
* **Mitigation (The Air Gap):** There is **zero** network connectivity between the Ghost VPS and the Analyst Node.
* **Mitigation (Data Diode):** The Ghost VPS only has credentials to **WRITE** to a specific S3 bucket. It cannot read or delete backups. The Analyst Node only **READS**.
* **Mitigation (Protocol Break):** The transfer mechanism is asynchronous (JSON files). Malicious network traffic cannot "tunnel" through a JSON file stored in S3.

### 🔴 Threat C: Infrastructure Tampering
**Risk:** An attacker gaining access to the VPS to alter code or steal API keys.
* **Attack Vector:** SSH Brute Force or Zero-day.
* **Mitigation (Hardening):** Root login disabled, SSH key-only auth, non-standard ports.
* **Mitigation (Active Defense):** `auditd` monitors the file integrity of `scraper.py` and `.env`. `Fail2Ban` actively bans scanning IPs.
* **Mitigation (Watchdog):** The system reports its own security logs to the dashboard. If the Ghost goes silent or reports a breach, it can be destroyed instantly via Terraform.

### 🔴 Threat D: Malicious Data Ingestion (Poisoning)
**Risk:** Threat actors injecting exploits (XSS, SQLi, Buffer Overflow) into scraped text to attack the dashboard.
* **Attack Vector:** A Telegram message containing a malicious payload designed to execute when viewed in Grafana.
* **Mitigation (Sanitization):** The Ingestor creates a "hygiene barrier."
    * All text is stripped of non-printable characters.
    * HTML entities are escaped.
    * Data types are strictly enforced (Float vs String) before database insertion.

---

## 4. Residual Risks
* **Zero-Day in Docker/Kernel:** A container escape on the VPS could compromise the host OS. Accepted risk (mitigated by ephemeral infrastructure).
* **Telegram Account Ban:** High scraping volume may lead to account termination. Mitigated by using diverse accounts and rate limiting (3600s cycle).

## 5. Security Posture Conclusion
The Volkov architecture assumes the collection node is a **liability**. By decoupling collection from analysis via an asynchronous S3 airlock, we achieve a high degree of resilience. A total compromise of the Ghost Node results in zero data loss and zero compromise of the core intelligence assets.
