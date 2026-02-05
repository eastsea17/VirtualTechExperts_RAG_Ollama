import requests
import yaml
import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class USPTOClient:
    """
    Client for fetching US Patents using PatentsView API v1.
    API Key managed via .env file.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        uspto_cfg = self.config['data_acquisition'].get('uspto', {})
        self.base_url = uspto_cfg.get('base_url', "https://search.patentsview.org/api/v1/patent")
        self.contact_email = uspto_cfg.get('contact_email', "research-agent@example.com")
        self.limit = uspto_cfg.get('fetch_limit', 25)
        
        # Load Key from Environment
        self.api_key = os.getenv("USPTO_API_KEY")

    def fetch_patents(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Fetches patents using the POST method with JSON query.
        """
        if not keywords:
            return []
            
        print(f"[USPTOClient] Fetching patents for: {keywords[:2]}...")
        
        # Check if key is available
        if not self.api_key or "YOUR_USPTO_KEY" in self.api_key:
            print("[USPTOClient] Warning: No valid USPTO_API_KEY found in .env.")
            print("   > Please add your key to the .env file.")
            print("   > Get key: https://patentsview.org/apis/key")
            return []

        query_text = keywords[0].replace('"', '')
        
        query = {
            "q": {
                "_or": [
                    {"_text_phrase": {"patent_title": query_text}},
                    {"_text_phrase": {"patent_abstract": query_text}}
                ]
            },
            "f": ["patent_number", "patent_title", "patent_abstract", "patent_date"],
            "o": {"per_page": self.limit}
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key,
            "User-Agent": self.contact_email
        }
        
        try:
            response = requests.post(self.base_url, json=query, headers=headers, timeout=30)
            
            if response.status_code == 403:
                print(f"[USPTOClient] Auth Error (403): Invalid API Key.")
                return []
            if response.status_code == 400:
                 print(f"[USPTOClient] Bad Request (400): Check query format.")
                 return []
                 
            response.raise_for_status()
            
            data = response.json()
            patents_data = data.get("patents", [])
            
            results = []
            for p in patents_data:
                results.append({
                    "id": p.get("patent_number"),
                    "title": p.get("patent_title"),
                    "abstract": p.get("patent_abstract"),
                    "publication_year": p.get("patent_date", "")[:4],
                    "source": "USPTO"
                })
                
            print(f"[USPTOClient] Found {len(results)} patents.")
            return results
            
        except Exception as e:
            print(f"[USPTOClient] Connection Error: {e}")
            return []

if __name__ == "__main__":
    client = USPTOClient()
    pass
