import requests
import yaml
import os
import base64
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class EPOClient:
    """
    Client for fetching Patents from European Patent Office (OPS).
    Keys managed via .env.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        self.consumer_key = os.getenv("EPO_CONSUMER_KEY")
        self.consumer_secret = os.getenv("EPO_CONSUMER_SECRET")
        
        epo_cfg = self.config['data_acquisition'].get('epo', {})
        self.auth_url = epo_cfg.get('auth_url', "https://ops.epo.org/3.2/auth/accesstoken")
        self.service_url = epo_cfg.get('service_url', "https://ops.epo.org/3.2/rest-services")
        self.limit = epo_cfg.get('fetch_limit', 20)
        self.access_token = None

    def _get_access_token(self):
        if not self.consumer_key or not self.consumer_secret or "YOUR_EPO_KEY" in self.consumer_key:
            print("[EPOClient] No valid EPO Keys found in .env. Skipping EPO fetch.")
            return None
            
        credentials = f"{self.consumer_key}:{self.consumer_secret}"
        encoded_creds = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_creds}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        try:
            response = requests.post(self.auth_url, data={"grant_type": "client_credentials"}, headers=headers, timeout=10)
            response.raise_for_status()
            self.access_token = response.json()['access_token']
            return self.access_token
        except Exception as e:
            print(f"[EPOClient] Auth Error: {e}")
            return None

    def fetch_patents(self, keyword: str) -> List[Dict[str, Any]]:
        if not self._get_access_token():
            return []
            
        print(f"[EPOClient] Fetching patents for: {keyword}...")
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }
        
        # Simple CQL search for title
        cql_query = f'ti="{keyword}"'
        search_url = f"{self.service_url}/published-data/search?q={cql_query}"
        
        try:
            response = requests.get(search_url, headers=headers, timeout=30)
            if response.status_code == 404:
                print(f"[EPOClient] No results found.")
                return []
            response.raise_for_status()
            
            data = response.json()
            # Parsing logic would depend on specific EPO JSON structure
            # Simplified for brevity/placeholder as EPO JSON is complex
            
            # TODO: Implement full parsing if actual EPO data is needed
            # For now, just logging success
            print(f"[EPOClient] Connection successful. (Parsing logic to be refined)")
            return [] 
            
        except Exception as e:
            print(f"[EPOClient] Fetch Error: {e}")
            return []

if __name__ == "__main__":
    client = EPOClient()
