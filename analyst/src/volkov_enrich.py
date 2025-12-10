import time
import requests
import html
import urllib.parse
from geopy.geocoders import Nominatim
from ipwhois import IPWhois
from ipwhois.exceptions import IPDefinedError, ASNRegistryError

# 1. GEOINT ENGINE (Nominatim)
# User-agent is required by OSM policy to prevent blocking
geolocator = Nominatim(user_agent="volkov_project_cti_v1")
GEO_CACHE = {}

def clean_victim_name(name):
    """
    Sanitizes victim names to improve lookup success.
    Decodes HTML entities (&amp;) and URL encoding (%20).
    """
    if not name: return ""
    clean = urllib.parse.unquote(name)
    clean = html.unescape(clean)
    return clean.strip()

def get_wikidata_location(company_name):
    """
    Queries Wikidata to find the Headquarters location of a company.
    """
    print(f"[*] WIKIDATA: Searching for '{company_name}'...")
    url = "https://www.wikidata.org/w/api.php"
    
    # WIKIMEDIA POLICY REQUIRES A CUSTOM USER-AGENT
    headers = {
        'User-Agent': 'VolkovBot/1.0 (volkov_project_research; contact@example.com)'
    }
    
    time.sleep(1.0) 
    try:
        # 1. Search for the entity (Company)
        params = {
            "action": "wbsearchentities",
            "language": "en",
            "format": "json",
            "search": company_name
        }
        r = requests.get(url, params=params, headers=headers, timeout=5)
        
        # DEBUG: Check if we got blocked
        if r.status_code != 200:
            print(f"[-] WIKIDATA HTTP ERROR: {r.status_code}")
            return None
        try:
            data = r.json()
        except ValueError:
            # This handles the "Expecting value" error
            print(f"[-] WIKIDATA DECODE ERROR. Raw response: {r.text[:100]}...")
            return None
        
        if not data.get('search'):
            return None
            
        # Get the first result's ID (e.g., Q8093 for Nintendo)
        entity_id = data['search'][0]['id']
        
        # 2. Get the Headquarters Property (P159)
        params = {
            "action": "wbgetclaims",
            "entity": entity_id,
            "property": "P159", # Headquarters location
            "format": "json"
        }
        r = requests.get(url, params=params, headers=headers, timeout=5)
        claims = r.json().get('claims', {})
        
        if 'P159' in claims:
            hq_id = claims['P159'][0]['mainsnak']['datavalue']['value']['id']
            
            # 3. Resolve HQ City ID to Coordinates (P625)
            params = {
                "action": "wbgetentities",
                "ids": hq_id,
                "props": "claims|labels",
                "format": "json"
            }
            r = requests.get(url, params=params, headers=headers, timeout=5)
            entity_data = r.json()['entities'][hq_id]
            
            # Get Name (e.g., "Kyoto")
            city_name = entity_data['labels']['en']['value']
            
            # Get Coordinates (P625)
            if 'P625' in entity_data['claims']:
                coords = entity_data['claims']['P625'][0]['mainsnak']['datavalue']['value']
                return {
                    "lat": coords['latitude'], 
                    "lon": coords['longitude'], 
                    "country": city_name, 
                    "found": True
                }
                
    except Exception as e:
        print(f"[-] WIKIDATA EXCEPTION: {e}")
        
    return None

def get_victim_location(victim_name):
    clean_name = clean_victim_name(victim_name)
    
    # Check Cache
    if clean_name in GEO_CACHE: return GEO_CACHE[clean_name]

    # Strategy A: Nominatim (Good for "Paris, France")
    try:
        location = geolocator.geocode(clean_name, timeout=3)
        if location:
            data = {
                "lat": location.latitude,
                "lon": location.longitude,
                "country": location.address.split(",")[-1].strip(),
                "found": True
            }
            GEO_CACHE[clean_name] = data
            print(f"[+] NOMINATIM: Found {clean_name}")
            return data
    except: pass

    # Strategy B: Wikidata 
    wiki_data = get_wikidata_location(clean_name)
    if wiki_data:
        GEO_CACHE[clean_name] = wiki_data
        print(f"[+] WIKIDATA: Found {clean_name} -> {wiki_data['country']}")
        return wiki_data

    # Failed
    return {"lat": 0.0, "lon": 0.0, "country": "Unknown", "found": False}

# 2. NETWORK INTEL ENGINE (IPWhois)
IP_CACHE = {}

def get_ip_context(ip_addr):
    if ip_addr in IP_CACHE: return IP_CACHE[ip_addr]
    if ip_addr.startswith(("192.168.", "10.", "127.")):
        return {"asn": "Internal", "org": "Private Network", "country": "XX"}

    try:
        obj = IPWhois(ip_addr)
        results = obj.lookup_rdap(depth=1)
        context = {
            "asn": results.get('asn', 'Unknown'),
            "org": results.get('network', {}).get('name', 'Unknown')[:50],
            "country": results.get('asn_country_code', 'XX')
        }
        IP_CACHE[ip_addr] = context
        print(f"[+] IP ENRICHED: {ip_addr} -> {context['org']}")
        return context
    except Exception:
        return {"asn": "Lookup_Failed", "org": "Unknown", "country": "XX"}

# 3. SECTOR CLASSIFICATION (hardcoded for now, work in progress)
def classify_victim(victim_name):
    name = victim_name.lower()
    if any(x in name for x in ['bank', 'finance', 'capital']): return "Finance"
    if any(x in name for x in ['hospital', 'health', 'medical']): return "Healthcare"
    if any(x in name for x in ['gov', 'city', 'state', 'ministry']): return "Government"
    if any(x in name for x in ['school', 'university', 'college']): return "Education"
    if any(x in name for x in ['tech', 'data', 'cyber']): return "Technology"
    return "Other"

def classify_org_type(victim_name, sector):
    if sector in ["Government", "Education"]: return "Public Sector"
    return "Private Sector"
