import os
import json
import time
import shutil
import boto3
from botocore.exceptions import NoCredentialsError
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import volkov_enrich 

# --- 1. CONFIGURATION ---

# InfluxDB
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "my-super-secret-auth-token"
ORG = "volkov_intel"
BUCKET = "ransomware_tracker"

# S3 / Filebase Config
S3_ENDPOINT = "https://s3.filebase.com"
S3_ACCESS_KEY = "D0438D62CFEA165D535E"
S3_SECRET_KEY = "4R95FQzhGyewZoHtpP4PqZ0feB6JPl9dSv3yqNnI"
S3_BUCKET_NAME = "volkov-dead-drop-01"

# Local Paths
DOWNLOAD_DIR = "/mnt/volkov_nas/incoming/"
ARCHIVE_DIR = "/mnt/volkov_nas/archive/"

# Attacker Geo-Base (debugging)
ATTACKER_HOME_BASES = {
    "lockbit3": {"lat": 55.7558, "lon": 37.6173},
    "qilin": {"lat": 59.9343, "lon": 30.3351},
    "8base": {"lat": 13.7563, "lon": 100.5018},
    "play": {"lat": -23.5505, "lon": -46.6333},
    "unknown": {"lat": 0.0, "lon": 0.0}
}

# --- 2. SETUP ---
if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)
if not os.path.exists(ARCHIVE_DIR): os.makedirs(ARCHIVE_DIR)

db_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=ORG)
write_api = db_client.write_api(write_options=SYNCHRONOUS)

s3 = boto3.client('s3', endpoint_url=S3_ENDPOINT, aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_KEY)

# --- 3. S3 FUNCTIONS ---
def download_from_s3():
    try:
        response = s3.list_objects_v2(Bucket=S3_BUCKET_NAME)
        if 'Contents' not in response: return []
        downloaded = []
        for item in response['Contents']:
            filename = item['Key']
            local_path = os.path.join(DOWNLOAD_DIR, filename)
            print(f"[*] S3: Downloading {filename}...")
            s3.download_file(S3_BUCKET_NAME, filename, local_path)
            downloaded.append(filename)
        return downloaded
    except Exception as e:
        print(f"[-] S3 Polling Error: {e}")
        return []

def delete_from_s3(filename):
    try: s3.delete_object(Bucket=S3_BUCKET_NAME, Key=filename)
    except: pass

