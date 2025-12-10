import os
import json
import re
import uuid
import time
import shutil
import asyncio
import boto3
import requests
from datetime import datetime
from telethon import TelegramClient
from bs4 import BeautifulSoup
from botocore.exceptions import NoCredentialsError
from dotenv import load_dotenv

import onion_lib 
import vetter
import rss_lib
import c2_lib

# --- CONFIGURATION ---
load_dotenv()
API_ID = os.getenv('TG_API_ID')
API_HASH = os.getenv('TG_API_HASH')
PHONE = os.getenv('TG_PHONE')
SESSION_NAME = '/app/data/volkov_session' 
S3_ENDPOINT = os.getenv('S3_ENDPOINT')
S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY')
S3_SECRET_KEY = os.getenv('S3_SECRET_KEY')
S3_BUCKET = os.getenv('S3_BUCKET')
AIRLOCK_FOLDER = './volkov_local_buffer/'
DISCOVERY_FILE = './volkov_discovery_log.json'
SCRAPE_INTERVAL = 3600
HEALTH_CHECK_INTERVAL = 300

# TARGET LIST
TARGETS = {
    # Aggregators
    'ransomwatcher': 'aggregator', 
    'venarix': 'aggregator',
    'vxundergroundofficial': 'aggregator',
    
    # Hacktivists
    'CyberArmyofRussia': 'hacktivist',
    'WeAreKillnet_Channel': 'hacktivist',
    'KillMarket_Official': 'market',

    # Discovery
    'telegram': 'snowball',
    
    # Tor
    'http://xb6q2aggycmlcrjtbjendcnnwpmmwbosqaugxsqb4nx6cmod3emy7sad.onion': 'onion_general',
}

# --- STRATEGIES ---

def parse_hacktivist(message):
    """
    Strategy: HACKTIVIST (Russian)
    Parses operational orders from CyberArmy and Killnet.
    """
    raw_text = message.text or ""
    intel = {"victims": [], "iocs": [], "gangs": [], "translation_failures": [], "leads": []}
    
    # 1. Check for Attack Triggers (Russian)
    triggers = ["новая цель", "атакуем", "сайт", "кладем", "цель", "ddos", "ддос"]
    if not any(t in raw_text.lower() for t in triggers):
        return {} # Not an attack order

    # 2. Extract IPs (Infrastructure Targeting)
    ips = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', raw_text)
    for ip in ips:
        intel["iocs"].append({"type": "ip", "value": ip, "role": "DDoS_Target"})
        intel["victims"].append(f"IP: {ip}")

    # 3. Extract Domains
    urls = re.findall(r'(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)', raw_text)
    for url in urls:
        # Filter noise
        if not any(x in url for x in ['t.me', 'telegra.ph', 'youtube', 'rutube']):
            intel["victims"].append(url)
            intel["iocs"].append({"type": "url", "value": url, "role": "DDoS_Target"})

    # 4. Attribution
    if "CyberArmy" in raw_text or "Киберармия" in raw_text:
        intel["gangs"].append("CyberArmyofRussia")
    elif "Killnet" in raw_text:
        intel["gangs"].append("Killnet")
    else:
        intel["gangs"].append("Russian_Hacktivist_General")

    return intel

def parse_aggregator(message):
    raw_text = message.text or ""
    if not re.search(r'(?:\*\*🎯 Victim:\*\*|Victim:|Target:|🚨 New cyber event|Threat group:)', raw_text, re.IGNORECASE):
        return {} 
    intel = {"victims": [], "iocs": [], "gangs": [], "translation_failures": []}
    victim_match = re.search(r'(?:\*\*🎯 Victim:\*\*|Victim:|Target:)\s*(.+)', raw_text, re.IGNORECASE)
    if victim_match: intel["victims"].append(victim_match.group(1).strip())
    gang_match = re.search(r'(?:\*\*⚠️ Gang Claimed:\*\*|Gang:|Threat group:|Actor:)\s*(.+)', raw_text, re.IGNORECASE)
    if gang_match:
        clean = re.sub(r'(?:Yes\s*\(|Claimed by\s*)(.+?)\)?$', r'\1', gang_match.group(1).strip(), flags=re.IGNORECASE)
        intel["gangs"].append(clean)
    if re.search(r'пролив', raw_text, re.IGNORECASE):
        intel["translation_failures"].append({"term": "пролив", "note": "Context Loss"})
    return intel

def parse_snowball(message):
    raw_text = message.text or ""
    intel = {"victims": [], "iocs": [], "gangs": [], "translation_failures": [], "leads": []}
    if message.fwd_from and message.fwd_from.from_id:
        try:
            lead = {"type": "forward_detection", "title": message.fwd_from.from_name, "detected_id": getattr(message.fwd_from.from_id, 'channel_id', 'unknown')}
            intel["leads"].append(lead)
        except: pass
    for m in re.findall(r'@([a-zA-Z0-9_]{5,})', raw_text):
        intel["leads"].append({"type": "mention", "username": m})
    return intel

