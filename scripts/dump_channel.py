import os
import json
import asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()

# Use your local credentials
API_ID = os.getenv('TG_API_ID')
API_HASH = os.getenv('TG_API_HASH')
PHONE = os.getenv('TG_PHONE')
SESSION_NAME = 'volkov_local_session' 

# the hacktivist target telegram channels, find and add
TARGETS = [
#    'WeAreKillnet_Channel', 
#    'CyberArmyofRussia'
#    'KillMarket_Official'
]

# JSON Encoder for DateTimes
class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

async def main():
    print("[*] Initializing Deep Dive Dumper...")
    
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        await client.start(phone=PHONE)
        
        full_dump = {}

        for username in TARGETS:
            print(f"\n[*] Scanning: {username}")
            try:
                # 1. Resolve Entity
                entity = await client.get_entity(username)
                
                # 2. Scrape History (Last 100)
                history = []
                count = 0
                
                async for message in client.iter_messages(entity, limit=100):
                    count += 1
                    
                    # --- EXTRACTION LOGIC ---
                    
                    # A. Extract Hyperlinks (The "Hidden" Links)
                    extracted_links = []
                    if message.entities:
                        for ent in message.entities:
                            # Text Link: [Click Here](https://telegra.ph/...)
                            if isinstance(ent, MessageEntityTextUrl):
                                extracted_links.append(ent.url)
                            # Raw Link: https://telegra.ph/...
                            elif isinstance(ent, MessageEntityUrl):
                                # Extract the substring from the raw text
                                offset = ent.offset
                                length = ent.length
                                url = message.text[offset : offset + length]
                                extracted_links.append(url)

                    # B. Check Forward Info
                    fwd_info = None
                    if message.fwd_from:
                        fwd_info = {
                            "from_name": message.fwd_from.from_name,
                            "channel_id": getattr(message.fwd_from.from_id, 'channel_id', None) if message.fwd_from.from_id else None,
                            "date": message.fwd_from.date
                        }

                    # C. Build Packet
                    msg_data = {
                        "id": message.id,
                        "date": message.date,
                        "text": message.text,
                        "views": message.views,
                        "forwards": message.forwards,
                        "extracted_links": extracted_links, # <--- CRITICAL FOR TELEGRAPH
                        "forward_origin": fwd_info
                    }
                    history.append(msg_data)
                    print(f"    > Processed message {message.id} ({len(extracted_links)} links found)")

                full_dump[username] = history
                print(f"[+] Successfully dumped {count} messages from {username}")

            except Exception as e:
                print(f"[-] FAILED to scrape {username}: {e}")

        # 3. Save to Disk
        filename = f"volkov_hacktivist_sample_{datetime.now().strftime('%Y%m%d')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(full_dump, f, cls=DateTimeEncoder, indent=4, ensure_ascii=False)
            
        print(f"\n[+] MISSION COMPLETE. Data saved to: {filename}")
        print(f"    - Upload this file to the chat for analysis.")

if __name__ == '__main__':
    asyncio.run(main())
