import time
from src.layer1.query_expander import QueryExpander

def test_query_expansion_logic():
    print("🚀 Initializing QueryExpander for Logic Visualization...")
    qe = QueryExpander()
    
    # 10 Complex Technical Topics (approx. 5-10 words each)
    test_topics = [
        "High voltage cathode materials for solid state lithium batteries",
        #"Reinforcement learning algorithms for autonomous robot navigation",
        #"Carbon capture utilization and storage in cement manufacturing",
        #"Quantum error correction codes for superconducting qubits",
        #"Perovskite solar cell stability under high humidity conditions",
        #"Nickel-rich cathode precursors for LIB",
        #"HHydrophobic coatings for aerospace aluminum alloys",
        #"Direct air capture absorbents using amine-functionalized metal-organic frameworks",
        #"Single-atom platinum catalysts on ceria support for CO oxidation",
        "Zeolite catalysts synthesis"
    ]
    
    print(f"🎯 Loaded {len(test_topics)} test topics.\n")
    print("="*80)

    for i, topic in enumerate(test_topics):
        print(f"\nExample #{i+1}: {topic}")
        print("-" * 80)
        
        # 1. Extract Keywords
        print("1️⃣  Extracted Keywords:")
        keywords = qe._extract_keywords(topic)
        print(f"   {keywords}")
        
        # 2. Synonyms (if applicable)
        print("\n2️⃣  Generated Synonyms (Logic: word count < 10):")
        # Check logic manually to see if it would trigger
        if len(topic.split()) < 10:
            synonyms = qe._generate_synonyms(topic)
            if synonyms:
                for syn in synonyms:
                    print(f"   • {syn}")
            else:
                print("   (No synonyms generated)")
        else:
            print(f"   (Skipped: Topic length {len(topic.split())} >= 10 words)")

        # 3. N-1 Adaptive Strategy Candidates
        print("\n3️⃣  N-1 Adaptive Strategy (Fallback Queries):")
        # We simulate the logic inside generate_search_queries regarding N-1
        N = len(keywords)
        if N < 3:
            print("   (Skipped: Less than 3 keywords, logic prevents N-1 expansion)")
        else:
            import itertools
            combos = list(itertools.combinations(keywords, N-1))
            if combos:
                # Use the ranking method to see which are chosen
                ranked = qe._rank_combinations(topic, combos, limit=2)
                print(f"   Total {len(combos)} combinations possible.")
                print("   Top 2 Selected by LLM:")
                for combo in ranked:
                    print(f"   • {' AND '.join([f'\"{k}\"' for k in combo])}")
            else:
                print("   (No combinations possible)")
        
        print("\n4️⃣  Final Query List (Simulation):")
        full_queries = qe.generate_search_queries(topic)
        for idx, q in enumerate(full_queries):
            print(f"   Q{idx+1}: {q}")
            
        print("="*80)
        # Small sleep to avoid rate limits if any, though likely local/cloud Inference
        time.sleep(1)

if __name__ == "__main__":
    test_query_expansion_logic()