def parse_market(message):
    """
    Strategy: MARKET
    Parses listings for data, access, and military docs.
    """
    raw_text = message.text or ""
    intel = {"victims": [], "iocs": [], "gangs": [], "translation_failures": [], "leads": []}

    # 1. Check for "Lot" indicator (Sales listing)
    if "Лот:" not in raw_text and "Lot:" not in raw_text:
        return {}

    # 2. Extract Product Description
    # Usually follows "Состав лота:" or "Description:"
    desc_match = re.search(r'(?:Состав лота|Описание лота|Description)[:\s*]+\**([^\n]+)', raw_text, re.IGNORECASE)
    
    if desc_match:
        product = desc_match.group(1).strip().replace('*', '') # Remove markdown stars
    else:
        # Fallback: If no label, take the first line (often the title)
        product = raw_text.split('\n')[0][:100]

    # 3. Categorize (Simple keyword matching)
    category = "General"
    if any(x in raw_text.lower() for x in ['leopard', 'bradley', 'документация', 'чертежи']):
        category = "Military_Intel"
    elif any(x in raw_text.lower() for x in ['access', 'доступ', 'rdp', 'vpn']):
        category = "Network_Access"

    # 4. Save as "Lead" for the dashboard
    intel["leads"].append({
        "type": "market_listing",
        "value": product[:100], # Truncate for display
        "category": category,
        "price": "Unknown" # Regex for price is hard, update later
    })

    intel["gangs"].append("KillNet_Market")
    return intel

def parse_onion_general(html_content, url):
    soup = BeautifulSoup(html_content, 'html.parser')
    intel = {"victims": [], "iocs": [], "gangs": [], "translation_failures": []}
    title = soup.title.string if soup.title else "Unknown Onion"
    headers = [h.get_text().strip() for h in soup.find_all(['h1', 'h2'])]
    if "DuckDuckGo" in title: intel["victims"].append("Tor Connectivity Test")
    return f"**🌐 TOR SOURCE:** {url}\n**Title:** {title}\n**Headlines:** {', '.join(headers[:5])}", intel

# --- NORMALIZERS ---
def normalize_telegram(message, strategy):
    if strategy == 'aggregator': analysis = parse_aggregator(message)
    elif strategy == 'snowball': analysis = parse_snowball(message)
    elif strategy == 'hacktivist': analysis = parse_hacktivist(message)
    elif strategy == 'market': analysis = parse_market(message)
    else: analysis = {}
    
    if not analysis: return None

    return {
        "timestamp": message.date.isoformat(),
        "source": getattr(message.chat, 'username', 'unknown'),
        "message_id": message.id,
        "raw_text": message.text,
        "analysis": analysis
    }

def normalize_onion(html, url, strategy):
    raw_text, analysis = parse_onion_general(html, url)
    return {"timestamp": datetime.utcnow().isoformat(), "source": "TOR_NETWORK", "message_id": hash(url), "raw_text": raw_text, "analysis": analysis}


# --- INFRA & MAIN ---
def fetch_ransomwatch_groups():
    url = "https://raw.githubusercontent.com/joshhighet/ransomwatch/main/groups.json"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200: return r.json()
    except: pass
    return []

def log_discovery(leads):
    if not leads: return
    if os.path.exists(DISCOVERY_FILE):
        try:
            with open(DISCOVERY_FILE, 'r') as f: database = json.load(f)
        except: database = []
    else: database = []
    updated = False
    for lead in leads:
        if not any(d.get('username') == lead.get('username') for d in database):
            lead['discovered_at'] = datetime.utcnow().isoformat()
            database.append(lead)
            updated = True
    if updated:
        with open(DISCOVERY_FILE, 'w') as f: json.dump(database, f, indent=4)

def push_to_airlock(filename):
    s3 = boto3.client('s3', endpoint_url=S3_ENDPOINT, aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_KEY)
    try:
        s3.upload_file(filename, S3_BUCKET, filename)
        os.remove(filename)
        return True
    except: return False

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

