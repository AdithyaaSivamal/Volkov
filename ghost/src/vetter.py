import json
import os
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
# These are only needed if running manually (standalone mode)
API_ID = os.getenv('TG_API_ID')
API_HASH = os.getenv('TG_API_HASH')
PHONE = os.getenv('TG_PHONE')
SESSION_NAME = '/app/data/volkov_session' 

DISCOVERY_FILE = './volkov_discovery_log.json'
TARGETS_FILE = './verified_targets.json'

# SCORING MATRIX (The "Hunter" Logic)
KEYWORDS = {
    # English High Value
    "leak": 3, "database": 3, "access": 4, "shell": 4, "c2": 5, "root": 3,
    "selling": 2, "price": 2, "dm me": 1, "dump": 3, "breach": 3,
    
    # Russian High Value (Fenya)
    "пролив": 10,    # Traffic/Access
    "отработка": 10, # Post-exploitation
    "скуп": 5,       # Buying logs
    "дедик": 5,      # Dedicated server
    "брут": 4,       # Brute force
    "шелл": 5,       # Shell
    "лог": 3,        # Log
    "база": 3        # Database
}

# THRESHOLD: If score > 15, it's a valid target.
SCORE_THRESHOLD = 15

async def calculate_density(client, channel_username):
    """
    Scans the last 50 messages of a channel to see if it talks about crime.
    """
    print(f"[*] VETTING: Checking {channel_username}...")
    score = 0
    message_count = 0
    
    try:
        # Check if entity exists
        try:
            entity = await client.get_entity(channel_username)
        except ValueError:
            print(f"    > Invalid channel or private: {channel_username}")
            return 0, 0
        except Exception as e:
            print(f"    > Error accessing {channel_username}: {e}")
            return 0, 0
        
        # Grab last 50 text messages
        async for msg in client.iter_messages(entity, limit=50):
            if msg.text:
                text = msg.text.lower()
                message_count += 1
                
                # Check keywords
                for word, points in KEYWORDS.items():
                    if word in text:
                        score += points
        
        # Normalize score (Average points per message)
        if message_count > 0:
            final_score = score / (message_count / 10) 
        else:
            final_score = 0
            
        return final_score, message_count

    except Exception as e:
        print(f"[-] ERROR: Could not vet {channel_username}: {e}")
        return 0, 0

async def main(client):
    """
    Main Logic: Accepts an active TelegramClient object.
    """
    print("[*] Volkov Vetter initialized.")
    
    # 1. Load Leads
    if not os.path.exists(DISCOVERY_FILE):
        print("[-] No discovery log found.")
        return
        
    try:
        with open(DISCOVERY_FILE, 'r') as f:
            leads = json.load(f)
    except json.JSONDecodeError:
        print("[-] Discovery log is corrupted or empty.")
        return
    
    # 2. Load Existing Targets (to avoid re-vetting)
    verified = []
    if os.path.exists(TARGETS_FILE):
        try:
            with open(TARGETS_FILE, 'r') as f:
                verified = json.load(f)
        except:
            verified = []
            
    verified_names = [v['username'] for v in verified]

    # 3. The Vetting Loop
    for lead in leads:
        target = lead.get('username')
        
        # Skip if invalid or already verified
        if not target or target in verified_names:
            continue
            
        score, count = await calculate_density(client, target)
        
        print(f"    > Result: {target} | Score: {score:.2f} | Msgs: {count}")
        
        if score >= SCORE_THRESHOLD:
            print(f"[+] HIGH VALUE TARGET IDENTIFIED: {target}")
            new_entry = {
                "username": target,
                "score": score,
                "vetted_at": "timestamp_placeholder", 
                "type": "potential_criminal"
            }
            verified.append(new_entry)
            
            # Save immediately to disk
            with open(TARGETS_FILE, 'w') as f:
                json.dump(verified, f, indent=4)
        
        # Rate Limit Protection (Critical for Telegram)
        await asyncio.sleep(5) 

    print("[*] Vetting cycle complete.")

# --- STANDALONE EXECUTION BLOCK ---
if __name__ == "__main__":
    # This block ONLY runs if you type 'python vetter.py' manually.
    # It creates its own client connection for testing purposes.
    print("[*] Manual Override: Starting standalone vetting session...")
    
    manual_client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    async def manual_run():
        await manual_client.start(phone=PHONE)
        await main(manual_client)
    
    with manual_client:
        manual_client.loop.run_until_complete(manual_run())
