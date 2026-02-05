import argparse
import sys
import os
import yaml

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.layer2.vector_store import VectorStoreManager
from src.layer3.debate_graph import AdvancedDebateGraph
from src.report_generator import ReportGenerator

def main():
    parser = argparse.ArgumentParser(description="Virtual Tech Experts Reuse Module")
    parser.add_argument("--list", action="store_true", help="List all available experts")
    parser.add_argument("--expert_id", type=str, help="ID of the expert to reuse")
    parser.add_argument("--delete", type=str, help="ID of the expert to delete")
    parser.add_argument("--mode", default="a", choices=['a', 'b', 'c'], help="Debate Mode")
    
    args = parser.parse_args()
    
    vsm = VectorStoreManager()
    
    # 1. List Experts
    if args.list:
        print("\n=== Available Virtual Experts ===")
        experts = vsm.list_experts()
        if not experts:
            print("No experts found in the database.")
            return
            
        print(f"{'Expert ID':<20} | {'Docs':<5} | {'Topic'}")
        print("-" * 60)
        for exp in experts:
            print(f"{exp['expert_id']:<20} | {exp['doc_count']:<5} | {exp['topic']}")
        print("-" * 60)
        print("To reuse an expert: python main_reuse.py --expert_id <Expert ID>")
        print("To delete an expert: python main_reuse.py --delete <Expert ID>")
        return

    # 2. Delete Expert
    if args.delete:
        print(f"\n[Usage] Deleting Expert ID: {args.delete}...")
        # Check existence first
        exists = vsm.expert_exists(args.delete)
        if not exists:
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

    # 3. Reuse Specific Expert
    if args.expert_id:
        if not vsm.expert_exists(args.expert_id):
            print(f"Error: Expert ID '{args.expert_id}' not found.")
            return
            
        topic = vsm.get_expert_topic(args.expert_id)
        if not topic:
            topic = "Unknown Topic"
            
        print(f"\n=== Reusing Expert: {args.expert_id} ===")
        print(f"Topic: {topic}")
        print(f"Mode: {args.mode.upper()}")
        
        # Skip Layer 1 & 2 -> Jump to Layer 3 (Debate)
        print(f"\n--- Layer 3: Debate Simulation (Mode {args.mode.upper()}) ---")
        debate = AdvancedDebateGraph()
        
        # Determine stats for report (approximate since we don't have raw lists)
        # We can fetch counts from metadata again if needed, or just say "Cached Data"
        data_stats = {
            "Source": "Vector Store Cache", 
            "Expert ID": args.expert_id,
            "Reused": True
        }
        
        final_state = debate.run(topic, args.expert_id, args.mode)
        
        # Layer 4: Reporting
        print("\n--- Layer 4: Reporting ---")
        rg = ReportGenerator()
        report_path = rg.generate_report(final_state, data_stats=data_stats)
        
        if report_path:
            print(f"Done! Open report: {report_path}")
            
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