async def main():
    print(f"[*] Ghost Scraper initialized.")
    await client.start(phone=PHONE)

    # Set to 0 to force a full scrape immediately on startup
    last_scrape_time = 0

    while True:
        current_time = time.time()

        # ==============================================================================
        # PHASE 1: HIGH-FREQUENCY HEARTBEAT (Health & Status)
        # Runs every cycle (5 mins) to keep the "Uptime" panel green/red.
        # ==============================================================================
        print(f"\n[*] --- HEARTBEAT CYCLE: {datetime.utcnow().isoformat()} ---")

        # 1. Dynamic Target Acquisition (Refresh List)
        rw_groups = fetch_ransomwatch_groups()
        priority_gangs = ['lockbit3', '8base', 'qilin', 'play', 'bianlian', 'blackbasta', 'rhysida']

        for group in rw_groups:
            if group['name'] in priority_gangs:
                for location in group['locations']:
                    if location['available'] and location['slug'].endswith('.onion'):
                        onion_url = "http://" + location['slug'] if not location['slug'].startswith("http") else location['slug']
                        if onion_url not in TARGETS:
                            print(f"[+] DYNAMIC TARGET ADDED: {group['name']} -> {onion_url}")
                            TARGETS[onion_url] = 'onion_general'
                        break

        # 2. Infrastructure Health Check (Ping Targets)
        health_batch = []
        for target in TARGETS:
            status = "DOWN"
            error_msg = "None"

            # Tor Ping
            if target.startswith("http"):
                # We use scrape_onion as a ping. If it returns content, the site is UP.
                if onion_lib.scrape_onion(target):
                    status = "UP"
                else:
                    error_msg = "Unreachable / Timeout"

            # Telegram Ping
            else:
                try:
                    # get_entity is a cheap way to verify the channel exists/is accessible
                    await client.get_entity(target)
                    status = "UP"
                except Exception as e:
                    error_msg = str(e)

            # Create Health Metric
            health_batch.append({
                "timestamp": datetime.utcnow().isoformat(),
                "source": "HEALTH_CHECK",
                "message_id": 0,
                "raw_text": f"Status check for {target}",
                "analysis": {
                    "infrastructure_status": {
                        "target": target,
                        "status": status,
                        "error": error_msg
                    }
                }
            })

        # 3. Push Health Data Immediately
        if health_batch:
            filename = f"volkov_health_{datetime.now().strftime('%H%M%S')}_{str(uuid.uuid4())[:4]}.json"
            with open(filename, "w") as f:
                json.dump(health_batch, f)
            push_to_airlock(filename)
            print(f"[+] HEARTBEAT: Sent {len(health_batch)} status updates.")

        # ==============================================================================
        # PHASE 2: LOW-FREQUENCY INTELLIGENCE (Content Scrape)
        # Runs only if 1 hour has passed since last full scrape.
        # ==============================================================================
        if current_time - last_scrape_time >= SCRAPE_INTERVAL:
            print(f"\n[*] >>> STARTING FULL CONTENT SCRAPE <<<")
            all_intel = []

            # A. RSS Feeds (APT Desk)
            try:
                rss_data = rss_lib.fetch_apt_intel()
                if rss_data: all_intel.extend(rss_data)
            except Exception as e:
                print(f"[-] RSS Module Failed: {e}")

            # B. C2 Infrastructure (Infrastructure Desk)
            try:
                c2_report = c2_lib.fetch_c2_infrastructure()
                if c2_report:
                    c2_report['timestamp'] = datetime.utcnow().isoformat()
                    all_intel.append(c2_report)
            except Exception as e:
                print(f"[-] C2 Module Failed: {e}")

            # C. Target Content Scraping (Telegram/Tor)
            for target, strategy in TARGETS.items():
                if target.startswith("http"):
                    print(f"[*] SCRAPING CONTENT: {target}...")
                    html = onion_lib.scrape_onion(target)
                    if html:
                        packet = normalize_onion(html, target, strategy)
                        if packet: all_intel.append(packet)
                else:
                    print(f"[*] SCRAPING CONTENT: {target}...")
                    try:
                        entity = await client.get_entity(target)
                        messages = await client.get_messages(entity, limit=5)
                        for m in messages:
                            if m.text:
                                packet = normalize_telegram(m, strategy)
                                if packet:
                                    all_intel.append(packet)
                                    if 'leads' in packet['analysis']:
                                        log_discovery(packet['analysis']['leads'])
                    except Exception as e:
                        print(f"[-] TG Error {target}: {e}")

            # D. Export Intelligence
            if all_intel:
                random_id = str(uuid.uuid4())[:8]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"volkov_intel_{timestamp}_{random_id}.json"

                with open(filename, "w", encoding='utf-8') as f:
                    json.dump(all_intel, f, indent=4, ensure_ascii=False)

                push_to_airlock(filename)
            else:
                print("[-] No actionable intelligence gathered this cycle.")

            # E. Run Vetting Module
            print("[*] Running Hunter-Killer Vetting...")
            try:
                await vetter.main(client)
            except Exception as e:
                print(f"[-] Vetting Error: {e}")

            # Update Timer
            last_scrape_time = time.time()
            print("[*] Full Scrape Cycle Finished.")

        # ==============================================================================
        # PHASE 3: SLEEP
        # ==============================================================================
        print(f"[*] Sleeping {HEALTH_CHECK_INTERVAL}s until next Heartbeat...")
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)

with client:
    client.loop.run_until_complete(main())
