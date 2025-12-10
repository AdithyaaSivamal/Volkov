# 📊 Grafana Dashboards

This directory contains the JSON definitions for the Volkov CTI visualization suite.

## Dashboard Files
* **`tactical_commander.json`**: The tactical view tracking real-time ransomware victims, attack vectors (Geomap), and crimeware market listings.
* **`strategic_watch.json`**: The strategic view focusing on Russian APTs (RSS), C2 infrastructure status, and internal security alerts.

## How to Import
1.  Log in to your Grafana instance (Default: `http://localhost:3000`).
2.  Navigate to **Dashboards** $\to$ **New** $\to$ **Import**.
3.  **Upload** a JSON file from this directory (or paste the file contents).
4.  When prompted for a **Data Source**, select your **InfluxDB** connection.
5.  Click **Import**.
