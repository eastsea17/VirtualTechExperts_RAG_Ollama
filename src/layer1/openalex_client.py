import requests
import yaml
from typing import List, Dict, Any

class OpenAlexClient:
    """
    Client for fetching academic papers from OpenAlex API.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        self.base_url = self.config['data_acquisition']['openalex']['base_url']
        self.user_agent = self.config['data_acquisition']['openalex']['user_agent_email']
        self.limit = self.config['data_acquisition']['openalex']['fetch_limit']
        
    def fetch_papers(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetches papers based on the optimized query string.
        """
        print(f"[OpenAlexClient] Fetching papers for: '{query}'...")
        
        params = {
            "search": query,
            "per-page": min(self.limit, 200),
            "filter": "has_abstract:true,from_publication_date:2020-01-01" # Default to recent papers
        }
        
        headers = {
            "User-Agent": f"mailto:{self.user_agent}"
        }
        
        try:
            response = requests.get(self.base_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            
            papers = []
            for result in results:
                title = result.get("title")
                abstract_inverted = result.get("abstract_inverted_index")
                
                # OpenAlex stores abstracts as inverted indexes to save space
                abstract = self._reconstruct_abstract(abstract_inverted)
                
                if title and abstract:
                    papers.append({
                        "id": result.get("id"),
                        "title": title,
                        "abstract": abstract,
                        "publication_year": result.get("publication_year"),
                        "cited_by_count": result.get("cited_by_count", 0),
                        "url": result.get("id")
                    })
            
            print(f"[OpenAlexClient] Found {len(papers)} papers.")
            return papers
            
        except requests.exceptions.RequestException as e:
            print(f"[OpenAlexClient] API Request Error: {e}")
            return []
        except Exception as e:
            print(f"[OpenAlexClient] Unexpected Error: {e}")
            return []

    def _reconstruct_abstract(self, inverted_index: Dict) -> str:
        """
        Reconstructs the abstract from the inverted index.
        """
        if not inverted_index:
            return ""
            
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        
        word_positions.sort()
        return " ".join([word for _, word in word_positions])

if __name__ == "__main__":
    client = OpenAlexClient()
    papers = client.fetch_papers("blockchain")
    if papers:
        print(f"First paper title: {papers[0]['title']}")
