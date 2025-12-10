import feedparser
import time
import re
from datetime import datetime
from time import mktime

# Trusted CTI Sources
RSS_SOURCES = {
    "CISA": "https://www.cisa.gov/cyber-threats-and-advisories/nation-state-cyber-actors/russia/publications/feed",
    "Mandiant": "https://www.mandiant.com/resources/blog/rss.xml",
    "Google_Threat": "https://cloud.google.com/blog/topics/threat-intelligence/rss/",
    "Microsoft": "https://www.microsoft.com/en-us/security/blog/feed/",
    "TheHackerNews": "https://thehackernews.com/feeds/posts/default",
    "KrebsOnSecurity": "https://krebsonsecurity.com/feed/"
}

# The Target List (Russian APTs)
RUSSIAN_KEYWORDS = [
    "apt28", "fancy bear", "forest blizzard", "sandworm", "voodoo bear",
    "apt29", "cozy bear", "midnight blizzard", "nobelium", "the dukes",
    "turla", "venomous bear", "krypton", "snake", "uroburos",
    "gamaredon", "primitive bear", "actinium",
    "russia", "russian", "fsb", "gru", "svr", "ukraine"
]

def fetch_apt_intel():
    print("[*] RSS: Scanning for Russian APT activity...")
    intel_batch = []
    
    for source, url in RSS_SOURCES.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                title = entry.title.lower()
                summary = getattr(entry, 'summary', '').lower()
                content = title + " " + summary
                
                # Check for Russian Actors
                matched_actors = [k for k in RUSSIAN_KEYWORDS if k in content]
                
                if matched_actors:
                    # Clean up actor list
                    specific_actors = [m for m in matched_actors if m not in ['russia', 'russian']]
                    final_actors = specific_actors if specific_actors else matched_actors
                    
                    # [FIX] Use Article Date for Deduplication
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        # Convert struct_time to ISO format
                        pub_time = datetime.fromtimestamp(mktime(entry.published_parsed)).isoformat()
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        pub_time = datetime.fromtimestamp(mktime(entry.updated_parsed)).isoformat()
                    else:
                        # Fallback only if no date exists
                        pub_time = datetime.utcnow().isoformat()

                    intel_batch.append({
                        "timestamp": pub_time, 
                        "source": f"RSS_{source}",
                        "message_id": entry.link,
                        "raw_text": f"**📰 {entry.title}**\n\n{getattr(entry, 'summary', 'No summary')[:300]}...\n\n🔗 [Read Report]({entry.link})",
                        "analysis": {
                            "victims": [],
                            "gangs": [tag.upper() for tag in final_actors],
                            "iocs": [],
                            "translation_failures": [],
                            "leads": []
                        }
                    })
                    print(f"[+] RSS MATCH: Found {final_actors} in {source}")
        except Exception as e:
            print(f"[-] RSS Error ({source}): {e}")
            
    return intel_batch
