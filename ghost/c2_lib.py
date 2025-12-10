import requests
import json

# Source: ThreatFox (Abuse.ch) - Recent IOCs (JSON)
C2_FEED_URL = "https://threatfox.abuse.ch/export/json/recent/"

def fetch_c2_infrastructure():
    """
    Downloads active C2s from ThreatFox with Malware Attribution.
    Adapted for Dictionary-based JSON response format.
    """
    print(f"[*] C2 HUNTER: Fetching ThreatFox feed...")
    
    try:
        r = requests.get(C2_FEED_URL, timeout=30)
        if r.status_code == 200:
            data = r.json()
            
            c2_intel = []
            count = 0
            
            for ioc_id, entries in data.items():
                if not entries: continue
                
                item = entries[0]
                
                # EXTRACT FIELDS
                threat_type = item.get('threat_type')
                raw_ioc = item.get('ioc_value', '')
                malware = item.get('malware_printable', 'Unknown')
                
                # FILTER: We want C2s (botnet_cc) or Payload Delivery
                # You can be broader here if you want more dots on the map
                if threat_type in ['botnet_cc', 'payload_delivery']:
                    
                    if ':' in raw_ioc and not 'http' in raw_ioc:
                        value = raw_ioc.split(':')[0]
                    else:
                        value = raw_ioc
                    
                    c2_intel.append({
                        "type": "c2_node",
                        "value": value,
                        "malware": malware,
                        "role": threat_type 
                    })
                    count += 1

            print(f"[+] C2 HUNTER: Ingested {count} verified C2s.")
            
            if count == 0:
                return None

            return {
                "timestamp": None, 
                "source": "C2_INTEL_FEED",
                "message_id": "THREATFOX_UPDATE",
                "raw_text": f"**📡 C2 Update:** Imported {count} indicators from ThreatFox.",
                "analysis": {
                    "victims": [],
                    "gangs": ["Infrastructure"],
                    "iocs": c2_intel,
                    "translation_failures": [],
                    "leads": []
                }
            }
            
    except Exception as e:
        print(f"[-] C2 HUNTER FAILED: {e}")
        return None
