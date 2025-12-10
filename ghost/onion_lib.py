import requests
import time

# The Docker service name 'tor_proxy' resolves to the container IP
TOR_PROXY = "socks5h://tor_proxy:9050"

def scrape_onion(url):
    """
    Scrapes a .onion site via the Tor Sidecar.
    """
    print(f"[*] TOR: Connecting to {url}...")
    
    session = requests.Session()
    session.proxies = {
        'http': TOR_PROXY,
        'https': TOR_PROXY
    }
    
    # Tor requires headers to look like a normal browser (Anti-Fingerprinting)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0'
    }

    try:
        # Long timeout because Tor is slow
        r = session.get(url, headers=headers, timeout=45)
        
        if r.status_code == 200:
            print(f"[+] TOR SUCCESS: Retrieved {len(r.text)} bytes.")
            return r.text
        else:
            print(f"[-] TOR ERROR: Status {r.status_code}")
            return None
            
    except Exception as e:
        print(f"[-] TOR FAILURE: {e}")
        return None
