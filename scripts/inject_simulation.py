import json
import uuid
import os
import shutil
import boto3
from datetime import datetime

# --- CONFIGURATION ---
S3_ENDPOINT = "S3_ENDPOINT"
S3_ACCESS_KEY = "S3_ACCESS_KEY" 
S3_SECRET_KEY = "S3_SECRET_KEY"
S3_BUCKET_NAME = "S3_BUCKET_NAME"

now_iso = datetime.utcnow().isoformat()

fake_data = [
    # TEST CASE 1: Corporate HQ Lookup
    # The system should display "Ferrari" but map it to Maranello, Italy
    {
        "timestamp": now_iso,
        "source": "SIMULATION_CORP",
        "message_id": 11001,
        "raw_text": "**🎯 Victim:** Ferrari **⚠️ Gang Claimed:** LockBit3",
        "analysis": {
            "victims": ["Ferrari"],
            "gangs": ["LockBit3"],
            "iocs": [], "translation_failures": [], "leads": []
        }
    },
    # TEST CASE 2: Tech Giant
    # The system should display "Nintendo" but map it to Kyoto, Japan
    {
        "timestamp": now_iso,
        "source": "SIMULATION_CORP",
        "message_id": 11002,
        "raw_text": "**🎯 Victim:** Nintendo **⚠️ Gang Claimed:** Qilin",
        "analysis": {
            "victims": ["Nintendo"],
            "gangs": ["Qilin"],
            "iocs": [], "translation_failures": [], "leads": []
        }
    },
    # TEST CASE 3: Airline
    # The system should display "Emirates" but map it to Dubai, UAE
    {
        "timestamp": now_iso,
        "source": "SIMULATION_CORP",
        "message_id": 11003,
        "raw_text": "**🎯 Victim:** Emirates Airlines **⚠️ Gang Claimed:** 8Base",
        "analysis": {
            "victims": ["Emirates Airlines"],
            "gangs": ["8Base"],
            "iocs": [], "translation_failures": [], "leads": []
        }
    }
]

def push_to_cloud(filename):
    print(f"[*] CONNECTING: Filebase S3 ({S3_BUCKET_NAME})...")
    s3 = boto3.client('s3', endpoint_url=S3_ENDPOINT,
                      aws_access_key_id=S3_ACCESS_KEY,
                      aws_secret_access_key=S3_SECRET_KEY)
    try:
        s3.upload_file(filename, S3_BUCKET_NAME, filename)
        print(f"[+] SUCCESS: Data is in the Dead Drop.")
        os.remove(filename)
    except Exception as e:
        print(f"[-] UPLOAD FAILED: {e}")

if __name__ == "__main__":
    filename = f"volkov_simulation_CORP_{str(uuid.uuid4())[:8]}.json"
    with open(filename, 'w') as f:
        json.dump(fake_data, f, indent=4)
    
    print(f"[+] Generated Corporate Test: {filename}")
    push_to_cloud(filename)
