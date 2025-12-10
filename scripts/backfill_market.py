import json
import re
import uuid
import os
import boto3
from datetime import datetime

# --- CONFIGURATION ---
INPUT_FILE = "volkov_hacktivist_sample.json"  
S3_ENDPOINT = "S3_ENDPOINT"
S3_ACCESS_KEY = "S3_ACCESS_KEY"
S3_SECRET_KEY = "S3_SECRET_KEY"
S3_BUCKET_NAME = "S3_BUCKET_NAME"

# ROBUST CATEGORY LIST (English + Russian Fenya)
CATEGORIES = {
    "ACCESS": [
        "rdp", "vpn", "access", "shell", "ssh", "citrix", "cpanel", "root",
        "доступ", "дедик", "шелл", "админка", "впн" 
    ],
    "DATA": [
        "database", "leak", "dump", "fullz", "passport", "sql", "ssn",
        "база", "слив", "дамп", "строки", "пасс", "доки", "логи"
    ],
    "MALWARE": [
        "botnet", "stealer", "rat", "loader", "exploit", "builder", "apk",
        "стилер", "ботнет", "лоадер", "ратник", "вирус", "майнер"
    ],
    "HARDWARE": [
        "flipper", "hackrf", "wifi", "jammer", "device", "skimmer",
        "флиппер", "глушилка", "скиммер", "оборудование"
    ],
    "SERVICES": [
        "ddos", "hosting", "bulletproof", "cashout", "design", "qr",
        "ддос", "хостинг", "абузоустойчивый", "обнал", "залив", "пробив"
    ],
    "MILITARY": [
        "leopard", "bradley", "abrams", "marder", "f-16", "su-", "mig-",
        "документация", "чертежи", "blueprints", "secret", "секретно"
    ]
}

def classify_listing(text):
    text = text.lower()
    found = []
    for cat, keywords in CATEGORIES.items():
        if any(k in text for k in keywords):
            found.append(cat)
    return ", ".join(found) if found else "General"


def parse_market_message(text, channel_name):
    # 1. Filter
    is_sale = any(x in text.lower() for x in ['lot:', 'лот:', 'price:', 'цена:', 'selling', 'продам'])
    if not is_sale: return None
    
    # 2. Extract Product Name
    # Looks for "Состав лота" or "Description" followed by text
    desc_match = re.search(r'(?:Состав лота|Описание лота|Description)[:\s*]+\**([^\n]+)', text, re.IGNORECASE)
    
    if desc_match:
        product = desc_match.group(1).strip().replace('*', '')
    else:
        # Fallback: just take the first line if it's a short post
        product = text.split('\n')[0][:100]

    # 3. Classify
    category = classify_listing(text)

    return {
        "victims": [],
        "gangs": [channel_name],
        "leads": [{
            "type": "market_listing",
            "value": product,
            "category": category,
            "price": "Unknown" 
        }]
    }

def main():
    print(f"[*] Reading dump: {INPUT_FILE}...")
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        print("[-] File not found. Did you rename your dump file?")
        return

    processed_batch = []
    
    for channel_name, messages in raw_data.items():
        print(f"[*] Processing {channel_name}...")
        for msg in messages:
            text = msg.get('text', '')
            if not text: continue
            
            analysis = parse_market_message(text, channel_name)
            
            if analysis:
                packet = {
                    "timestamp": msg['date'],
                    "source": channel_name,
                    "message_id": msg['id'],
                    "raw_text": text,
                    "analysis": analysis
                }
                processed_batch.append(packet)

    print(f"[+] Extracted {len(processed_batch)} market listings.")
    
    if processed_batch:
        # Save & Push
        filename = f"volkov_market_backfill_{str(uuid.uuid4())[:8]}.json"
        with open(filename, 'w') as f:
            json.dump(processed_batch, f, indent=4, ensure_ascii=False)
        
        print(f"[*] Pushing to S3 Dead Drop...")
        s3 = boto3.client('s3', endpoint_url=S3_ENDPOINT,
                          aws_access_key_id=S3_ACCESS_KEY,
                          aws_secret_access_key=S3_SECRET_KEY)
        s3.upload_file(filename, S3_BUCKET_NAME, filename)
        print("[+] UPLOAD SUCCESS. Ingestor will process shortly.")
        os.remove(filename)

if __name__ == "__main__":
    main()
