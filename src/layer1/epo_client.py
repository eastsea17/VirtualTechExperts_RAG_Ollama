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
        
        
        # Determine CQL query
        # If the keyword contains boolean operators or quotes, assume it's a constructed query
        # and search in the default index (often title/abstract/fulltext) or assume user knows CQL.
        # But 'QueryExpander' returns "Term" AND "Term". 
        # For EPO OPS, broad search on title/abs is better for these.
        # Try wrapping in parens for safety? Or just raw.
        # Raw "A" AND "B" is usually valid CQL for default fields.
        if ' AND ' in keyword or ' OR ' in keyword:
             cql_query = keyword
        else:
             cql_query = f'ti="{keyword}"'
             
        # Use params for proper encoding
        params = {'q': cql_query}
        search_url = f"{self.service_url}/published-data/search"
        
        try:
            response = requests.get(search_url, headers=headers, params=params, timeout=30)
            if response.status_code == 404:
                print(f"[EPOClient] No results found.")
                return []
            response.raise_for_status()
            
            data = response.json()
            # Parsing logic would depend on specific EPO JSON structure
            # Parsing logic for EPO OPS JSON (v3.2)
            results = []
            
            # Parsing logic for EPO OPS JSON (v3.2)
            results = []
            
            # Navigate efficiently through the deep structure
            ops_data = data.get('ops:world-patent-data', {})
            
            # Note: The structure varies slightly between services.
            # For Search, it is often direct: world-patent-data -> biblio-search
            biblio = ops_data.get('ops:biblio-search', {})
            
            # Fallback for standardization wrapper if present (sometimes happens in other endpoints)
            if not biblio:
                 std_data = ops_data.get('ops:standardization', {})
                 output = std_data.get('ops:output', {})
                 biblio = output.get('ops:biblio-search', {})
            
            search_result = biblio.get('ops:search-result', {})
            publications = search_result.get('ops:publication-reference', [])
            
            # Ensure list
            if not isinstance(publications, list):
                publications = [publications]
                
            print(f"[EPOClient] Found {len(publications)} raw patent references.")
                
            # Iterate through publications
            for pub in publications:
                try:
                    # Extract Document ID
                    # Document-id can be a list or dict. We want '@document-id-type': 'docdb'
                    doc_id_list = pub.get('document-id', [])
                    if isinstance(doc_id_list, dict): doc_id_list = [doc_id_list]
                    
                    docdb_obj = None
                    for ref in doc_id_list:
                        if ref.get('@document-id-type') == 'docdb':
                            docdb_obj = ref
                            break
                    
                    # Fallback if no docdb type found explicitly (or if API changes simplified)
                    if not docdb_obj and doc_id_list:
                        docdb_obj = doc_id_list[0]
                        
                    if not docdb_obj:
                        continue
                        
                    doc_number = docdb_obj.get('doc-number', {}).get('$', 'Unknown')
                    kind = docdb_obj.get('kind', {}).get('$', '')
                    country = docdb_obj.get('country', {}).get('$', 'EP')
                    date = docdb_obj.get('date', {}).get('$', 'Unknown Date')
                    
                    full_id = f"{country}.{doc_number}.{kind}"
                    
                    # Fetch detailed abstract and title using docdb ID
                    # Note: We prioritize fetching details because OPS Search often lacks them in result view
                    title, abstract, applicant = self._fetch_patent_details(country, doc_number, kind)
                    
                    # Store result
                    results.append({
                        "source": "EPO",
                        "id": full_id,
                        "title": title if title else f"Patent {country}{doc_number}",
                        "abstract": abstract if abstract else "Abstract not available via OPS.",
                        "published_date": date,
                        "url": f"https://worldwide.espacenet.com/publicationDetails/biblio?CC={country}&NR={doc_number}&KC={kind}",
                        "authors": [applicant] if applicant else [],
                        "raw": pub
                    })
                    
                except Exception as ex:
                    print(f"[EPOClient] Parse error for one item: {ex}")
                    continue
            
            return results
        except Exception as e:
            print(f"[EPOClient] Fetch Error: {e}")
            return []

    def _fetch_patent_details(self, country, number, kind):
        """
        Helper to fetch Title and Abstract for a specific patent.
        """
        try:
            url = f"{self.service_url}/published-data/publication/docdb/{country}/{number}/{kind}/biblio"
            headers = {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200: return None, None, None
            
            b_data = res.json()
            biblio = b_data.get('ops:world-patent-data', {}).get('exchange-documents', {}).get('exchange-document', {})
            
            # Title
            title = "Unknown Patent"
            titles = biblio.get('bibliographic-data', {}).get('invention-title', [])
            if isinstance(titles, dict): titles = [titles]
            for t in titles:
                if t.get('@lang') == 'en':
                    title = t.get('$', title)
                    break
            
            # Abstract
            abstract = None
            abst_obj = biblio.get('abstract', [])
            if isinstance(abst_obj, dict): abst_obj = [abst_obj]
            for a in abst_obj:
                if a.get('@lang') == 'en':
                    p_text = a.get('p', {})
                    if isinstance(p_text, list): 
                        abstract = " ".join([p.get('$', '') for p in p_text])
                    else:
                        abstract = p_text.get('$', '')
                    break
            
            # Applicant
            applicant = "Unknown"
            apps = biblio.get('bibliographic-data', {}).get('parties', {}).get('applicants', {}).get('applicant', [])
            if isinstance(apps, dict): apps = [apps]
            if apps:
                applicant = apps[0].get('applicant-name', {}).get('name', {}).get('$', 'Unknown')
                
            return title, abstract, applicant
            
        except Exception:
            return None, None, None

if __name__ == "__main__":
    client = EPOClient()