# --- 4. PROCESSING LOGIC ---
def process_file(filepath):
    print(f"[*] Processing {filepath}...")
    try:
        with open(filepath, 'r') as f: data = json.load(f)
    except Exception as e:
        print(f"[-] Read Error: {e}")
        return False

    points = []
    
    for entry in data:
        timestamp = entry['timestamp']
        source = entry.get('source', 'unknown')
        analysis = entry.get('analysis', {})
        
        # [GLOBAL VAR] Extract Gang Name safely for use in all branches
        gang_name = "Unknown"
        if analysis.get('gangs'):
            gang_name = analysis['gangs'][0]

        # --- BRANCH 1: STRATEGIC INTEL (RSS) ---
        if source.startswith("RSS_"):
            p = Point("attack_intel") \
                .tag("source_channel", source) \
                .tag("gang", gang_name) \
                .field("raw_text", entry.get("raw_text", "")) \
                .field("url", entry.get("message_id", "")) \
                .field("victim_count", 0) \
                .time(timestamp)
            points.append(p)
            continue 

        # --- BRANCH 2: C2 INFRASTRUCTURE ---
        if source == "C2_INTEL_FEED":
            for ioc in analysis.get('iocs', []):
                ip_addr = ioc.get('value', 'unknown')
                
                # Context initialization to prevent UnboundLocalError
                ctx = {"asn": "Unknown", "org": "Unknown", "country": "XX"}
                if ioc.get('type') == 'ip' or 'type' not in ioc:
                    ctx = volkov_enrich.get_ip_context(ip_addr)
                
                p_c2 = Point("infrastructure_c2") \
                    .tag("ip", ip_addr) \
                    .tag("malware", ioc.get('malware', 'Unknown_C2')) \
                    .tag("geo_country", ctx['country']) \
                    .tag("asn", str(ctx['asn'])) \
                    .tag("hosting_provider", ctx['org']) \
                    .field("count", 1) \
                    .time(timestamp)
                points.append(p_c2)
            continue 

        # --- BRANCH 3: TACTICAL INTEL (Telegram/Tor) ---
        if analysis.get('victims') or analysis.get('iocs') or analysis.get('translation_failures'):
            has_translation_fail = len(analysis.get('translation_failures', [])) > 0
            
            # IP Enrichment
            asn_tag, org_tag, country_tag = "None", "None", "None"
            if analysis.get('iocs'):
                for ioc in analysis['iocs']:
                    if ioc['type'] == 'ip':
                        ctx = volkov_enrich.get_ip_context(ioc['value'])
                        asn_tag, org_tag, country_tag = ctx['asn'], ctx['org'], ctx['country']
                        break 

            # Sector & Map Enrichment
            victim_list = analysis.get('victims', [])
            first_victim = victim_list[0] if victim_list else "Unknown"
            
            # Garbage Filter
            if len(first_victim) < 3 or first_victim.startswith("&") or "DuckDuckGo" in first_victim:
                first_victim = "Unknown"
                sector_tag = "Other"
                type_tag = "Unknown"
                victim_loc = {"found": False, "lat": 0.0, "lon": 0.0}
            else:
                sector_tag = volkov_enrich.classify_victim(first_victim)
                type_tag = volkov_enrich.classify_org_type(first_victim, sector_tag)
                victim_loc = volkov_enrich.get_victim_location(first_victim)

            attacker_loc = ATTACKER_HOME_BASES.get(gang_name.lower(), ATTACKER_HOME_BASES["unknown"])

            p = Point("attack_intel") \
                .tag("source_channel", source) \
                .tag("gang", gang_name) \
                .tag("language_barrier", str(has_translation_fail)) \
                .tag("hosting_provider", org_tag) \
                .tag("geo_country", country_tag) \
                .tag("asn", str(asn_tag)) \
                .tag("victim_sector", sector_tag) \
                .tag("org_type", type_tag) \
                .field("raw_text", entry.get("raw_text", "")) \
                .field("victim_count", len(victim_list)) \
                .time(timestamp)
            
            if victim_list: p.field("victims", ", ".join(victim_list))
            if victim_loc['found']:
                p.field("src_lat", float(attacker_loc['lat']))
                p.field("src_lon", float(attacker_loc['lon']))
                p.field("dst_lat", float(victim_loc['lat']))
                p.field("dst_lon", float(victim_loc['lon']))

            points.append(p)

        # --- BRANCH 4: DISCOVERY & MARKET LEADS ---
        for lead in analysis.get('leads', []):
            lead_type = lead.get("type", "unknown")
            
            # SUB-BRANCH: Crimeware Market Listings
            if lead_type == "market_listing":
                p = Point("crimeware_market") \
                    .tag("category", lead.get("category", "General")) \
                    .tag("seller", gang_name) \
                    .field("listing", lead.get("value", "Unknown Product")) \
                    .time(timestamp)
                points.append(p)
            
            # SUB-BRANCH: Standard Leads
            else:
                target_name = lead.get("username") or lead.get("title") or lead.get("value") or "unknown"
                p = Point("target_discovery") \
                    .tag("discovery_source", source) \
                    .tag("lead_type", lead_type) \
                    .field("discovered_target", target_name) \
                    .time(timestamp)
                points.append(p)

        # --- BRANCH 5: HEALTH ---
        infra = analysis.get('infrastructure_status')
        if infra:
            status_int = 1 if infra['status'] == 'UP' else 0
            p = Point("infrastructure_health") \
                .tag("target_url", infra['target']) \
                .tag("status_text", infra['status']) \
                .field("status_code", status_int) \
                .field("error_msg", infra['error']) \
                .time(timestamp)
            points.append(p)

        # --- BRANCH 6: INTERNAL SECURITY ---
        sec_event = analysis.get('security_event')
        if sec_event:
            p = Point("host_security") \
                .tag("event_type", sec_event['type']) \
                .tag("severity", "HIGH") \
                .field("message", sec_event['message']) \
                .field("source_ip", sec_event.get('ip', 'N/A')) \
                .time(timestamp)
            points.append(p)
            continue

    if points:
        try:
            write_api.write(bucket=BUCKET, org=ORG, record=points)
            print(f"[+] Ingested {len(points)} metrics.")
            return True
        except Exception as e:
            print(f"[-] DB Write Failed: {e}")
            return False
            
    print("[*] File processed (Noise Filter active).")
    return True

# --- 5. MAIN LOOP ---
def main():
    print("[*] Volkov Ingestor Active. Polling S3 & Local Drop...")
    while True:
        s3_files = download_from_s3()
        try:
            local_files = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith('.json')]
        except: local_files = []
        
        all_files = list(set(s3_files + local_files))

        if not all_files:
            time.sleep(10)
            continue
            
        for filename in all_files:
            if filename.startswith("._"): continue
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            try:
                if os.path.getsize(filepath) == 0: continue
            except: continue

            if process_file(filepath):
                try:
                    shutil.move(filepath, os.path.join(ARCHIVE_DIR, filename))
                    delete_from_s3(filename)
                except: pass
        time.sleep(10)

if __name__ == "__main__":
    main()
