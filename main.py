import argparse
import sys
import yaml
import uuid
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.layer1.query_expander import QueryExpander, adaptive_fetch
from src.layer1.openalex_client import OpenAlexClient
from src.layer1.epo_client import EPOClient
from src.layer1.uspto_client import USPTOClient
from src.layer2.vector_store import VectorStoreManager
from src.layer3.debate_graph import AdvancedDebateGraph
from src.layer3.report_generator import ReportGenerator


def main():
    # 1. Parse Arguments
    with open("config/config.yaml", 'r') as f:
        config = yaml.safe_load(f)
        
    defaults = config.get('defaults', {})
    
    parser = argparse.ArgumentParser(description="Virtual Tech Experts & R&D System")
    parser.add_argument("topic", nargs='?', default=defaults.get('topic'), help="Research topic")
    parser.add_argument("--mode", default=defaults.get('mode', 'a'), choices=['a', 'b', 'c'], help="Debate Mode (a=Sequential, b=Parallel, c=Consensus)")
    parser.add_argument("--turn", type=int, help="Override Max Turns per Persona (for Mode C mainly)", default=None)
    
    # New Arguments for Reuse/Management
    parser.add_argument("--list", action="store_true", help="List all available experts")
    parser.add_argument("--expert_id", type=str, help="Reuse an existing expert by ID (skips data collection)")
    parser.add_argument("--delete", type=str, help="Delete an expert by ID")
    
    args = parser.parse_args()
    
    print(f"=== VTE-R&D System V2.5 ===")
    
    # Initialize Vector Store Manager (needed for all operations)
    vsm = VectorStoreManager()

    # --- Feature 1: List Experts ---
    if args.list:
        print("\n=== Available Virtual Experts ===")
        experts = vsm.list_experts()
        if not experts:
            print("No experts found in the database.")
            return
            
        # Header Layout
        header = f"{'Expert ID':<15} | {'Topic':<35} | {'Art.':<5} | {'Pat.':<5} | {'News':<5} | {'Total'}"
        print("-" * len(header))
        print(header)
        print("-" * len(header))
        
        for exp in experts:
            eid = exp['expert_id'][:15]
            topic = exp['topic'][:35]
            n_art = exp.get('articles', 0)
            n_pat = exp.get('patents', 0)
            n_news = exp.get('news', 0)
            n_total = exp['doc_count']
            
            print(f"{eid:<15} | {topic:<35} | {n_art:<5} | {n_pat:<5} | {n_news:<5} | {n_total}")
            
        print("-" * len(header))
        print("Usage:")
        print("  Reuse:  python main.py --expert_id <ID>")
        print("  Delete: python main.py --delete <ID>")
        return

    # --- Feature 2: Delete Expert ---
    if args.delete:
        print(f"\n[Usage] Deleting Expert ID: {args.delete}...")
        if not vsm.expert_exists(args.delete):
             print(f"Error: Expert ID '{args.delete}' not found. Cannot delete.")
             return
             
        confirm = input(f"Are you sure you want to permanently delete expert '{args.delete}'? (y/n): ")
        if confirm.lower() == 'y':
            success = vsm.delete_expert(args.delete)
            if success:
                print(f"Expert '{args.delete}' deleted successfully.")
            else:
                print(f"Failed to delete expert '{args.delete}'.")
        else:
            print("Deletion cancelled.")
        return

    # --- Feature 3: Reuse Existing Expert (Skip L1/L2) ---
    if args.expert_id:
        if not vsm.expert_exists(args.expert_id):
            print(f"Error: Expert ID '{args.expert_id}' not found.")
            return
            
        topic = vsm.get_expert_topic(args.expert_id)
        if not topic: topic = "Unknown Topic"
            
        print(f"\n=== Reusing Expert: {args.expert_id} ===")
        print(f"Topic: {topic}")
        print(f"Mode: {args.mode.upper()}")
        if args.turn:
            print(f"Turn Limit Override: {args.turn}")
        
        # Skip Layer 1 & 2 -> Jump to Layer 3 (Debate)
        print(f"\n--- Layer 3: Debate Simulation (Mode {args.mode.upper()}) ---")
        debate = AdvancedDebateGraph()
        
        data_stats = {
            "Source": "Vector Store Cache", 
            "Expert ID": args.expert_id,
            "Reused": True
        }
        
        final_state = debate.run(topic, args.expert_id, args.mode, turns=args.turn)
        
        # Layer 4: Reporting
        print("\n--- Layer 4: Reporting ---")
        rg = ReportGenerator()
        report_path = rg.generate_report(final_state, data_stats=data_stats)
        
        if report_path:
            print(f"Done! Open report: {report_path}")
        return

    # --- Feature 4: Standard Pipeline (New Expert) ---
    # Ensure topic is provided
    if not args.topic:
        print("Error: No topic provided for new research.")
        print("Usage: python main.py \"Topic Name\"")
        return

    print(f"Topic: {args.topic}")
    print(f"Mode: {args.mode.upper()}")
    if args.turn:
        print(f"Turn Limit Override: {args.turn}")
    
    # Generate Sequential Expert ID
    # vsm is already initialized above
    expert_id = vsm.generate_next_expert_id()
    print(f"Assigning Next Available Expert ID: {expert_id}")
    
    # 2. Layer 1: Data Acquisition
    print("\n--- Layer 1: Data Acquisition ---")
    qe = QueryExpander()
    queries = qe.generate_search_queries(args.topic)
    keywords = qe._extract_keywords(args.topic)
    
    # 2a. OpenAlex
    oa_client = OpenAlexClient()
    papers = adaptive_fetch(oa_client.fetch_papers, queries, limit=20, source_name="OpenAlex")
    
    # 2b. EPO (Optional)
    epo_client = EPOClient()
    patents_epo = adaptive_fetch(epo_client.fetch_patents, queries, limit=20, source_name="EPO")
    
    # 2c. USPTO (New)
    uspto_client = USPTOClient()
    patents_uspto = uspto_client.fetch_patents(keywords)
    
    # 2d. Tavily (New)
    from src.layer1.market_client import MarketClient
    market_client = MarketClient()
    market_news = adaptive_fetch(market_client.fetch_market_news, queries, limit=10, source_name="Tavily")
    
    combined_data = papers + patents_epo + patents_uspto + market_news
    if not combined_data:
        print("No data found. Exiting.")
        return

    # Data Preview
    print("\n=== Selected Data Sources ===")
    print(f"{'Source':<15} | {'Year':<6} | {'Title'}")
    print("-" * 80)
    for doc in combined_data[:20]: # Show top 20
        title = doc.get('title', 'N/A')[:55]
        year = str(doc.get('publication_year', 'N/A'))
        source = doc.get('source', 'OpenAlex') # Set default source if missing
        if 'patent_number' in doc: source = 'USPTO'
        
        print(f"{source:<15} | {year:<6} | {title}")
    print(f"... and {len(combined_data) - 20} more items." if len(combined_data) > 20 else "")
    print("-" * 80)

    # --- CSV Export (New) ---
    print("\n   > Exporting raw data log...")
    rg_temp = ReportGenerator() # Temp instance for export
    csv_path = rg_temp.export_data_collection_csv(combined_data, args.topic)
    if csv_path:
        print(f"   > CSV Log Saved: {csv_path}")

    # 3. Layer 2: Vector Store
    print("\n--- Layer 2: Intelligence Engine ---")
    # vsm already initialized at top
    vsm.add_expert_knowledge(combined_data, expert_id, args.topic)
    
    # 4. Layer 3: Debate
    print(f"\n--- Layer 3: Debate Simulation (Mode {args.mode.upper()}) ---")
    debate = AdvancedDebateGraph()
    final_state = debate.run(args.topic, expert_id, args.mode, turns=args.turn)
    
    # Calculate Data Stats
    data_stats = {
        "OpenAlex Papers": len(papers),
        "EPO Patents": len(patents_epo),
        "USPTO Patents": len(patents_uspto),
        "Tavily News": len(market_news), 
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
