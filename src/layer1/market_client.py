import os
import requests
import yaml
from typing import List, Dict, Any
from dotenv import load_dotenv

s = load_dotenv()

class MarketClient:
    """
    Client for fetching market news and insights from Tavily API.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        self.api_key = os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            print("[MarketClient] Warning: TAVILY_API_KEY not found in environment variables.")
        
        self.base_url = "https://api.tavily.com/search"
        self.fetch_limit = self.config.get('data_acquisition', {}).get('tavily', {}).get('fetch_limit', 5)
        
    def fetch_market_news(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetches market news and insights for the given query.
        """
        if not self.api_key:
            return []
            
        print(f"[MarketClient] Fetching market news for: '{query}'...")
        
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced", # Use advanced for better market insights
            "max_results": self.fetch_limit,
            "include_domains": [],
            "exclude_domains": [],
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False
        }
        
        try:
            response = requests.post(self.base_url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            
            news_items = []
            for result in results:
                news_items.append({
                    "title": result.get("title"),
                    "url": result.get("url"),
                    "abstract": result.get("content"), # Mapping content to abstract for compatibility
                    "content": result.get("content"),
                    "publication_year": "2024", # Tavily results are usually recent; default to recent year or extract if possible
                    "source": "Tavily News"
                })
            
            print(f"[MarketClient] Found {len(news_items)} news items.")
            return news_items
            
        except requests.exceptions.RequestException as e:
            print(f"[MarketClient] API Request Error: {e}")
            return []
        except Exception as e:
            print(f"[MarketClient] Unexpected Error: {e}")
            return []

if __name__ == "__main__":
    client = MarketClient()
    news = client.fetch_market_news("Solid State Batteries Market Trends")
    for item in news:
        print(f"- {item['title']} ({item['url']})")
