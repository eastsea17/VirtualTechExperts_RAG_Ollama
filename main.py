import argparse
import sys
import yaml
import uuid
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.layer1.query_expander import QueryExpander
from src.layer1.openalex_client import OpenAlexClient
from src.layer1.epo_client import EPOClient
from src.layer1.uspto_client import USPTOClient
from src.layer2.vector_store import VectorStoreManager
from src.layer3.debate_graph import AdvancedDebateGraph
from src.report_generator import ReportGenerator

def main():
    # 1. Parse Arguments
    with open("config/config.yaml", 'r') as f:
        config = yaml.safe_load(f)
        
    defaults = config.get('defaults', {})
    
    parser = argparse.ArgumentParser(description="Virtual Tech Experts & R&D System")
    parser.add_argument("topic", nargs='?', default=defaults.get('topic'), help="Research topic")
    parser.add_argument("--mode", default=defaults.get('mode', 'a'), choices=['a', 'b', 'c'], help="Debate Mode (a=Sequential, b=Parallel, c=Consensus)")
    
    args = parser.parse_args()
    
    print(f"=== VTE-R&D System Started ===")
    print(f"Topic: {args.topic}")
    print(f"Mode: {args.mode.upper()}")
    
    expert_id = f"exp_{uuid.uuid4().hex[:8]}"
    
    # 2. Layer 1: Data Acquisition
    print("\n--- Layer 1: Data Acquisition ---")
    qe = QueryExpander()
    optimized_query, keywords = qe.refine_search_query(args.topic)
    
    # 2a. OpenAlex
    oa_client = OpenAlexClient()
    papers = oa_client.fetch_papers(optimized_query)
    
    # 2b. EPO (Optional)
    epo_client = EPOClient()
    patents_epo = epo_client.fetch_patents(keywords[0])
    
    # 2c. USPTO (New)
    uspto_client = USPTOClient()
    patents_uspto = uspto_client.fetch_patents(keywords)
    
    combined_data = papers + patents_epo + patents_uspto
    if not combined_data:
        print("No data found. Exiting.")
        return

    # Data Preview
    print("\n=== Selected Data Sources ===")
    print(f"{'Source':<10} | {'Year':<6} | {'Title'}")
    print("-" * 80)
    for doc in combined_data[:20]: # Show top 20
        title = doc.get('title', 'N/A')[:60]
        year = str(doc.get('publication_year', 'N/A'))
        source = doc.get('source', 'OpenAlex') # Set default source if missing
        if 'patent_number' in doc: source = 'USPTO'
        
        print(f"{source:<10} | {year:<6} | {title}")
    print(f"... and {len(combined_data) - 20} more items." if len(combined_data) > 20 else "")
    print("-" * 80)

    # 3. Layer 2: Vector Store
    print("\n--- Layer 2: Intelligence Engine ---")
    vsm = VectorStoreManager()
    vsm.add_expert_knowledge(combined_data, expert_id, args.topic)
    
    # 4. Layer 3: Debate
    print(f"\n--- Layer 3: Debate Simulation (Mode {args.mode.upper()}) ---")
    debate = AdvancedDebateGraph()
    final_state = debate.run(args.topic, expert_id, args.mode)
    
    # Calculate Data Stats
    data_stats = {
        "OpenAlex Papers": len(papers),
        "EPO Patents": len(patents_epo),
        "USPTO Patents": len(patents_uspto),
        "Total Documents": len(combined_data)
    }
    
    # 5. Reporting
    print("\n--- Layer 4: Reporting ---")
    rg = ReportGenerator()
    report_path = rg.generate_report(final_state, data_stats=data_stats)
    
    if report_path:
        print(f"Done! Open report: {report_path}")

if __name__ == "__main__":
    main()
