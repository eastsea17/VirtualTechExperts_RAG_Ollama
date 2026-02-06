import sys
import os
import csv
import time
import datetime
from typing import List, Dict, Any

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.layer1.query_expander import QueryExpander, adaptive_fetch
from src.layer1.openalex_client import OpenAlexClient
from src.layer1.epo_client import EPOClient
from src.layer1.uspto_client import USPTOClient
from src.layer1.market_client import MarketClient

# Configuration
TEST_TOPIC = "ammonia cracking based hydrogen generation"
RESULTS_DIR = "results"

def ensure_results_dir():
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)

def normalize_data_for_csv(data: List[Dict[str, Any]], source_type: str) -> List[Dict[str, Any]]:
    """
    Normalize data fields for CSV export.
    Target Columns: Source, Type, ID, Title, Date, Abstract/Summary, Link
    """
    normalized = []
    for item in data:
        row = {
            "Source": source_type,
            "Type": "Unknown",
            "ID": "N/A",
            "Title": "N/A",
            "Date": "N/A",
            "Abstract": "N/A",
            "Link": "N/A"
        }
        
        # OpenAlex Papers
        if source_type == "OpenAlex":
            row["Type"] = "Paper"
            row["ID"] = item.get('id', 'N/A')
            row["Title"] = item.get('title', 'N/A')
            row["Date"] = str(item.get('publication_year', 'N/A'))
            # Abstract is usually inverted index, might be missing or raw. 
            # OpenAlexClient might have processed it? 
            # Looking at client code (implied), usually it returns dict.
            # We'll just grab what we can.
            row["Abstract"] = str(item.get('abstract', ''))[:500] 
            row["Link"] = item.get('doi', item.get('id', ''))

        # EPO Patents (OPS)
        elif source_type == "EPO":
            row["Type"] = "Patent"
            # EPO client returns dict with 'id', 'title', 'abstract', 'published_date'
            row["ID"] = item.get('id', 'N/A')
            row["Title"] = item.get('title', 'N/A')
            row["Date"] = item.get('published_date', 'N/A')
            row["Abstract"] = item.get('abstract', 'N/A')[:500]
            if item.get('url'):
                 row["Link"] = item.get('url')
            else:
                 row["Link"] = f"https://worldwide.espacenet.com/publicationDetails/biblio?CC={item.get('id','').split('.')[0]}&NR={item.get('id','').split('.')[1]}&KC={item.get('id','').split('.')[2]}"

            
        # USPTO Patents
        elif source_type == "USPTO":
            row["Type"] = "Patent"
            row["ID"] = item.get('patent_number', 'N/A')
            row["Title"] = item.get('title', 'N/A')
            row["Date"] = item.get('date', 'N/A')
            row["Abstract"] = item.get('abstract', 'N/A')[:500]
            row["Link"] = f"https://patents.google.com/patent/US{item.get('patent_number','')}"

        # Tavily News
        elif source_type == "Tavily":
            row["Type"] = "News"
            row["ID"] = "N/A"
            row["Title"] = item.get('title', 'N/A')
            row["Date"] = item.get('published_date', 'N/A')
            row["Abstract"] = item.get('content', 'N/A')[:500]
            row["Link"] = item.get('url', 'N/A')
            
        normalized.append(row)
    return normalized

def run_layer1_test():
    print(f"\n🚀 Starting Layer 1 Data Acquisition Test")
    print(f"🎯 Topic: {TEST_TOPIC}")
    print("----------------------------------------------------------------")
    
    ensure_results_dir()
    
    # 1. Query Expansion
    print("\n[1] Generating Search Strategy via QueryExpander...")
    qe = QueryExpander()
    queries = qe.generate_search_queries(TEST_TOPIC)
    keywords = qe._extract_keywords(TEST_TOPIC)
    
    print(f"    > Extracted Keywords: {keywords}")
    print(f"    > Generated Queries ({len(queries)}):")
    for i, q in enumerate(queries):
        print(f"      Q{i+1}: {q}")
        
    all_collected_data = []
    
    # 2. OpenAlex (Adaptive)
    print("\n[2] Fetching Papers from OpenAlex...")
    oa_client = OpenAlexClient()
    papers = adaptive_fetch(oa_client.fetch_papers, queries, limit=20, source_name="OpenAlex")
    print(f"    ✅ Collected {len(papers)} papers.")
    all_collected_data.extend(normalize_data_for_csv(papers, "OpenAlex"))
    
    # 3. EPO Patents (Adaptive)
    print("\n[3] Fetching Patents from EPO (European Patent Office)...")
    epo_client = EPOClient()
    epo_patents = adaptive_fetch(epo_client.fetch_patents, queries, limit=20, source_name="EPO")
    print(f"    ✅ Collected {len(epo_patents)} EPO patents.")
    all_collected_data.extend(normalize_data_for_csv(epo_patents, "EPO"))
    
    # 4. USPTO Patents (Keyword-based)
    print("\n[4] Fetching Patents from USPTO...")
    uspto_client = USPTOClient()
    # USPTO client usually takes a list of keywords or single string? 
    # main.py passes 'keywords' (list).
    uspto_patents = uspto_client.fetch_patents(keywords)
    print(f"    ✅ Collected {len(uspto_patents)} USPTO patents.")
    all_collected_data.extend(normalize_data_for_csv(uspto_patents, "USPTO"))
    
    # 5. Tavily News (Adaptive)
    print("\n[5] Fetching Market News via Tavily...")
    market_client = MarketClient()
    news = adaptive_fetch(market_client.fetch_market_news, queries, limit=10, source_name="Tavily")
    print(f"    ✅ Collected {len(news)} news items.")
    all_collected_data.extend(normalize_data_for_csv(news, "Tavily"))
    
    # 6. Export Results
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{RESULTS_DIR}/layer1_data_collection_{timestamp}.csv"
    
    print(f"\n[6] Exporting results to {filename}...")
    
    if all_collected_data:
        keys = all_collected_data[0].keys()
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_collected_data)
        print(f"    ✅ Export complete! Total {len(all_collected_data)} rows.")
    else:
        print("    ⚠️ No data collected to export.")

    print("\n🎉 Layer 1 Test Complete.")

if __name__ == "__main__":
    run_layer1_test()
